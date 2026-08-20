"""
Pruebas para el borrado de documentos: individual, seleccionados y todos.
"""

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from core.models import DocumentoTributario

MEDIA_ROOT_TEMPORAL = tempfile.mkdtemp(prefix="tributia_test_media_eliminar_")


@override_settings(MEDIA_ROOT=MEDIA_ROOT_TEMPORAL)
class EliminarDocumentosTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT_TEMPORAL, ignore_errors=True)

    def setUp(self):
        self.usuario = User.objects.create_user(username="eliminar_user", password="clave12345")
        self.otro_usuario = User.objects.create_user(username="otro_user", password="clave12345")
        self.client = Client()
        self.client.force_login(self.usuario)

    def _crear_documento(self, usuario, nombre="factura.pdf"):
        archivo = SimpleUploadedFile(nombre, b"contenido-pdf-simulado", content_type="application/pdf")
        return DocumentoTributario.objects.create(usuario=usuario, nombre=nombre, archivo=archivo)

    def test_eliminar_individual_borra_el_documento(self):
        doc = self._crear_documento(self.usuario)
        respuesta = self.client.post(f"/documento/{doc.id}/eliminar/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(DocumentoTributario.objects.filter(id=doc.id).exists())

    def test_eliminar_individual_no_borra_documento_ajeno(self):
        doc_ajeno = self._crear_documento(self.otro_usuario)
        respuesta = self.client.post(f"/documento/{doc_ajeno.id}/eliminar/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(DocumentoTributario.objects.filter(id=doc_ajeno.id).exists())

    def test_eliminar_seleccionados_borra_solo_los_marcados(self):
        doc1 = self._crear_documento(self.usuario, "a.pdf")
        doc2 = self._crear_documento(self.usuario, "b.pdf")
        doc3 = self._crear_documento(self.usuario, "c.pdf")

        respuesta = self.client.post(
            "/documentos/eliminar-seleccionados/",
            {"documento_ids": [doc1.id, doc2.id]},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(DocumentoTributario.objects.filter(id=doc1.id).exists())
        self.assertFalse(DocumentoTributario.objects.filter(id=doc2.id).exists())
        self.assertTrue(DocumentoTributario.objects.filter(id=doc3.id).exists())

    def test_eliminar_seleccionados_ignora_documentos_ajenos(self):
        doc_propio = self._crear_documento(self.usuario)
        doc_ajeno = self._crear_documento(self.otro_usuario)

        self.client.post(
            "/documentos/eliminar-seleccionados/",
            {"documento_ids": [doc_propio.id, doc_ajeno.id]},
        )

        self.assertFalse(DocumentoTributario.objects.filter(id=doc_propio.id).exists())
        self.assertTrue(DocumentoTributario.objects.filter(id=doc_ajeno.id).exists())

    def test_eliminar_seleccionados_sin_ids_no_truena(self):
        respuesta = self.client.post("/documentos/eliminar-seleccionados/", {})
        self.assertEqual(respuesta.status_code, 302)

    def test_eliminar_todos_borra_todos_los_del_usuario(self):
        self._crear_documento(self.usuario, "a.pdf")
        self._crear_documento(self.usuario, "b.pdf")
        doc_ajeno = self._crear_documento(self.otro_usuario)

        respuesta = self.client.post("/documentos/eliminar-todos/")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(DocumentoTributario.objects.filter(usuario=self.usuario).count(), 0)
        self.assertTrue(DocumentoTributario.objects.filter(id=doc_ajeno.id).exists())

    def test_eliminar_todos_sin_documentos_no_truena(self):
        respuesta = self.client.post("/documentos/eliminar-todos/")
        self.assertEqual(respuesta.status_code, 302)

    def test_requiere_metodo_post(self):
        doc = self._crear_documento(self.usuario)
        respuesta = self.client.get(f"/documento/{doc.id}/eliminar/")
        self.assertEqual(respuesta.status_code, 405)
