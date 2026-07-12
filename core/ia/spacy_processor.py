import spacy
import re

nlp = spacy.load(
    "es_core_news_sm"
)


def analizar_entidades(texto):

    doc = nlp(texto)

    resultado = {

        "personas": [],
        "organizaciones": [],
        "lugares": [],

        "nombre_empresa": None,
        "nombre_cliente": None,

        "fecha_documento": None,
        "numero_documento": None,
        "tipo_documento": None,
    }

    # =====================================
    # ENTIDADES DE SPACY
    # =====================================

    for ent in doc.ents:

        if ent.label_ == "PER":

            resultado["personas"].append(
                ent.text.strip()
            )

        elif ent.label_ == "ORG":

            resultado["organizaciones"].append(
                ent.text.strip()
            )

        elif ent.label_ in ["LOC", "GPE"]:

            resultado["lugares"].append(
                ent.text.strip()
            )

    # =====================================
    # EMPRESA
    # =====================================

    empresa = re.search(
        r'(?:EMPRESA|EMISOR|RAZON SOCIAL|RAZÓN SOCIAL)\s*[:\-]?\s*(.+)',
        texto,
        re.IGNORECASE
    )

    if empresa:

        resultado["nombre_empresa"] = (
            empresa.group(1).split("\n")[0].strip()
        )

    elif resultado["organizaciones"]:

        resultado["nombre_empresa"] = (
            resultado["organizaciones"][0]
        )

    # =====================================
    # CLIENTE
    # =====================================

    cliente = re.search(
        r'(?:CLIENTE|SEÑOR\(A\)|NOMBRE)\s*[:\-]?\s*(.+)',
        texto,
        re.IGNORECASE
    )

    if cliente:

        resultado["nombre_cliente"] = (
            cliente.group(1).split("\n")[0].strip()
        )

    elif resultado["personas"]:

        resultado["nombre_cliente"] = (
            resultado["personas"][0]
        )

    # =====================================
    # FECHA
    # =====================================

    fecha = re.search(
        r'\d{2}[\/\-]\d{2}[\/\-]\d{4}',
        texto
    )

    if fecha:

        resultado["fecha_documento"] = (
            fecha.group()
        )

    # =====================================
    # NUMERO DOCUMENTO
    # =====================================

    patrones_documento = [

        r'(?:FACTURA)\s*(?:N°|NO|NUMERO|#)?\s*([A-Z0-9\-]+)',

        r'(?:CCF)\s*(?:N°|NO|NUMERO|#)?\s*([A-Z0-9\-]+)',

        r'(?:DOCUMENTO)\s*(?:N°|NO|NUMERO|#)?\s*([A-Z0-9\-]+)',

        r'(?:COMPROBANTE)\s*(?:N°|NO|NUMERO|#)?\s*([A-Z0-9\-]+)',
    ]

    for patron in patrones_documento:

        numero = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if numero:

            resultado["numero_documento"] = (
                numero.group(1)
            )

            break

    # =====================================
    # TIPO DOCUMENTO
    # =====================================

    texto_upper = texto.upper()

    if "CRÉDITO FISCAL" in texto_upper:

        resultado["tipo_documento"] = (
            "Crédito Fiscal"
        )

    elif "CREDITO FISCAL" in texto_upper:

        resultado["tipo_documento"] = (
            "Crédito Fiscal"
        )

    elif "FACTURA" in texto_upper:

        resultado["tipo_documento"] = (
            "Factura"
        )

    elif "RETENCION" in texto_upper:

        resultado["tipo_documento"] = (
            "Comprobante de Retención"
        )

    elif "DECLARACION" in texto_upper:

        resultado["tipo_documento"] = (
            "Declaración"
        )

    elif "CONSTANCIA SALARIAL" in texto_upper:

        resultado["tipo_documento"] = (
            "Constancia Salarial"
        )

    # =====================================
    # DIRECCION
    # =====================================

    direccion = re.search(

        r'(?:DIRECCION|DIRECCIÓN)\s*[:\-]?\s*(.+)',

        texto,

        re.IGNORECASE
    )

    if direccion:

        resultado["lugares"].append(
            direccion.group(1).split("\n")[0]
        )

    return resultado