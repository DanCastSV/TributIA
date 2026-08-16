import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from core.models import ConversacionAsistente

CACHE_PRUEBAS = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'tributia-hotfix-rate-tests',
    }
}


@override_settings(CACHES=CACHE_PRUEBAS)
class RateLimitHotfixTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(REMOTE_ADDR='203.0.113.10')

    def tearDown(self):
        cache.clear()

    def test_registro_bloquea_sexto_post_en_cinco_minutos(self):
        for _ in range(5):
            respuesta = self.client.post('/registro/', {})
            self.assertNotEqual(respuesta.status_code, 429)

        respuesta = self.client.post('/registro/', {})
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn('Retry-After', respuesta)

    def test_api_analisis_bloquea_septimo_post_por_usuario(self):
        usuario = User.objects.create_user(username='rate_user', password='StrongPass!123')
        self.client.force_login(usuario)

        for _ in range(6):
            respuesta = self.client.post('/api/v1/analizar-documento/', {})
            self.assertEqual(respuesta.status_code, 400)

        respuesta = self.client.post('/api/v1/analizar-documento/', {})
        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(respuesta.json()['error'], 'demasiadas_solicitudes')
        self.assertIn('Retry-After', respuesta)

    @patch('core.views.responder_con_gemini')
    def test_chat_rechaza_pregunta_excesiva_sin_llamar_a_gemini(self, responder):
        usuario = User.objects.create_user(username='chat_user', password='StrongPass!123')
        conversacion = ConversacionAsistente.objects.create(
            usuario=usuario,
            titulo='Prueba',
        )
        self.client.force_login(usuario)

        respuesta = self.client.post(
            '/api/chat/mensaje/',
            data=json.dumps({
                'pregunta': 'x' * 2001,
                'conversacion_id': conversacion.id,
            }),
            content_type='application/json',
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('larga', respuesta.json()['error'].lower())
        responder.assert_not_called()
