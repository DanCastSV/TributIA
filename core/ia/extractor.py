import fitz
import re


def extraer_texto_pdf(ruta_archivo):

    texto = ""

    pdf = fitz.open(ruta_archivo)

    for pagina in pdf:
        texto += pagina.get_text()

    pdf.close()

    return texto


def extraer_montos(texto):

    patron = r'\$?\s?\d+(?:,\d{3})*(?:\.\d{2})?'

    montos = re.findall(
        patron,
        texto
    )

    return list(set(montos))


def extraer_identificadores(texto):

    resultado = {
        "dui_o_nit_homologado": [],
        "nit_tradicional": []
    }

    homologados = re.findall(
        r'\d{8}-\d',
        texto
    )

    tradicionales = re.findall(
        r'\d{4}-\d{6}-\d{3}-\d',
        texto
    )

    resultado["dui_o_nit_homologado"] = homologados
    resultado["nit_tradicional"] = tradicionales

    return resultado


def extraer_resumen_fiscal(texto):

    resultado = {

        "subtotal": None,
        "iva": None,
        "total": None,
        "otros_cargos": None,

        "nrc": None,
        "telefono": None,
        "correo": None,
        "giro": None
    }

    patrones_subtotal = [
        r'SUBTOTAL[:\s\$]*([\d,]+\.\d{2})',
        r'Subtotal[:\s\$]*([\d,]+\.\d{2})'
    ]

    patrones_iva = [
        r'IVA[:\s\$]*([\d,]+\.\d{2})',
        r'IVA\s*13%[:\s\$]*([\d,]+\.\d{2})'
    ]

    patrones_total = [
        r'TOTAL[:\s\$]*([\d,]+\.\d{2})',
        r'Total[:\s\$]*([\d,]+\.\d{2})'
    ]

    patrones_cargos = [
        r'PROPINA[:\s\$]*([\d,]+\.\d{2})',
        r'SERVICIO[:\s\$]*([\d,]+\.\d{2})',
        r'CARGO[:\s\$]*([\d,]+\.\d{2})'
    ]

    for patron in patrones_subtotal:

        match = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if match:

            resultado["subtotal"] = match.group(1)
            break

    for patron in patrones_iva:

        match = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if match:

            resultado["iva"] = match.group(1)
            break

    for patron in patrones_total:

        match = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if match:

            resultado["total"] = match.group(1)
            break

    for patron in patrones_cargos:

        match = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if match:

            resultado["otros_cargos"] = match.group(1)
            break

    # NRC

    nrc = re.search(
        r'NRC[:\s]*(\d+)',
        texto,
        re.IGNORECASE
    )

    if nrc:
        resultado["nrc"] = nrc.group(1)

    # TELEFONO

    telefono = re.search(
        r'(\d{4}-\d{4})',
        texto
    )

    if telefono:
        resultado["telefono"] = telefono.group(1)

    # CORREO

    correo = re.search(
        r'[\w\.-]+@[\w\.-]+\.\w+',
        texto
    )

    if correo:
        resultado["correo"] = correo.group()

    # GIRO

    giro = re.search(
        r'GIRO[:\s]*(.+)',
        texto,
        re.IGNORECASE
    )

    if giro:
        resultado["giro"] = giro.group(1).strip()

    return resultado