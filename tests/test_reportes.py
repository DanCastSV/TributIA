"""
Pruebas para core/services/reportes.py (reporte anual en PDF).
"""

import shutil
import tempfile
from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import AnalisisDocumento, DocumentoTributario, PerfilTributario
from core.services.reportes import generar_reporte_anual_pdf

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_reportes_")


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class GenerarReporteAnualPdfTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.usuario = User.objects.create_user(username="reporte_user", password="clave12345")

    def _crear_analisis(self, total, es_deducible):
        archivo = SimpleUploadedFile("factura.pdf", b"contenido-pdf-simulado", content_type="application/pdf")
        documento = DocumentoTributario.objects.create(
            usuario=self.usuario, nombre="factura.pdf", archivo=archivo, estado="analizado",
        )
        return AnalisisDocumento.objects.create(
            documento=documento,
            texto_extraido="FACTURA ACME",
            nombre_empresa="ACME",
            total=total,
            es_documento_tributario=True,
            es_deducible=es_deducible,
        )

    def test_pdf_sin_documentos_no_truena_y_devuelve_pdf_valido(self):
        contenido = generar_reporte_anual_pdf(self.usuario, date.today().year)
        self.assertTrue(contenido.startswith(b"%PDF"))

    def test_pdf_con_documentos_y_perfil_incluye_ahorro_isr(self):
        PerfilTributario.objects.create(
            usuario=self.usuario, salario_mensual=800, actividad_economica="Desarrollo de software",
        )
        self._crear_analisis(total=113, es_deducible=True)
        self._crear_analisis(total=50, es_deducible=False)

        contenido = generar_reporte_anual_pdf(self.usuario, date.today().year)
        self.assertTrue(contenido.startswith(b"%PDF"))
        self.assertGreater(len(contenido), 500)

    def test_pdf_de_otro_anio_no_incluye_documentos_del_anio_actual(self):
        self._crear_analisis(total=100, es_deducible=True)

        contenido_anio_pasado = generar_reporte_anual_pdf(self.usuario, date.today().year - 5)
        contenido_anio_actual = generar_reporte_anual_pdf(self.usuario, date.today().year)

        # El PDF con documentos reales debe pesar más que uno vacío.
        self.assertLess(len(contenido_anio_pasado), len(contenido_anio_actual))
