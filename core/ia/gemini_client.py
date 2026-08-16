import json
import logging

from django.conf import settings
from google import genai
from google.genai import types

from core.datos_el_salvador import DATOS_EL_SALVADOR

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash-lite"

cliente = genai.Client(
    api_key=settings.GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=30_000,
        retry_options=types.HttpRetryOptions(
            attempts=3,
            initial_delay=0.5,
            max_delay=4.0,
        ),
    ),
)

MAX_CARACTERES_TEXTO = 8000

_CAMPOS_TEXTO = {
    "empresa", "cliente", "tipo_documento", "fecha", "numero_documento",
    "nit", "direccion", "resumen", "justificacion_deducible", "recomendacion",
}
_CAMPOS_BOOLEANOS = {"es_documento_tributario", "es_deducible"}
_CAMPOS_NUMERICOS = {"subtotal", "iva", "total"}
_CAMPOS_RESPUESTA = _CAMPOS_TEXTO | _CAMPOS_BOOLEANOS | _CAMPOS_NUMERICOS


def _nullable(tipo, **restricciones):
    return {
        "anyOf": [
            {"type": tipo, **restricciones},
            {"type": "null"},
        ]
    }


RESPUESTA_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": sorted(_CAMPOS_RESPUESTA),
    "properties": {
        **{campo: _nullable("string") for campo in _CAMPOS_TEXTO},
        **{campo: _nullable("boolean") for campo in _CAMPOS_BOOLEANOS},
        **{
            campo: _nullable("number", minimum=0, maximum=1_000_000_000)
            for campo in _CAMPOS_NUMERICOS
        },
    },
}


def _validar_respuesta(data):
    """Valida tipos y límites antes de persistir una respuesta del modelo."""
    if not isinstance(data, dict):
        raise ValueError("La respuesta de Gemini no es un objeto")
    if set(data) != _CAMPOS_RESPUESTA:
        raise ValueError("La respuesta de Gemini no contiene el esquema esperado")

    for campo in _CAMPOS_TEXTO:
        valor = data[campo]
        limite = 4000 if campo == "recomendacion" else 2000 if campo in {
            "resumen", "justificacion_deducible"
        } else 500
        if valor is not None and (not isinstance(valor, str) or len(valor) > limite):
            raise ValueError(f"Campo de texto inválido: {campo}")

    for campo in _CAMPOS_BOOLEANOS:
        valor = data[campo]
        if valor is not None and not isinstance(valor, bool):
            raise ValueError(f"Campo booleano inválido: {campo}")

    for campo in _CAMPOS_NUMERICOS:
        valor = data[campo]
        if valor is not None and (
            isinstance(valor, bool)
            or not isinstance(valor, (int, float))
            or not 0 <= valor <= 1_000_000_000
        ):
            raise ValueError(f"Campo numérico inválido: {campo}")

    return data


def _reglas_deduccion_texto():
    deducciones = DATOS_EL_SALVADOR["deducciones"]
    familia = deducciones["familia"]
    hipotecarios = deducciones["prestamos"]["hipotecarios"]
    otros_prestamos = deducciones["prestamos"]["otros"]
    educacion = deducciones["educacion"]
    salud = deducciones["salud"]

    return (
        f"- Gastos de educación propios o de dependientes: deducibles hasta ${educacion['maximo']:,} anuales.\n"
        f"- Gastos de salud y medicina: deducibles hasta ${salud['maximo']:,} anuales.\n"
        f"- Intereses hipotecarios: {hipotecarios['tasa_deducible']}% del interés es deducible.\n"
        f"- Otros intereses: deducibles hasta ${otros_prestamos['maximo']:,}.\n"
        f"- Cargas familiares: ${familia['conyuge']:,} por cónyuge, ${familia['hijo']:,} por hijo "
        f"(máximo {familia['maximo_hijos']} hijos)."
    )


def _resultado_vacio(mensaje_error):
    return {
        "resumen": None,
        "es_documento_tributario": None,
        "es_deducible": None,
        "justificacion_deducible": None,
        "subtotal": None,
        "iva": None,
        "total": None,
        "recomendacion": mensaje_error,
        # Entidades
        "empresa": None,
        "cliente": None,
        "tipo_documento": None,
        "fecha": None,
        "numero_documento": None,
        "nit": None,
        "direccion": None,
    }


def _extraer_json(texto_respuesta):
    texto = texto_respuesta.strip()

    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.startswith("json"):
            texto = texto[4:]

    inicio = texto.find("{")
    fin = texto.rfind("}")

    if inicio == -1 or fin == -1:
        raise ValueError("La respuesta no contiene un objeto JSON")

    return json.loads(texto[inicio:fin + 1])


