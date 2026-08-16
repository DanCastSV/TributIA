from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from core.services.asistente import responder_con_gemini


class AsistenteGeminiHotfixTests(SimpleTestCase):
    @patch('core.services.asistente._historial_gemini', return_value=[])
    @patch('core.services.asistente._contexto_documentos', return_value='Sin documentos')
    @patch('core.services.asistente._contexto_perfil', return_value='Perfil de prueba')
    @patch('core.services.asistente.cliente.models.generate_content')
    def test_usa_sdk_nuevo_con_timeout_global_y_limite_de_salida(
        self, generar, _perfil, _documentos, _historial
    ):
        generar.return_value = Mock(text='Respuesta breve')
        conversacion = Mock(usuario=Mock())

        respuesta = responder_con_gemini(conversacion, '¿Qué muestra mi documento?')

        self.assertEqual(respuesta, 'Respuesta breve')
        argumentos = generar.call_args.kwargs
        self.assertTrue(argumentos['contents'])
        self.assertLessEqual(argumentos['config'].max_output_tokens, 1024)
        self.assertIsNotNone(argumentos['config'].system_instruction)

    @patch('core.services.asistente._historial_gemini', return_value=[])
    @patch('core.services.asistente._contexto_documentos', return_value='Sin documentos')
    @patch('core.services.asistente._contexto_perfil', return_value='Perfil de prueba')
    @patch('core.services.asistente.cliente.models.generate_content')
    def test_error_no_filtra_detalle_interno(
        self, generar, _perfil, _documentos, _historial
    ):
        generar.side_effect = RuntimeError('api-key-super-secreta')
        conversacion = Mock(usuario=Mock())

        with self.assertLogs('core.services.asistente', level='ERROR') as logs:
            respuesta = responder_con_gemini(conversacion, 'hola')

        self.assertNotIn('api-key-super-secreta', respuesta)
        self.assertNotIn('api-key-super-secreta', ' '.join(logs.output))
