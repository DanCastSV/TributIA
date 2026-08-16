"""
Pruebas para el comando enviar_recordatorios_fiscales.
"""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from core.models import EventoCalendario


class EnviarRecordatoriosFiscalesTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            username="recordatorio_user", password="clave12345", email="usuario@example.com",
        )

    def _correr_comando(self, dias=3):
        salida = StringIO()
        call_command("enviar_recordatorios_fiscales", "--dias", str(dias), stdout=salida)
        return salida.getvalue()

    def test_no_envia_correo_si_no_hay_eventos_proximos(self):
        self._correr_comando(dias=3)
        self.assertEqual(len(mail.outbox), 0)

    def test_envia_correo_cuando_hay_evento_propio_en_la_ventana(self):
        EventoCalendario.objects.create(
            usuario=self.usuario,
            titulo="Vence factura proveedor",
            fecha=date.today() + timedelta(days=1),
            tipo="vencimiento",
        )

        self._correr_comando(dias=3)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["usuario@example.com"])
        self.assertIn("Vence factura proveedor", mail.outbox[0].body)

    def test_no_envia_correo_a_usuario_sin_email(self):
        User.objects.create_user(username="sin_email", password="clave12345", email="")
        EventoCalendario.objects.create(
            usuario=self.usuario,
            titulo="Evento propio",
            fecha=date.today(),
            tipo="recordatorio",
        )

        self._correr_comando(dias=3)

        destinatarios = [correo.to[0] for correo in mail.outbox]
        self.assertNotIn("", destinatarios)
        self.assertEqual(len(mail.outbox), 1)

    def test_evento_fuera_de_la_ventana_no_se_incluye(self):
        EventoCalendario.objects.create(
            usuario=self.usuario,
            titulo="Evento lejano",
            fecha=date.today() + timedelta(days=30),
            tipo="recordatorio",
        )

        self._correr_comando(dias=3)

        self.assertEqual(len(mail.outbox), 0)