def analizar_documento_con_gemini(texto_ocr, datos_extraidos):
    """
    Analiza el texto real extraído de un documento (OCR o texto digital)
    junto con los datos preliminares detectados por regex/spaCy, y le pide
    a Gemini que valide/corrija esos datos y emita un juicio fundamentado
    sobre si el documento es tributario y si es deducible según las
    reglas fiscales de El Salvador.

    Devuelve un dict con: resumen, es_documento_tributario, es_deducible,
    justificacion_deducible, subtotal, iva, total, recomendacion.
    Si Gemini falla o responde algo no parseable, devuelve el mismo dict
    con los campos en None y "recomendacion" describiendo el error, sin
    levantar excepción (el análisis del documento debe poder continuar).
    """

    texto_truncado = (texto_ocr or "")[:MAX_CARACTERES_TEXTO]

    prompt = f"""
Eres TributIA, un asesor tributario experto en legislación fiscal de El Salvador.

Analiza el siguiente documento usando el TEXTO REAL extraído (puede tener errores menores de OCR) y los datos preliminares detectados automáticamente, que pueden estar incompletos o equivocados.

TEXTO EXTRAÍDO DEL DOCUMENTO
{texto_truncado}

DATOS PRELIMINARES DETECTADOS (verifícalos contra el texto real, corrígelos si es necesario)
Empresa: {datos_extraidos.get('empresa') or 'No detectada'}
Cliente: {datos_extraidos.get('cliente') or 'No detectado'}
Tipo de documento: {datos_extraidos.get('tipo_documento') or 'No identificado'}
Fecha: {datos_extraidos.get('fecha') or 'No detectada'}
NIT: {datos_extraidos.get('nit') or 'No detectado'}
Subtotal: {datos_extraidos.get('subtotal') or 'No detectado'}
IVA: {datos_extraidos.get('iva') or 'No detectado'}
Total: {datos_extraidos.get('total') or 'No detectado'}

REGLAS DE DEDUCCIONES FISCALES EN EL SALVADOR (úsalas para fundamentar tu juicio sobre deducibilidad)
{_reglas_deduccion_texto()}

INSTRUCCIONES

Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional antes ni después, sin bloques de código markdown, con exactamente estas claves:

{{
  "empresa": "Nombre real de la empresa emisora del documento según el texto, o null",
  "cliente": "Nombre real del cliente o receptor según el texto, o null",
  "tipo_documento": "Tipo exacto: Factura de Consumidor Final, Comprobante de Crédito Fiscal, Constancia Salarial, Declaración de Renta, Recibo, u otro tipo detectado, o null",
  "fecha": "Fecha del documento en formato DD/MM/YYYY según el texto, o null",
  "numero_documento": "Número o código del documento (correlativo, serie, folio), o null",
  "nit": "NIT del emisor detectado en el texto (formato XXXX-XXXXXX-XXX-X o similar), o null",
  "direccion": "Dirección física del emisor según el texto, o null",
  "resumen": "Descripción breve del documento en 2-3 frases",
  "es_documento_tributario": true o false,
  "es_deducible": true, false, o null si no se puede determinar,
  "justificacion_deducible": "Explicación breve de por qué es o no deducible, citando la regla aplicable si corresponde",
  "subtotal": número o null,
  "iva": número o null,
  "total": número o null,
  "recomendacion": "Recomendación profesional, riesgos y datos faltantes, máximo 200 palabras"
}}

Extrae los campos directamente del TEXTO REAL del documento. No uses los datos preliminares si contradicen lo que ves en el texto. No inventes información. Si el documento no es de naturaleza tributaria/fiscal salvadoreña, indica "es_documento_tributario": false.
"""

    try:
        respuesta = cliente.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=RESPUESTA_SCHEMA,
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )

        data = _validar_respuesta(_extraer_json(respuesta.text))

        return {
            # Entidades extraídas por Gemini (más precisas que spaCy)
            "empresa":          data.get("empresa"),
            "cliente":          data.get("cliente"),
            "tipo_documento":   data.get("tipo_documento"),
            "fecha":            data.get("fecha"),
            "numero_documento": data.get("numero_documento"),
            "nit":              data.get("nit"),
            "direccion":        data.get("direccion"),
            # Análisis tributario
            "resumen":                 data.get("resumen"),
            "es_documento_tributario": data.get("es_documento_tributario"),
            "es_deducible":            data.get("es_deducible"),
            "justificacion_deducible": data.get("justificacion_deducible"),
            "subtotal":                data.get("subtotal"),
            "iva":                     data.get("iva"),
            "total":                   data.get("total"),
            "recomendacion":           data.get("recomendacion"),
        }

    except Exception as e:
        logger.error(
            "gemini_analisis_fallido",
            extra={"tipo_error": type(e).__name__},
        )
        return _resultado_vacio(
            "El análisis con IA no está disponible temporalmente. Inténtalo de nuevo."
        )
