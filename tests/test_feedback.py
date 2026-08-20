"""
Pruebas para el endpoint de feedback de clasificación
(POST /documento/<id>/feedback/).
"""

import re
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from core.models import AnalisisDocumento, DocumentoTributario

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_feedback_")


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class FeedbackAnalisisTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.usuario = User.objects.create_user(username="feedback_user", password="clave12345")
        self.otro_usuario = User.objects.create_user(username="otro_user", password="clave12345")
        self.client = Client()
        self.client.force_login(self.usuario)

        archivo = SimpleUploadedFile("factura.pdf", b"contenido-pdf-simulado", content_type="application/pdf")
        self.documento = DocumentoTributario.objects.create(
            usuario=self.usuario, nombre="factura.pdf", archivo=archivo, estado="analizado",
        )
        self.analisis = AnalisisDocumento.objects.create(
            documento=self.documento, texto_extraido="FACTURA ACME",
        )

    def _url(self):
        return f"/documento/{self.documento.id}/feedback/"

    def test_marca_correcto(self):
        respuesta = self.client.post(self._url(), {"feedback": "correcto"})
        self.assertEqual(respuesta.status_code, 200)
        self.analisis.refresh_from_db()
        self.assertEqual(self.analisis.feedback_usuario, "correcto")
        self.assertEqual(self.analisis.feedback_comentario, "")

    def test_marca_incorrecto_con_comentario(self):
        respuesta = self.client.post(self._url(), {
            "feedback": "incorrecto", "comentario": "El monto total está mal",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.analisis.refresh_from_db()
        self.assertEqual(self.analisis.feedback_usuario, "incorrecto")
        self.assertEqual(self.analisis.feedback_comentario, "El monto total está mal")

    def test_rechaza_valor_invalido(self):
        respuesta = self.client.post(self._url(), {"feedback": "mas_o_menos"})
        self.assertEqual(respuesta.status_code, 400)
        self.analisis.refresh_from_db()
        self.assertIsNone(self.analisis.feedback_usuario)

    def test_no_puede_dar_feedback_de_documento_ajeno(self):
        self.client.force_login(self.otro_usuario)
        respuesta = self.client.post(self._url(), {"feedback": "correcto"})
        self.assertEqual(respuesta.status_code, 404)

    def test_requiere_autenticacion(self):
        self.client.logout()
        respuesta = self.client.post(self._url(), {"feedback": "correcto"})
        self.assertEqual(respuesta.status_code, 302)

    def test_botones_quedan_ocultos_si_ya_hay_feedback_guardado(self):
        """
        Bug reportado: al recargar la página después de dar feedback, los
        botones "Es correcto"/"Hay un error" seguían visibles y clicables,
        lo que permitía sobrescribir la respuesta anterior por accidente.
        """
        self.client.post(self._url(), {"feedback": "correcto"})

        respuesta = self.client.get(f"/documento/{self.documento.id}/")
        contenido = respuesta.content.decode()

        etiqueta_botones = re.search(r'<div[^>]*id="feedback-botones"[^>]*>', contenido)
        self.assertIsNotNone(etiqueta_botones)
        self.assertIn("hidden", etiqueta_botones.group())
        self.assertContains(respuesta, "Marcaste este análisis como correcto")
        self.assertContains(respuesta, "Cambiar respuesta")
