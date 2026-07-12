from decimal import Decimal, InvalidOperation

from core.ocr_utils import extraer_texto_documento


class DocumentoNoTributarioError(Exception):
    """Se lanza cuando Gemini determina que el documento no es tributario."""
    pass

from core.ia.extractor import (
    extraer_montos,
    extraer_identificadores,
    extraer_resumen_fiscal
)

from core.ia.spacy_processor import (
    analizar_entidades
)

from core.ia.gemini_client import (
    analizar_documento_con_gemini
)

from core.models import AnalisisDocumento, EventoCalendario
from datetime import datetime as _dt


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


def analizar_documento(documento):

    print("PASO 1 - Extrayendo texto")

    texto = extraer_texto_documento(
        documento.archivo.path
    )

    print("PASO 2 - Extrayendo montos")

    montos = extraer_montos(texto)

    print("PASO 3 - Extrayendo identificadores")

    ids = extraer_identificadores(texto)

    print("PASO 4 - Resumen fiscal")

    resumen = extraer_resumen_fiscal(texto)

    print("PASO 5 - Procesamiento spaCy")

    entidades = analizar_entidades(texto)

    nit_detectado = (
        ids.get("nit_tradicional", [None])[0]
        if ids.get("nit_tradicional")
        else None
    )

    print("PASO 6 - Generando análisis con Gemini")

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

    es_tributario = analisis_gemini.get("es_documento_tributario")
    print(f"PASO 6b - Gemini resultado: es_documento_tributario={es_tributario!r}")

    # Rechazar ANTES de guardar si Gemini determina que no es tributario
    if es_tributario is False:
        if documento.archivo:
            try:
                documento.archivo.delete(save=False)
            except Exception:
                pass
        documento.delete()
        motivo = (
            analisis_gemini.get("justificacion_deducible")
            or analisis_gemini.get("recomendacion")
            or "El documento no corresponde a un documento tributario válido en El Salvador."
        )
        raise DocumentoNoTributarioError(motivo)

    print("PASO 7 - Guardando análisis")

    # Gemini como fuente principal de entidades; spaCy/regex como fallback
    def _primero(*valores):
        """Devuelve el primer valor no nulo y no vacío."""
        for v in valores:
            if v is not None and str(v).strip():
                return v
        return None

    # Confianza basada en campos clave que Gemini logró extraer
    _campos_clave = [
        analisis_gemini.get("empresa"),
        analisis_gemini.get("tipo_documento"),
        analisis_gemini.get("fecha"),
        analisis_gemini.get("total"),
    ]
    _campos_sec = [
        analisis_gemini.get("cliente"),
        analisis_gemini.get("numero_documento"),
        analisis_gemini.get("iva"),
        analisis_gemini.get("subtotal"),
        analisis_gemini.get("nit"),
    ]
    _ok_clave = sum(1 for v in _campos_clave if v is not None and str(v).strip())
    _ok_sec   = sum(1 for v in _campos_sec   if v is not None and str(v).strip())
    confianza = round((_ok_clave * 0.18 + _ok_sec * 0.056), 2)  # máx ≈ 1.0

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

    print("PASO 8 - Actualizando documento")

    documento.estado = "analizado"

    documento.save()

    print("PASO 9 - Finalizado")
