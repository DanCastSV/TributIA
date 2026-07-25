"""
Pruebas unitarias para core/ia/extractor.py: extracción por regex de
montos, identificadores (NIT/DUI) y datos fiscales (subtotal, IVA, total,
NRC, teléfono, correo, giro) desde el texto plano de un documento.
"""

import unittest

from core.ia.extractor import (
    extraer_identificadores,
    extraer_montos,
    extraer_resumen_fiscal,
)


class ExtraerMontosTests(unittest.TestCase):

    def test_encuentra_montos_con_decimales_y_separador_de_miles(self):
        texto = "Subtotal $1,234.56 IVA $160.49 Total $1,395.05"
        montos = extraer_montos(texto)

        self.assertIn("$1,234.56", montos)
        self.assertIn("$160.49", montos)
        self.assertIn("$1,395.05", montos)

    def test_texto_sin_montos_devuelve_lista_vacia(self):
        self.assertEqual(extraer_montos("Documento sin ningún número de dinero."), [])

    def test_no_duplica_montos_repetidos(self):
        texto = "Total: $50.00. Total confirmado: $50.00."
        montos = extraer_montos(texto)

        self.assertEqual(montos.count("$50.00"), 1)


class ExtraerIdentificadoresTests(unittest.TestCase):

    def test_detecta_nit_tradicional(self):
        resultado = extraer_identificadores("NIT: 0614-123456-102-1")
        self.assertIn("0614-123456-102-1", resultado["nit_tradicional"])

    def test_detecta_dui_o_nit_homologado(self):
        resultado = extraer_identificadores("DUI: 12345678-9")
        self.assertIn("12345678-9", resultado["dui_o_nit_homologado"])

    def test_texto_sin_identificadores_devuelve_listas_vacias(self):
        resultado = extraer_identificadores("Documento sin identificadores fiscales.")
        self.assertEqual(resultado["nit_tradicional"], [])
        self.assertEqual(resultado["dui_o_nit_homologado"], [])


class ExtraerResumenFiscalTests(unittest.TestCase):

    def test_extrae_subtotal_iva_y_total(self):
        texto = "SUBTOTAL: $100.00\nIVA: $13.00\nTOTAL: $113.00"
        resultado = extraer_resumen_fiscal(texto)

        self.assertEqual(resultado["subtotal"], "100.00")
        self.assertEqual(resultado["iva"], "13.00")
        self.assertEqual(resultado["total"], "113.00")

    def test_extrae_nrc_telefono_correo_y_giro(self):
        texto = (
            "NRC: 123456\n"
            "Tel: 2222-3333\n"
            "Correo: contacto@empresa.com\n"
            "GIRO: Venta de repuestos automotrices"
        )
        resultado = extraer_resumen_fiscal(texto)

        self.assertEqual(resultado["nrc"], "123456")
        self.assertEqual(resultado["telefono"], "2222-3333")
        self.assertEqual(resultado["correo"], "contacto@empresa.com")
        self.assertEqual(resultado["giro"], "Venta de repuestos automotrices")

    def test_campos_ausentes_quedan_en_none(self):
        resultado = extraer_resumen_fiscal("Texto sin ningún dato fiscal relevante.")

        for campo in ("subtotal", "iva", "total", "otros_cargos", "nrc", "telefono", "correo", "giro"):
            self.assertIsNone(resultado[campo])


if __name__ == "__main__":
    unittest.main()
