"""
Pruebas unitarias para el parseo de la respuesta de Gemini en
core/ia/gemini_client.py. No hacen ninguna llamada real a la API: solo
prueban la lógica pura de parseo de JSON y el resultado por defecto ante
errores.
"""

import unittest

from core.ia.gemini_client import _extraer_json, _resultado_vacio


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


if __name__ == "__main__":
    unittest.main()
