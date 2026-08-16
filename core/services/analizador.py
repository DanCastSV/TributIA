import logging
import time
from decimal import Decimal, InvalidOperation

from core.ocr_utils import extraer_texto_documento

logger = logging.getLogger("core.services.analizador")


class DocumentoNoTributarioError(Exception):
    """Se lanza cuando Gemini determina que el documento no es tributario."""
    pass

from datetime import datetime as _dt

from core.ia.extractor import (
    extraer_identificadores,
    extraer_montos,
    extraer_resumen_fiscal,
)
from core.ia.gemini_client import (
    MODEL_NAME,
    analizar_documento_con_gemini,
)
from core.ia.spacy_processor import analizar_entidades
from core.models import AnalisisDocumento, EventoCalendario


def _duracion_ms(inicio):
    return round((time.monotonic() - inicio) * 1000, 1)


def _parsear_fecha(texto):
    """Intenta convertir un string de fecha a date. Devuelve None si falla."""
    if not texto:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%Y/%m/%d', '%m/%d/%Y'):
        try:
            return _dt.strptime(str(texto).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _a_decimal(valor):
    if valor is None:
        return None

    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def calcular_confianza(analisis_gemini):
    """
    Calcula confianza_clasificacion (0.0-1.0) según cuántos de los campos
    clave/secundarios logró extraer Gemini. Campos clave pesan más porque
    son los que más impactan la utilidad del análisis para el usuario.
    """

    campos_clave = [
        analisis_gemini.get("empresa"),
        analisis_gemini.get("tipo_documento"),
        analisis_gemini.get("fecha"),
        analisis_gemini.get("total"),
    ]
    campos_sec = [
        analisis_gemini.get("cliente"),
        analisis_gemini.get("numero_documento"),
        analisis_gemini.get("iva"),
        analisis_gemini.get("subtotal"),
        analisis_gemini.get("nit"),
    ]

    ok_clave = sum(1 for v in campos_clave if v is not None and str(v).strip())
    ok_sec = sum(1 for v in campos_sec if v is not None and str(v).strip())

    return round((ok_clave * 0.18 + ok_sec * 0.056), 2)  # máx ≈ 1.0


def analizar_documento(documento):

    documento_id = documento.id
    inicio_total = time.monotonic()
    logger.info("analisis_iniciado", extra={"documento_id": documento_id})

    inicio = time.monotonic()
    texto = extraer_texto_documento(
        documento.archivo.path
    )
    logger.info("etapa_completada", extra={
        "documento_id": documento_id,
        "etapa": "extraccion_texto",
        "duracion_ms": _duracion_ms(inicio),
        "caracteres_extraidos": len(texto or ""),
    })

    montos = extraer_montos(texto)

    ids = extraer_identificadores(texto)

    resumen = extraer_resumen_fiscal(texto)

    inicio = time.monotonic()
    entidades = analizar_entidades(texto)
    logger.info("etapa_completada", extra={
        "documento_id": documento_id,
        "etapa": "spacy",
        "duracion_ms": _duracion_ms(inicio),
    })

    nit_detectado = (
        ids.get("nit_tradicional", [None])[0]
        if ids.get("nit_tradicional")
        else None
    )

    inicio = time.monotonic()
    analisis_gemini = analizar_documento_con_gemini(
        texto,
        {
            "empresa": entidades.get("nombre_empresa"),
            "cliente": entidades.get("nombre_cliente"),
            "tipo_documento": entidades.get("tipo_documento"),
            "fecha": entidades.get("fecha_documento"),
            "nit": nit_detectado,
            "subtotal": resumen.get("subtotal"),
            "iva": resumen.get("iva"),
            "total": resumen.get("total"),
        }
    )
    logger.info("etapa_completada", extra={
        "documento_id": documento_id,
        "etapa": "gemini",
        "modelo": MODEL_NAME,
        "duracion_ms": _duracion_ms(inicio),
    })

    es_tributario = analisis_gemini.get("es_documento_tributario")

    # Rechazar ANTES de guardar si Gemini determina que no es tributario
    if es_tributario is False:
        if documento.archivo:
            try:
                documento.archivo.delete(save=False)
            except Exception as e:
                logger.warning(
                    "eliminacion_archivo_rechazado_fallida",
                    extra={"documento_id": documento_id, "tipo_error": type(e).__name__},
                )
        documento.delete()
        motivo = (
            analisis_gemini.get("justificacion_deducible")
            or analisis_gemini.get("recomendacion")
            or "El documento no corresponde a un documento tributario válido en El Salvador."
        )
        logger.warning("analisis_rechazado", extra={
            "tipo_error": "documento_no_tributario",
            "duracion_total_ms": _duracion_ms(inicio_total),
        })
        raise DocumentoNoTributarioError(motivo)

    # Gemini como fuente principal de entidades; spaCy/regex como fallback
    def _primero(*valores):
        """Devuelve el primer valor no nulo y no vacío."""
        for v in valores:
            if v is not None and str(v).strip():
                return v
        return None

    # Confianza basada en campos clave que Gemini logró extraer
    confianza = calcular_confianza(analisis_gemini)

    AnalisisDocumento.objects.create(

        documento=documento,

        texto_extraido=texto,

        # IDENTIFICADORES — Gemini primero, regex como fallback
        nit_tradicional=_primero(
            analisis_gemini.get("nit"),
            nit_detectado,
        ),

        identificador_homologado=(
            ids.get("dui_o_nit_homologado", [None])[0]
            if ids.get("dui_o_nit_homologado")
            else None
        ),

        # ENTIDADES — Gemini primero (más preciso), spaCy como fallback
        nombre_empresa=_primero(
            analisis_gemini.get("empresa"),
            entidades.get("nombre_empresa"),
        ),

        nombre_cliente=_primero(
            analisis_gemini.get("cliente"),
            entidades.get("nombre_cliente"),
        ),

        fecha_documento=_primero(
            analisis_gemini.get("fecha"),
            entidades.get("fecha_documento"),
        ),

        numero_documento=_primero(
            analisis_gemini.get("numero_documento"),
            entidades.get("numero_documento"),
        ),

        direccion_detectada=_primero(
            analisis_gemini.get("direccion"),
            entidades["lugares"][0] if entidades.get("lugares") else None,
        ),

        tipo_documento_detectado=_primero(
            analisis_gemini.get("tipo_documento"),
            entidades.get("tipo_documento"),
        ),

        # MONTOS

        montos_detectados=", ".join(montos),

        subtotal=(
            _a_decimal(analisis_gemini.get("subtotal"))
            or _a_decimal(resumen.get("subtotal"))
        ),

        iva=(
            _a_decimal(analisis_gemini.get("iva"))
            or _a_decimal(resumen.get("iva"))
        ),

        total=(
            _a_decimal(analisis_gemini.get("total"))
            or _a_decimal(resumen.get("total"))
        ),

        otros_cargos=_a_decimal(resumen.get("otros_cargos")),

        nrc=resumen.get(
            "nrc"
        ),

        telefono=resumen.get(
            "telefono"
        ),

        correo=resumen.get(
            "correo"
        ),

        giro=resumen.get(
            "giro"
        ),

        # IA

        resumen_ia=analisis_gemini.get("resumen"),

        recomendacion_ia=analisis_gemini.get("recomendacion"),

        es_documento_tributario=analisis_gemini.get("es_documento_tributario"),

        es_deducible=analisis_gemini.get("es_deducible"),

        justificacion_deducible=analisis_gemini.get("justificacion_deducible"),

        confianza_clasificacion=confianza,

    )

    # Auto-crear evento en el calendario si el documento tiene fecha detectada
    fecha_doc = _parsear_fecha(
        _primero(analisis_gemini.get("fecha"), entidades.get("fecha_documento"))
    )
    if fecha_doc:
        tipo_doc = _primero(
            analisis_gemini.get("tipo_documento"),
            entidades.get("tipo_documento"),
            "Documento",
        )
        EventoCalendario.objects.get_or_create(
            usuario=documento.usuario,
            fecha=fecha_doc,
            titulo=f"{tipo_doc}: {documento.nombre}",
            defaults={
                'tipo': 'factura',
                'descripcion': f'Fecha detectada automáticamente del documento "{documento.nombre}".',
            }
        )

    documento.estado = "analizado"

    documento.save()

    logger.info("analisis_completado", extra={
        "documento_id": documento_id,
        "duracion_total_ms": _duracion_ms(inicio_total),
        "confianza_clasificacion": confianza,
    })
