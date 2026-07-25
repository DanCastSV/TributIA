"""
Pruebas para core/services/analizador.py:

- Unitarias puras para calcular_confianza() (sin BD, sin mocks).
- De integración para analizar_documento(), el flujo completo
  OCR -> regex -> spaCy -> Gemini -> guardado en BD, mockeando las
  dependencias externas costosas/lentas (Tesseract/OCR y Gemini) para que
  la prueba sea rápida, determinista y no gaste cuota real de la API.
"""

import shutil
import tempfile
import unittest
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import AnalisisDocumento, DocumentoTributario, EventoCalendario
from core.services.analizador import (
    DocumentoNoTributarioError,
    analizar_documento,
    calcular_confianza,
)

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_")


class CalcularConfianzaTests(unittest.TestCase):

    def test_todos_los_campos_clave_y_secundarios_presentes(self):
        analisis = {
            "empresa": "ACME", "tipo_documento": "Factura", "fecha": "01/01/2026", "total": 100,
            "cliente": "Juan", "numero_documento": "F-001", "iva": 13, "subtotal": 87, "nit": "1234-567890-123-4",
        }
        self.assertEqual(calcular_confianza(analisis), 1.0)

    def test_sin_ningun_campo_extraido(self):
        analisis = {k: None for k in (
            "empresa", "tipo_documento", "fecha", "total",
            "cliente", "numero_documento", "iva", "subtotal", "nit",
        )}
        self.assertEqual(calcular_confianza(analisis), 0.0)

    def test_solo_campos_clave_pesa_mas_que_solo_secundarios(self):
        solo_clave = calcular_confianza({
            "empresa": "ACME", "tipo_documento": "Factura", "fecha": "01/01/2026", "total": 100,
        })
        solo_secundarios = calcular_confianza({
            "cliente": "Juan", "numero_documento": "F-001", "iva": 13, "subtotal": 87, "nit": "1234-567890-123-4",
        })
        self.assertGreater(solo_clave, solo_secundarios)

    def test_cadenas_vacias_no_cuentan_como_extraidas(self):
        analisis = {"empresa": "", "tipo_documento": "   ", "fecha": None, "total": None}
        self.assertEqual(calcular_confianza(analisis), 0.0)


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class AnalizarDocumentoIntegracionTests(TestCase):
    """
    Integra el pipeline completo, pero mockea Tesseract/OCR y Gemini
    (las dos dependencias externas reales) para que la prueba sea
    rápida y no dependa de tener Tesseract instalado ni de gastar
    cuota de la API de Gemini.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.usuario = User.objects.create_user(username="usuario_test", password="clave12345")

    def _crear_documento(self, nombre="factura.pdf"):
        archivo = SimpleUploadedFile(nombre, b"contenido-pdf-simulado", content_type="application/pdf")
        return DocumentoTributario.objects.create(usuario=self.usuario, nombre=nombre, archivo=archivo)

    @patch("core.services.analizador.analizar_documento_con_gemini")
    @patch("core.services.analizador.extraer_texto_documento")
    def test_analiza_y_guarda_documento_tributario_valido(self, mock_ocr, mock_gemini):
        mock_ocr.return_value = "FACTURA\nEMPRESA: Ferretería ACME\nTOTAL: $113.00\nFecha: 15/03/2026"
        mock_gemini.return_value = {
            "empresa": "Ferretería ACME", "cliente": None, "tipo_documento": "Factura",
            "fecha": "15/03/2026", "numero_documento": "F-001", "nit": "0614-123456-102-1",
            "direccion": None, "resumen": "Factura de compra de materiales.",
            "es_documento_tributario": True, "es_deducible": False,
            "justificacion_deducible": "No aplica a deducciones personales.",
            "subtotal": 100.0, "iva": 13.0, "total": 113.0,
            "recomendacion": "Conservar el documento por si se requiere en una auditoría.",
        }

        doc = self._crear_documento()
        analizar_documento(doc)

        doc.refresh_from_db()
        self.assertEqual(doc.estado, "analizado")

        analisis = AnalisisDocumento.objects.get(documento=doc)
        self.assertTrue(analisis.es_documento_tributario)
        self.assertEqual(analisis.nombre_empresa, "Ferretería ACME")
        self.assertEqual(analisis.total, 113.0)
        self.assertGreater(analisis.confianza_clasificacion, 0)

        # Al detectar una fecha, debe crearse un evento en el calendario fiscal.
        self.assertTrue(
            EventoCalendario.objects.filter(usuario=self.usuario, fecha__day=15, fecha__month=3).exists()
        )

    @patch("core.services.analizador.analizar_documento_con_gemini")
    @patch("core.services.analizador.extraer_texto_documento")
    def test_rechaza_y_elimina_documento_no_tributario(self, mock_ocr, mock_gemini):
        mock_ocr.return_value = "Receta médica sin valor fiscal."
        mock_gemini.return_value = {
            "empresa": None, "cliente": None, "tipo_documento": None, "fecha": None,
            "numero_documento": None, "nit": None, "direccion": None,
            "resumen": None, "es_documento_tributario": False, "es_deducible": None,
            "justificacion_deducible": None, "subtotal": None, "iva": None, "total": None,
            "recomendacion": "Este documento no es un comprobante fiscal válido en El Salvador.",
        }

        doc = self._crear_documento(nombre="receta.pdf")
        doc_id = doc.id

        with self.assertRaises(DocumentoNoTributarioError):
            analizar_documento(doc)

        self.assertFalse(DocumentoTributario.objects.filter(id=doc_id).exists())
        self.assertFalse(AnalisisDocumento.objects.filter(documento_id=doc_id).exists())


if __name__ == "__main__":
    unittest.main()
