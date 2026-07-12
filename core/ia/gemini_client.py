import json
import logging

import google.generativeai as genai
from django.conf import settings

from core.datos_el_salvador import DATOS_EL_SALVADOR

logger = logging.getLogger(__name__)

genai.configure(
    api_key=settings.GEMINI_API_KEY
)

modelo = genai.GenerativeModel(
    "models/gemini-2.5-flash-lite"
)

MAX_CARACTERES_TEXTO = 8000


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
        respuesta = modelo.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )

        data = _extraer_json(respuesta.text)

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
        logger.error(f"Error en análisis IA con Gemini: {str(e)}")
        return _resultado_vacio(f"Error al generar análisis IA: {str(e)}")
