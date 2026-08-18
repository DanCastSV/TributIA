"""
Pruebas para la carga múltiple de documentos (POST /documentos/lote/).
Mockea OCR y Gemini igual que tests/test_analizador.py para que sea
rápido, determinista y no gaste cuota real de la API.
"""

import shutil
import tempfile
from unittest.mock import patch

import fitz
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from core.analysis_capacity import CapacidadAnalisisAgotada
from core.models import DocumentoTributario
from core.views import MAX_ARCHIVOS_LOTE

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_lote_")


def _pdf_valido_bytes():
    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), 'FACTURA SINTETICA QA')
    contenido = documento.tobytes()
    documento.close()
    return contenido


def _pdf(nombre="factura.pdf"):
    return SimpleUploadedFile(nombre, _pdf_valido_bytes(), content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class CargaMultipleTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.usuario = User.objects.create_user(username="lote_user", password="clave12345")
        self.client = Client()
        self.client.force_login(self.usuario)

    @patch("core.services.analizador.analizar_documento_con_gemini")
    @patch("core.services.analizador.extraer_texto_documento")
    def test_sube_varios_archivos_validos(self, mock_ocr, mock_gemini):
        mock_ocr.return_value = "FACTURA ACME TOTAL $10.00"
        mock_gemini.return_value = {
            "empresa": "ACME", "cliente": None, "tipo_documento": "Factura", "fecha": "01/01/2026",
            "numero_documento": None, "nit": None, "direccion": None, "resumen": "resumen",
            "es_documento_tributario": True, "es_deducible": True, "justificacion_deducible": "ok",
            "subtotal": 10, "iva": 1.3, "total": 11.3, "recomendacion": "ok",
        }

        respuesta = self.client.post(
            "/documentos/lote/",
            {"archivos": [_pdf("a.pdf"), _pdf("b.pdf")]},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(DocumentoTributario.objects.filter(usuario=self.usuario).count(), 2)

    def test_sin_archivos_no_truena(self):
        respuesta = self.client.post("/documentos/lote/", {})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(DocumentoTributario.objects.exists())

    def test_rechaza_archivo_invalido_sin_tronar_el_resto(self):
        archivo_invalido = SimpleUploadedFile("falso.pdf", b"NO ES PDF", content_type="application/pdf")
        respuesta = self.client.post(
            "/documentos/lote/", {"archivos": [archivo_invalido]},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(DocumentoTributario.objects.exists())

    def test_respeta_el_tope_maximo_de_archivos_por_lote(self):
        archivos = [_pdf(f"archivo_{i}.pdf") for i in range(MAX_ARCHIVOS_LOTE + 3)]
        with patch("core.services.analizador.analizar_documento_con_gemini") as mock_gemini, \
             patch("core.services.analizador.extraer_texto_documento") as mock_ocr:
            mock_ocr.return_value = "FACTURA ACME"
            mock_gemini.return_value = {
                "empresa": "ACME", "cliente": None, "tipo_documento": "Factura", "fecha": None,
                "numero_documento": None, "nit": None, "direccion": None, "resumen": None,
                "es_documento_tributario": True, "es_deducible": None, "justificacion_deducible": None,
                "subtotal": None, "iva": None, "total": None, "recomendacion": None,
            }
            self.client.post("/documentos/lote/", {"archivos": archivos})

        self.assertEqual(
            DocumentoTributario.objects.filter(usuario=self.usuario).count(),
            MAX_ARCHIVOS_LOTE,
        )

    @patch("core.views.reservar_capacidad_analisis", side_effect=CapacidadAnalisisAgotada)
    def test_capacidad_agotada_a_mitad_del_lote_no_truena(self, _capacidad):
        respuesta = self.client.post(
            "/documentos/lote/", {"archivos": [_pdf("a.pdf"), _pdf("b.pdf")]},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(DocumentoTributario.objects.exists())
