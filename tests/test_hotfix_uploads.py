import io
from unittest.mock import Mock, patch

import fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from core.forms import DocumentoForm
from core.ocr_utils import extraer_texto_pdf, validar_archivo


def _pdf_valido(paginas=1):
    documento = fitz.open()
    for _ in range(paginas):
        documento.new_page(width=595, height=842)
    contenido = documento.tobytes()
    documento.close()
    return contenido


def _png_valido(ancho=64, alto=64):
    salida = io.BytesIO()
    Image.new('RGB', (ancho, alto), 'white').save(salida, format='PNG')
    return salida.getvalue()


class ValidacionUploadHotfixTests(SimpleTestCase):
    def test_rechaza_pdf_falso_aunque_extension_sea_pdf(self):
        archivo = SimpleUploadedFile(
            'falso.pdf', b'ESTO NO ES UN PDF', content_type='application/pdf'
        )
        valido, mensaje = validar_archivo(archivo)
        self.assertFalse(valido)
        self.assertIn('contenido', mensaje.lower())

    def test_rechaza_extension_que_no_coincide_con_firma(self):
        archivo = SimpleUploadedFile(
            'imagen.pdf', _png_valido(), content_type='application/pdf'
        )
        valido, mensaje = validar_archivo(archivo)
        self.assertFalse(valido)
        self.assertIn('contenido', mensaje.lower())

    def test_acepta_pdf_real_y_rebobina_archivo(self):
        archivo = SimpleUploadedFile(
            'factura.pdf', _pdf_valido(), content_type='application/pdf'
        )
        valido, mensaje = validar_archivo(archivo)
        self.assertTrue(valido, mensaje)
        self.assertEqual(archivo.tell(), 0)

    def test_rechaza_pdf_con_demasiadas_paginas(self):
        archivo = SimpleUploadedFile(
            'demasiado.pdf', _pdf_valido(paginas=21), content_type='application/pdf'
        )
        valido, mensaje = validar_archivo(archivo)
        self.assertFalse(valido)
        self.assertIn('páginas', mensaje.lower())

    def test_acepta_png_real(self):
        archivo = SimpleUploadedFile(
            'factura.png', _png_valido(), content_type='image/png'
        )
        valido, mensaje = validar_archivo(archivo)
        self.assertTrue(valido, mensaje)
        self.assertEqual(archivo.tell(), 0)

    def test_formulario_web_rechaza_archivo_falso(self):
        archivo = SimpleUploadedFile(
            'falso.pdf', b'NO ES PDF', content_type='application/pdf'
        )
        formulario = DocumentoForm(
            data={'nombre': 'Factura falsa'}, files={'archivo': archivo}
        )
        self.assertFalse(formulario.is_valid())
        self.assertIn('contenido', str(formulario.errors['archivo']).lower())


class OcrPdfAcotadoTests(SimpleTestCase):
    @patch('core.ocr_utils.pytesseract.image_to_string', return_value='texto')
    @patch('core.ocr_utils.convert_from_path')
    @patch('core.ocr_utils.pdfinfo_from_path', return_value={'Pages': 3})
    def test_convierte_una_pagina_por_vez_para_acotar_memoria(
        self, _info, convertir, _ocr
    ):
        convertir.side_effect = [[Mock()], [Mock()], [Mock()]]

        texto = extraer_texto_pdf('/tmp/prueba.pdf', dpi=150)

        self.assertIn('texto', texto)
        self.assertEqual(convertir.call_count, 3)
        self.assertEqual(
            [c.kwargs['first_page'] for c in convertir.call_args_list],
            [1, 2, 3],
        )
        self.assertEqual(
            [c.kwargs['last_page'] for c in convertir.call_args_list],
            [1, 2, 3],
        )
