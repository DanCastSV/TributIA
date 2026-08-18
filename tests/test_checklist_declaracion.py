"""
Pruebas para el checklist de documentos por formulario
(core/formularios_fiscales.py y la vista recursos_fiscales).
"""

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from core.formularios_fiscales import formularios_con_checklist
from core.models import AnalisisDocumento, DocumentoTributario

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_checklist_")


class FormulariosConChecklistUnitTests(TestCase):
    """Prueba formularios_con_checklist() directo, sin BD ni HTTP."""

    def test_sin_analisis_todo_queda_pendiente(self):
        formularios = formularios_con_checklist([])
        for formulario in formularios:
            self.assertEqual(formulario['cubiertos'], 0)
            self.assertTrue(all(not d['cubierto'] for d in formulario['documentos']))

    def test_analisis_con_tipo_detectado_cubre_el_item_correspondiente(self):
        class _AnalisisFalso:
            tipo_documento_detectado = "Constancia Salarial"

            class documento:
                nombre = "constancia.pdf"

        formularios = formularios_con_checklist([_AnalisisFalso()])
        f11 = next(f for f in formularios if f['codigo'] == 'F-11')

        item_constancia = f11['documentos'][0]
        self.assertTrue(item_constancia['cubierto'])
        self.assertGreaterEqual(f11['cubiertos'], 1)


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class RecursosFiscalesVistaTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.usuario = User.objects.create_user(username="checklist_user", password="clave12345")
        self.client = Client()
        self.client.force_login(self.usuario)

    def test_vista_responde_200_y_trae_formularios_con_checklist(self):
        respuesta = self.client.get("/recursos-fiscales/")
        self.assertEqual(respuesta.status_code, 200)
        formularios = respuesta.context["formularios"]
        self.assertTrue(all("cubiertos" in f and "total" in f for f in formularios))

    def test_documento_del_usuario_sube_el_contador_de_cubiertos(self):
        archivo = SimpleUploadedFile("factura.pdf", b"contenido-pdf-simulado", content_type="application/pdf")
        documento = DocumentoTributario.objects.create(
            usuario=self.usuario, nombre="factura.pdf", archivo=archivo, estado="analizado",
        )
        AnalisisDocumento.objects.create(
            documento=documento, texto_extraido="txt", tipo_documento_detectado="Factura de Consumidor Final",
        )

        respuesta = self.client.get("/recursos-fiscales/")
        formularios = respuesta.context["formularios"]
        f07 = next(f for f in formularios if f['codigo'] == 'F-07')
        self.assertGreaterEqual(f07['cubiertos'], 1)
