import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase, override_settings

from core.models import ConversacionAsistente, RateLimitBucket
from core.rate_limit import _ip_cliente


class RateLimitHotfixTests(TestCase):
    def setUp(self):
        self.client = Client(REMOTE_ADDR='203.0.113.10')

    def test_registro_bloquea_sexto_post_en_cinco_minutos(self):
        for _ in range(5):
            respuesta = self.client.post('/registro/', {})
            self.assertNotEqual(respuesta.status_code, 429)

        respuesta = self.client.post('/registro/', {})
        self.assertEqual(respuesta.status_code, 429)
        self.assertIn('Retry-After', respuesta)
        self.assertEqual(RateLimitBucket.objects.count(), 1)

    def test_xff_de_cliente_no_evade_limite_por_ip(self):
        for indice in range(5):
            respuesta = self.client.post(
                '/registro/', {}, HTTP_X_FORWARDED_FOR=f'198.51.100.{indice + 1}'
            )
            self.assertNotEqual(respuesta.status_code, 429)

        respuesta = self.client.post(
            '/registro/', {}, HTTP_X_FORWARDED_FOR='198.51.100.250'
        )
        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(RateLimitBucket.objects.count(), 1)

    @override_settings(TRIBUTIA_TRUSTED_PROXY_CIDRS=('127.0.0.0/8',))
    def test_proxy_confiable_usa_ultima_ip_valida_de_xff(self):
        request = RequestFactory().get(
            '/',
            REMOTE_ADDR='127.0.0.1',
            HTTP_X_FORWARDED_FOR='192.0.2.10, 198.51.100.20',
        )
        self.assertEqual(_ip_cliente(request), '198.51.100.20')

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
