"""
Pruebas para la verificación de correo al registrarse (Fase 2):
registro (crea token + manda correo, revierte si el envío falla),
endpoint de verificación, y el gate de login. Todo con el backend de
correo en memoria de Django — nunca SMTP real.
"""

import importlib
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.email_verificacion import generar_token_verificacion, verificar_token
from core.models import EmailVerificationToken, PerfilTributario


class RegistroConVerificacionTests(TestCase):

    def setUp(self):
        self.client = Client()

    def _datos_registro(self, username="nuevo_user"):
        return {
            "username": username,
            "email": f"{username}@example.com",
            "password1": "ClaveSegura!123",
            "password2": "ClaveSegura!123",
        }

    def test_registro_exitoso_crea_token_y_manda_correo(self):
        respuesta = self.client.post("/registro/", self._datos_registro())

        self.assertEqual(respuesta.status_code, 302)
        usuario = User.objects.get(username="nuevo_user")
        self.assertTrue(EmailVerificationToken.objects.filter(usuario=usuario).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["nuevo_user@example.com"])
        self.assertIn("verificar-correo", mail.outbox[0].body)

    def test_registro_no_deja_sesion_iniciada(self):
        self.client.post("/registro/", self._datos_registro())
        respuesta = self.client.get("/dashboard/")
        self.assertEqual(respuesta.status_code, 302)  # redirige a login, no hay sesión

    @patch("core.views.enviar_correo_verificacion", return_value=False)
    def test_si_falla_el_envio_se_revierte_la_cuenta(self, _mock):
        self.client.post("/registro/", self._datos_registro())

        self.assertFalse(User.objects.filter(username="nuevo_user").exists())
        self.assertEqual(EmailVerificationToken.objects.count(), 0)


class VerificarCorreoTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            username="verificar_user", password="clave12345", email="verificar@example.com",
        )
        self.perfil = PerfilTributario.objects.create(usuario=self.usuario)
        self.client = Client()

    def test_token_valido_marca_verificado(self):
        token = generar_token_verificacion(self.usuario)

        respuesta = self.client.get(f"/verificar-correo/?token={token}")

        self.assertEqual(respuesta.status_code, 302)
        self.perfil.refresh_from_db()
        self.assertIsNotNone(self.perfil.email_verified_at)

    def test_token_invalido_no_verifica(self):
        respuesta = self.client.get("/verificar-correo/?token=no-existe")
        self.assertEqual(respuesta.status_code, 302)
        self.perfil.refresh_from_db()
        self.assertIsNone(self.perfil.email_verified_at)

    def test_token_ya_usado_no_verifica_dos_veces(self):
        token = generar_token_verificacion(self.usuario)
        ok_primera, _ = verificar_token(token)
        ok_segunda, _ = verificar_token(token)

        self.assertTrue(ok_primera)
        self.assertFalse(ok_segunda)

    def test_token_expirado_no_verifica(self):
        token = generar_token_verificacion(self.usuario)
        EmailVerificationToken.objects.filter(usuario=self.usuario).update(
            expires_at=timezone.now() - timedelta(hours=1)
        )

        ok, _ = verificar_token(token)
        self.assertFalse(ok)


@override_settings(EMAIL_VERIFICATION_REQUIRED=True)
class LoginGateTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            username="gate_user", password="ClaveSegura!123", email="gate@example.com",
        )
        self.perfil = PerfilTributario.objects.create(usuario=self.usuario)
        self.client = Client()

    def test_login_bloqueado_sin_verificar(self):
        respuesta = self.client.post("/login/", {
            "username": "gate_user", "password": "ClaveSegura!123",
        })
        self.assertEqual(respuesta.status_code, 200)  # se queda en el form con error
        self.assertFalse(respuesta.wsgi_request.user.is_authenticated)

    def test_login_permitido_si_ya_esta_verificado(self):
        self.perfil.email_verified_at = timezone.now()
        self.perfil.save()

        respuesta = self.client.post("/login/", {
            "username": "gate_user", "password": "ClaveSegura!123",
        })
        self.assertEqual(respuesta.status_code, 302)

    @override_settings(EMAIL_VERIFICATION_REQUIRED=False)
    def test_login_permitido_si_la_politica_esta_apagada(self):
        respuesta = self.client.post("/login/", {
            "username": "gate_user", "password": "ClaveSegura!123",
        })
        self.assertEqual(respuesta.status_code, 302)


class BackfillTests(TestCase):

    def test_backfill_marca_perfiles_existentes_como_verificados(self):
        from django.apps import apps as django_apps

        modulo = importlib.import_module("core.migrations.0019_backfill_email_verified_at")

        usuario = User.objects.create_user(username="legacy_user", password="clave12345")
        perfil = PerfilTributario.objects.create(usuario=usuario)
        self.assertIsNone(perfil.email_verified_at)

        modulo.backfill_verificados(django_apps, None)

        perfil.refresh_from_db()
        self.assertEqual(perfil.email_verified_at, usuario.date_joined)
