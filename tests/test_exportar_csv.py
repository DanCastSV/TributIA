"""
Pruebas para /centro-analisis/exportar/ (exportar análisis a CSV).
"""

import csv
import io
import shutil
import tempfile
from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from core.models import AnalisisDocumento, DocumentoTributario

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_csv_")


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class ExportarCsvTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.usuario = User.objects.create_user(username="csv_user", password="clave12345")
        self.client = Client()
        self.client.force_login(self.usuario)

        archivo = SimpleUploadedFile("factura.pdf", b"contenido-pdf-simulado", content_type="application/pdf")
        documento = DocumentoTributario.objects.create(
            usuario=self.usuario, nombre="factura.pdf", archivo=archivo, estado="analizado",
        )
        AnalisisDocumento.objects.create(
            documento=documento,
            texto_extraido="FACTURA ACME",
            nombre_empresa="ACME",
            nit_tradicional="0614-123456-123-4",
            nrc="123456",
            total=113,
            iva=13,
            subtotal=100,
            es_documento_tributario=True,
            es_deducible=True,
            confianza_clasificacion=0.94,
            modelo_ia="gemini-2.5-flash",
        )

    def test_csv_trae_content_type_correcto(self):
        respuesta = self.client.get(f"/centro-analisis/exportar/?anio={date.today().year}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("text/csv", respuesta["Content-Type"])

    def test_csv_incluye_la_fila_del_documento(self):
        respuesta = self.client.get(f"/centro-analisis/exportar/?anio={date.today().year}")
        filas = list(csv.reader(io.StringIO(respuesta.content.decode("utf-8"))))

        encabezado = filas[0]
        self.assertEqual(encabezado[1], "Empresa")
        self.assertEqual(len(filas), 2)

        fila = filas[1]
        self.assertEqual(fila[encabezado.index("Empresa")], "ACME")
        self.assertEqual(fila[encabezado.index("NIT tradicional")], "0614-123456-123-4")
        self.assertEqual(fila[encabezado.index("NRC")], "123456")
        self.assertEqual(fila[encabezado.index("Tributario")], "Sí")
        self.assertEqual(fila[encabezado.index("Deducible")], "Sí")
        self.assertEqual(fila[encabezado.index("Confianza clasificación")], "0.94")
        self.assertEqual(fila[encabezado.index("Modelo IA")], "gemini-2.5-flash")

    def test_csv_de_anio_sin_documentos_solo_trae_encabezado(self):
        respuesta = self.client.get("/centro-analisis/exportar/?anio=2000")
        filas = list(csv.reader(io.StringIO(respuesta.content.decode("utf-8"))))
        self.assertEqual(len(filas), 1)
