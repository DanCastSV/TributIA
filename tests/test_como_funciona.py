"""
Prueba para la vista /como-funciona/ (guía de onboarding).
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase


class ComoFuncionaTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username="guia_user", password="clave12345")
        self.client = Client()

    def test_requiere_login(self):
        respuesta = self.client.get("/como-funciona/")
        self.assertEqual(respuesta.status_code, 302)

    def test_usuario_logueado_ve_la_guia(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get("/como-funciona/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cómo funciona TributIA")
