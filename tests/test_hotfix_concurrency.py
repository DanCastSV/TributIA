from unittest.mock import MagicMock, patch

import fitz
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.analysis_capacity import CapacidadAnalisisAgotada, reservar_capacidad_analisis
from core.models import DocumentoTributario


class CapacidadAnalisisTests(SimpleTestCase):
    @override_settings(TRIBUTIA_MAX_ANALISIS_CONCURRENTES=2)
    @patch('core.analysis_capacity.connection')
    def test_rechaza_inmediatamente_si_todos_los_slots_estan_ocupados(self, conexion):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(False,), (False,)]
        conexion.vendor = 'postgresql'
        conexion.cursor.return_value.__enter__.return_value = cursor

        with self.assertRaises(CapacidadAnalisisAgotada):
            with reservar_capacidad_analisis():
                self.fail('No debe entrar sin capacidad')

        self.assertEqual(cursor.execute.call_count, 2)

    @override_settings(TRIBUTIA_MAX_ANALISIS_CONCURRENTES=2)
    @patch('core.analysis_capacity.connection')
    def test_libera_el_slot_incluso_si_el_analisis_falla(self, conexion):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(True,), (True,)]
        conexion.vendor = 'postgresql'
        conexion.cursor.return_value.__enter__.return_value = cursor

        with self.assertRaises(RuntimeError):
            with reservar_capacidad_analisis():
                raise RuntimeError('fallo sintético')

        consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
        self.assertIn('SELECT pg_try_advisory_lock(%s)', consultas)
        self.assertIn('SELECT pg_advisory_unlock(%s)', consultas)


def _pdf_sintetico():
    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), 'FACTURA SINTETICA QA')
    contenido = documento.tobytes()
    documento.close()
    return contenido


class CapacidadEnVistasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username='capacidad_user',
            password='StrongPass!123',
        )
        self.client = Client()
        self.client.force_login(self.usuario)

    @patch(
        'core.api_views.reservar_capacidad_analisis',
        side_effect=CapacidadAnalisisAgotada,
    )
    def test_api_responde_429_sin_guardar_documento_si_esta_ocupado(self, _capacidad):
        respuesta = self.client.post(
            '/api/v1/analizar-documento/',
            {
                'nombre': 'Factura QA',
                'archivo': SimpleUploadedFile(
                    'factura.pdf',
                    _pdf_sintetico(),
                    content_type='application/pdf',
                ),
            },
        )

        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(respuesta.json()['error'], 'capacidad_temporal_agotada')
        self.assertEqual(respuesta['Retry-After'], '15')
        self.assertFalse(DocumentoTributario.objects.exists())

    @patch(
        'core.views.reservar_capacidad_analisis',
        side_effect=CapacidadAnalisisAgotada,
    )
    def test_web_redirige_sin_guardar_documento_si_esta_ocupado(self, _capacidad):
        respuesta = self.client.post(
            '/documentos/',
            {
                'nombre': 'Factura QA',
                'archivo': SimpleUploadedFile(
                    'factura.pdf',
                    _pdf_sintetico(),
                    content_type='application/pdf',
                ),
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(DocumentoTributario.objects.exists())
