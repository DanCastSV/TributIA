"""
Pruebas para el registro de tokens de Gemini por usuario
(core/uso_gemini.py y la vista /uso-gemini/).
"""

from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.models import UsoGemini
from core.uso_gemini import registrar_uso_gemini


def _respuesta_con_uso(entrada=100, salida=50, total=150):
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=entrada,
            candidates_token_count=salida,
            total_token_count=total,
        )
    )


class RegistrarUsoGeminiTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="uso_user", password="clave12345")

    def test_crea_registro_con_los_conteos_correctos(self):
        registrar_uso_gemini(self.usuario, "analisis_documento", _respuesta_con_uso(100, 50, 150))

        registro = UsoGemini.objects.get()
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.tipo, "analisis_documento")
        self.assertEqual(registro.tokens_entrada, 100)
        self.assertEqual(registro.tokens_salida, 50)
        self.assertEqual(registro.tokens_total, 150)

    def test_no_hace_nada_si_usuario_es_none(self):
        registrar_uso_gemini(None, "asistente_chat", _respuesta_con_uso())
        self.assertEqual(UsoGemini.objects.count(), 0)

    def test_no_truena_si_la_respuesta_no_trae_usage_metadata(self):
        registrar_uso_gemini(self.usuario, "asistente_chat", object())
        self.assertEqual(UsoGemini.objects.count(), 0)


class RegistrarUsoGeminiSinBdTests(SimpleTestCase):
    def test_no_truena_sin_acceso_a_bd_ni_usuario_real(self):
        # Simula lo que hacen los tests existentes de gemini_client/asistente:
        # SimpleTestCase (sin BD) + un Mock como "usuario".
        from unittest.mock import Mock
        usuario_falso = Mock()
        registrar_uso_gemini(usuario_falso, "analisis_documento", _respuesta_con_uso())
        # Si no lanzó excepción, el try/except amplio cumplió su función.


class UsoGeminiResumenVistaTests(TestCase):
    def setUp(self):
        self.usuario_normal = User.objects.create_user(username="normal_user", password="clave12345")
        self.usuario_staff = User.objects.create_user(
            username="staff_user", password="clave12345", is_staff=True,
        )
        self.client = Client()

    def test_usuario_no_staff_no_puede_entrar(self):
        self.client.force_login(self.usuario_normal)
        respuesta = self.client.get("/uso-gemini/")
        self.assertNotEqual(respuesta.status_code, 200)

    def test_usuario_staff_ve_los_totales_agregados(self):
        registrar_uso_gemini(self.usuario_normal, "analisis_documento", _respuesta_con_uso(10, 5, 15))
        registrar_uso_gemini(self.usuario_normal, "asistente_chat", _respuesta_con_uso(20, 10, 30))

        self.client.force_login(self.usuario_staff)
        respuesta = self.client.get("/uso-gemini/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["totales"]["hoy"], 45)
        fila = respuesta.context["por_usuario"][0]
        self.assertEqual(fila["usuario__username"], "normal_user")
        self.assertEqual(fila["tokens"], 45)
        self.assertEqual(fila["llamadas"], 2)

    @override_settings(
        TRIBUTIA_GEMINI_RPD_LIMITE=20,
        TRIBUTIA_GEMINI_RPM_LIMITE=10,
        TRIBUTIA_GEMINI_TPM_LIMITE=250_000,
    )
    def test_limites_rpd_rpm_tpm_se_calculan_contra_la_configuracion(self):
        for _ in range(16):
            registrar_uso_gemini(self.usuario_normal, "analisis_documento", _respuesta_con_uso(100, 50, 150))

        self.client.force_login(self.usuario_staff)
        respuesta = self.client.get("/uso-gemini/")
        limites = respuesta.context["limites"]

        self.assertEqual(limites["rpd"]["usado"], 16)
        self.assertEqual(limites["rpd"]["limite"], 20)
        self.assertEqual(limites["rpd"]["pct"], 80)
        self.assertEqual(limites["rpm"]["usado"], 16)
        self.assertEqual(limites["tpm"]["usado"], 16 * 150)
        self.assertIn("reset_en", limites)
        self.assertIn("reset_local", limites)

    def test_pct_no_pasa_de_100_aunque_se_supere_el_limite(self):
        with override_settings(TRIBUTIA_GEMINI_RPD_LIMITE=1):
            registrar_uso_gemini(self.usuario_normal, "analisis_documento", _respuesta_con_uso())
            registrar_uso_gemini(self.usuario_normal, "analisis_documento", _respuesta_con_uso())

            self.client.force_login(self.usuario_staff)
            respuesta = self.client.get("/uso-gemini/")

            self.assertEqual(respuesta.context["limites"]["rpd"]["pct"], 100)
