"""
Pruebas de seguridad para core/api_views.py::analizar_documento_api.

Cubre el hallazgo V-01 del informe de seguridad (2026-08-15): el endpoint
tenía @csrf_exempt pese a autenticar por cookie de sesión, lo que
permitía un bypass de CSRF. Estas pruebas usan Client(enforce_csrf_checks=True)
para que Django SÍ aplique la protección CSRF real (el test client, por
defecto, la desactiva).
"""

import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_csrf_")


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class AnalizarDocumentoApiCsrfTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.usuario = User.objects.create_user(username="usuario_csrf", password="clave12345")
        self.client.login(username="usuario_csrf", password="clave12345")

    def _archivo(self):
        return SimpleUploadedFile("factura.pdf", b"contenido-pdf-simulado", content_type="application/pdf")

    def test_sesion_valida_sin_token_csrf_devuelve_403(self):
        response = self.client.post(
            "/api/v1/analizar-documento/",
            {"archivo": self._archivo()},
        )
        self.assertEqual(response.status_code, 403)

    @patch("core.services.analizador.analizar_documento_con_gemini")
    @patch("core.services.analizador.extraer_texto_documento")
    def test_sesion_valida_con_token_csrf_correcto_pasa_la_proteccion(self, mock_ocr, mock_gemini):
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

        respuesta_login = self.client.get("/login/")
        csrf_token = respuesta_login.cookies["csrftoken"].value

        response = self.client.post(
            "/api/v1/analizar-documento/",
            {"archivo": self._archivo()},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 201)

    def test_token_csrf_incorrecto_devuelve_403(self):
        respuesta_login = self.client.get("/login/")
        # Cookie real presente, pero el header no coincide con ella.
        assert "csrftoken" in respuesta_login.cookies

        response = self.client.post(
            "/api/v1/analizar-documento/",
            {"archivo": self._archivo()},
            HTTP_X_CSRFTOKEN="token-invalido-de-otro-origen",
        )
        self.assertEqual(response.status_code, 403)

    def test_usuario_no_autenticado_con_csrf_valido_devuelve_401(self):
        """
        Con CSRF válido pero sin sesión, la vista sí debe llegar a
        evaluar la autenticación y rechazar con 401 (no con 403): el
        middleware de CSRF corre antes que la lógica de la vista, así
        que sin cookie CSRF en absoluto el 403 llega primero y nunca se
        alcanza a comprobar la sesión (cubierto por el siguiente caso).
        """
        client_anonimo = Client(enforce_csrf_checks=True)
        respuesta_login = client_anonimo.get("/login/")
        csrf_token = respuesta_login.cookies["csrftoken"].value

        response = client_anonimo.post(
            "/api/v1/analizar-documento/",
            {"archivo": self._archivo()},
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 401)

    def test_usuario_no_autenticado_sin_csrf_devuelve_403(self):
        """Sin cookie CSRF en absoluto, rechaza en la capa de CSRF (403) antes de llegar a la vista."""
        client_anonimo = Client(enforce_csrf_checks=True)
        response = client_anonimo.post(
            "/api/v1/analizar-documento/",
            {"archivo": self._archivo()},
        )
        self.assertEqual(response.status_code, 403)