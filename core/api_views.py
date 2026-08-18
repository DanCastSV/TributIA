"""
API interna versionada (/api/v1/) que expone la capacidad de IA del proyecto
(OCR + spaCy + Gemini) a clientes externos (curl, Postman, Swagger, etc.),
reutilizando el mismo pipeline de core/services/analizador.py que usa la
vista web de subida de documentos.
"""

import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from core.analysis_capacity import CapacidadAnalisisAgotada, reservar_capacidad_analisis
from core.models import AnalisisDocumento, DocumentoTributario
from core.ocr_utils import _tesseract_cmd, validar_archivo
from core.rate_limit import limitar_solicitudes
from core.services.analizador import DocumentoNoTributarioError, analizar_documento

logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"


@require_http_methods(["GET"])
def health(request):
    """Verifica que el servicio y sus dependencias externas estén disponibles."""

    checks = {}

    try:
        connection.ensure_connection()
        checks["base_datos"] = "ok"
        db_ok = True
    except Exception as e:
        logger.error("health_db_fallido", extra={"tipo_error": type(e).__name__})
        checks["base_datos"] = "error"
        db_ok = False

    checks["tesseract"] = "ok" if _tesseract_cmd else "no_encontrado"
    checks["gemini_api_key"] = "configurada" if getattr(settings, "GEMINI_API_KEY", "") else "faltante"

    todo_ok = db_ok and bool(_tesseract_cmd) and checks["gemini_api_key"] == "configurada"

    return JsonResponse(
        {"status": "ok" if todo_ok else "degraded", "checks": checks},
        status=200 if todo_ok else 503,
    )


@require_http_methods(["GET"])
def metadata(request):
    """Describe el propósito, versión y tecnología del servicio de IA."""

    return JsonResponse({
        "nombre": "TributIA - Analizador de Documentos Tributarios",
        "version": API_VERSION,
        "descripcion": (
            "Analiza documentos tributarios (facturas, constancias, comprobantes) en "
            "PDF/PNG/JPG: extrae texto (OCR), identifica entidades y montos, clasifica "
            "si es tributario/deducible, y genera un resumen y una recomendación en "
            "lenguaje natural."
        ),
        "tecnologia": {
            "ocr": "Tesseract OCR (pytesseract) + PyMuPDF (texto embebido en PDF)",
            "nlp": "spaCy (es_core_news_sm)",
            "llm": "Google Gemini (gemini-2.5-flash)",
        },
        "endpoint_principal": {
            "ruta": "/api/v1/analizar-documento/",
            "metodo": "POST",
        },
        "formatos_soportados": ["pdf", "png", "jpg", "jpeg"],
        "tamano_maximo_mb": 20,
        "autenticacion": "Sesión de Django (login requerido)",
    })


@require_http_methods(["POST"])
@limitar_solicitudes(
    ambito='analizar-documento-api',
    limite=6,
    ventana_segundos=300,
    clave='usuario',
    json=True,
)
def analizar_documento_api(request):
    """
    Sube y analiza un documento tributario.

    Entrada (multipart/form-data):
        archivo (obligatorio): PDF, PNG, JPG o JPEG, máximo 20MB.
        nombre (opcional): nombre a mostrar; si se omite se usa el del archivo.

    Requiere sesión autenticada (login previo vía /login/) Y el token CSRF
    de esa sesión (ver docs/api.md) — se quitó @csrf_exempt (hallazgo V-01
    del informe de seguridad de 2026-08-15): al depender de la cookie de
    sesión para autenticar, este endpoint necesita la misma protección
    CSRF que cualquier otra vista autenticada por sesión, o cualquier sitio
    externo podría forzar al navegador de un usuario logueado a llamarlo.
    """

    if not request.user.is_authenticated:
        logger.warning("solicitud_rechazada", extra={"tipo_error": "no_autenticado"})
        return JsonResponse({
            "error": "no_autenticado",
            "detalle": "Debes iniciar sesión para usar este endpoint.",
        }, status=401)

    archivo = request.FILES.get("archivo")

    if not archivo:
        logger.warning("solicitud_rechazada", extra={"tipo_error": "archivo_faltante"})
        return JsonResponse({
            "error": "archivo_faltante",
            "detalle": 'Debes enviar un archivo en el campo "archivo" (multipart/form-data).',
        }, status=400)

    es_valido, mensaje = validar_archivo(archivo)
    if not es_valido:
        # No se loguea `mensaje` completo ni el nombre real del archivo:
        # podría contener datos que el usuario puso en el nombre del archivo.
        logger.warning("solicitud_rechazada", extra={"tipo_error": "archivo_invalido"})
        return JsonResponse({
            "error": "archivo_invalido",
            "detalle": mensaje,
        }, status=400)

    nombre = request.POST.get("nombre") or archivo.name

    try:
        with reservar_capacidad_analisis():
            doc = DocumentoTributario.objects.create(
                usuario=request.user,
                nombre=nombre,
                archivo=archivo,
            )

            try:
                analizar_documento(doc)
            except DocumentoNoTributarioError as e:
                return JsonResponse({
                    "error": "documento_no_tributario",
                    "detalle": str(e),
                }, status=422)
            except Exception as e:
                logger.exception("analisis_fallido_inesperado", extra={
                    "documento_id": doc.id,
                    "tipo_error": type(e).__name__,
                })
                doc.estado = "error"
                doc.save()
                return JsonResponse({
                    "error": "error_interno",
                    "detalle": "Ocurrió un error al procesar el documento. Inténtalo de nuevo.",
                }, status=500)
    except CapacidadAnalisisAgotada:
        logger.warning("solicitud_rechazada", extra={"tipo_error": "capacidad_agotada"})
        respuesta = JsonResponse({
            "error": "capacidad_temporal_agotada",
            "detalle": "Hay varios documentos en proceso. Inténtalo nuevamente en unos segundos.",
        }, status=429)
        respuesta["Retry-After"] = "15"
        return respuesta

    analisis = AnalisisDocumento.objects.get(documento=doc)

    def _f(valor):
        return float(valor) if valor is not None else None

    return JsonResponse({
        "documento_id": doc.id,
        "nombre": doc.nombre,
        "estado": doc.estado,
        "es_documento_tributario": analisis.es_documento_tributario,
        "es_deducible": analisis.es_deducible,
        "confianza_clasificacion": analisis.confianza_clasificacion,
        "tipo_documento_detectado": analisis.tipo_documento_detectado,
        "entidades": {
            "empresa": analisis.nombre_empresa,
            "cliente": analisis.nombre_cliente,
            "fecha_documento": analisis.fecha_documento,
            "numero_documento": analisis.numero_documento,
            "direccion": analisis.direccion_detectada,
            "nit_tradicional": analisis.nit_tradicional,
            "identificador_homologado": analisis.identificador_homologado,
            "nrc": analisis.nrc,
            "telefono": analisis.telefono,
            "correo": analisis.correo,
            "giro": analisis.giro,
        },
        "montos": {
            "subtotal": _f(analisis.subtotal),
            "iva": _f(analisis.iva),
            "otros_cargos": _f(analisis.otros_cargos),
            "total": _f(analisis.total),
        },
        "resumen_ia": analisis.resumen_ia,
        "recomendacion_ia": analisis.recomendacion_ia,
        "justificacion_deducible": analisis.justificacion_deducible,
    }, status=201)
