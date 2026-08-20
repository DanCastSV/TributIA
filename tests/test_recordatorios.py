"""
Pruebas para el comando enviar_recordatorios_fiscales.

"Hoy" se congela a una fecha fija y lejos de cualquier fecha fiscal fija
(ISR el día 10, IVA el día 21) para que estas pruebas no dependan de en
qué día del mes real se ejecuten — de otro modo, correr la suite cerca
del día 10 o 21 hace que el comando mande un correo real por una fecha
fiscal fija aunque el usuario de prueba no tenga ningún evento propio,
y los asserts de "no debe enviar nada" fallan sin que el código esté roto.
"""

import datetime as _dt
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from core.models import EventoCalendario

HOY_FIJO = date(2026, 1, 15)


class _FechaFija(_dt.date):
    @classmethod
    def today(cls):
        return HOY_FIJO


class EnviarRecordatoriosFiscalesTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            username="recordatorio_user", password="clave12345", email="usuario@example.com",
        )
        self.enterContext(
            patch("core.management.commands.enviar_recordatorios_fiscales.date", _FechaFija)
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
            fecha=HOY_FIJO + timedelta(days=1),
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
            fecha=HOY_FIJO,
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
            fecha=HOY_FIJO + timedelta(days=30),
            tipo="recordatorio",
        )

        self._correr_comando(dias=3)

        self.assertEqual(len(mail.outbox), 0)
