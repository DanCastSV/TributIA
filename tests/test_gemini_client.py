"""
Pruebas unitarias para el parseo de la respuesta de Gemini en
core/ia/gemini_client.py. No hacen ninguna llamada real a la API: solo
prueban la lógica pura de parseo de JSON y el resultado por defecto ante
errores.
"""

import unittest
from unittest.mock import Mock, patch

from core.ia.gemini_client import (
    _extraer_json,
    _resultado_vacio,
    _validar_respuesta,
    analizar_documento_con_gemini,
)


class ExtraerJsonTests(unittest.TestCase):

    def test_parsea_json_plano(self):
        texto = '{"empresa": "ACME", "es_documento_tributario": true}'
        data = _extraer_json(texto)

        self.assertEqual(data["empresa"], "ACME")
        self.assertTrue(data["es_documento_tributario"])

    def test_parsea_json_envuelto_en_bloque_markdown(self):
        texto = '```json\n{"empresa": "ACME", "total": 113.0}\n```'
        data = _extraer_json(texto)

        self.assertEqual(data["empresa"], "ACME")
        self.assertEqual(data["total"], 113.0)

    def test_parsea_json_con_bloque_markdown_sin_etiqueta_json(self):
        texto = '```\n{"empresa": "ACME"}\n```'
        data = _extraer_json(texto)

        self.assertEqual(data["empresa"], "ACME")

    def test_ignora_texto_extra_antes_y_despues_del_json(self):
        texto = 'Aquí está el resultado:\n{"empresa": "ACME"}\nEspero que ayude.'
        data = _extraer_json(texto)

        self.assertEqual(data["empresa"], "ACME")

    def test_respuesta_sin_json_lanza_value_error(self):
        with self.assertRaises(ValueError):
            _extraer_json("Esto no es un JSON válido.")


class ResultadoVacioTests(unittest.TestCase):

    def test_incluye_mensaje_de_error_en_recomendacion(self):
        resultado = _resultado_vacio("Gemini no respondió")
        self.assertEqual(resultado["recomendacion"], "Gemini no respondió")

    def test_todas_las_demas_claves_quedan_en_none(self):
        resultado = _resultado_vacio("error")

        claves_esperadas = {
            "resumen", "es_documento_tributario", "es_deducible",
            "justificacion_deducible", "subtotal", "iva", "total",
            "empresa", "cliente", "tipo_documento", "fecha",
            "numero_documento", "nit", "direccion",
        }
        for clave in claves_esperadas:
            self.assertIsNone(resultado[clave])


def _respuesta_valida():
    return {
        "empresa": "ACME",
        "cliente": None,
        "tipo_documento": "Factura",
        "fecha": "15/03/2026",
        "numero_documento": "F-001",
        "nit": None,
        "direccion": None,
        "resumen": "Factura de prueba.",
        "es_documento_tributario": True,
        "es_deducible": None,
        "justificacion_deducible": None,
        "subtotal": 100.0,
        "iva": 13.0,
        "total": 113.0,
        "recomendacion": "Revisar el documento.",
    }


class ValidacionRespuestaGeminiTests(unittest.TestCase):
    def test_acepta_respuesta_completa_con_tipos_validos(self):
        self.assertEqual(_validar_respuesta(_respuesta_valida()), _respuesta_valida())

    def test_rechaza_booleano_convertido_a_texto(self):
        respuesta = _respuesta_valida()
        respuesta["es_documento_tributario"] = "true"
        with self.assertRaises(ValueError):
            _validar_respuesta(respuesta)

    def test_rechaza_monto_negativo(self):
        respuesta = _respuesta_valida()
        respuesta["total"] = -1
        with self.assertRaises(ValueError):
            _validar_respuesta(respuesta)

    @patch("core.ia.gemini_client.cliente.models.generate_content")
    def test_envia_schema_json_y_limite_de_tokens(self, generar):
        generar.return_value = Mock(text=__import__('json').dumps(_respuesta_valida()))

        resultado = analizar_documento_con_gemini("FACTURA TOTAL 113", {})

        self.assertTrue(resultado["es_documento_tributario"])
        config = generar.call_args.kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertIsNotNone(config.response_json_schema)
        self.assertNotIn("maxLength", __import__('json').dumps(config.response_json_schema))
        self.assertLessEqual(config.max_output_tokens, 2048)

    @patch("core.ia.gemini_client.cliente.models.generate_content")
    def test_error_del_sdk_no_filtra_el_mensaje_interno(self, generar):
        generar.side_effect = RuntimeError("api-key-super-secreta")

        with self.assertLogs("core.ia.gemini_client", level="ERROR") as logs:
            resultado = analizar_documento_con_gemini("FACTURA", {})

        recomendacion = resultado["recomendacion"] or ""
        self.assertNotIn("api-key-super-secreta", recomendacion)
        self.assertIn("disponible", recomendacion.lower())
        self.assertNotIn("api-key-super-secreta", " ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
