"""
Utilidades para extracción de texto desde PDF e imágenes
"""

import glob
import io
import logging
import os
import shutil

import fitz
import pytesseract
from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Paquete de idioma español empaquetado con el proyecto (el Tesseract
# instalado en el sistema solo trae "eng" por defecto).
TESSDATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tessdata')

if os.path.isdir(TESSDATA_DIR):
    # pytesseract divide este config con shlex en modo no-POSIX en Windows,
    # que no quita comillas (quedarían como parte literal de la ruta), así
    # que va sin comillas. Asume que TESSDATA_DIR no contiene espacios.
    TESSERACT_CONFIG = f'--tessdata-dir {TESSDATA_DIR}'
else:
    TESSERACT_CONFIG = ''

# Un PDF con capa de texto digital extraído vía PyMuPDF normalmente trae
# bastante más que esto; por debajo de este umbral se asume que es un
# escaneo/imagen sin texto real y se cae al OCR.
MIN_CARACTERES_TEXTO_DIGITAL = 40


def _localizar_binario(nombre_exe, rutas_conocidas_glob):
    """Busca un ejecutable primero en PATH y, si no aparece (típico justo
    después de instalarlo, ya que procesos/terminales abiertos no recogen
    el PATH actualizado hasta reiniciarse), en rutas de instalación
    conocidas vía glob.
    """
    encontrado = shutil.which(nombre_exe)
    if encontrado:
        return encontrado

    for patron in rutas_conocidas_glob:
        coincidencias = glob.glob(patron)
        if coincidencias:
            return coincidencias[0]

    return None


_tesseract_cmd = _localizar_binario(
    'tesseract.exe' if os.name == 'nt' else 'tesseract',
    [r'C:\Program Files\Tesseract-OCR\tesseract.exe']
)

if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

_poppler_bin = None
_pdftoppm_cmd = _localizar_binario(
    'pdftoppm.exe' if os.name == 'nt' else 'pdftoppm',
    [
        os.path.expandvars(
            r'%LOCALAPPDATA%\Microsoft\WinGet\Packages\oschwartz10612.Poppler_*\poppler-*\Library\bin\pdftoppm.exe'
        )
    ]
)

if _pdftoppm_cmd:
    _poppler_bin = os.path.dirname(_pdftoppm_cmd)


def extraer_texto_pdf(ruta_pdf, dpi=300):
    """
    Extrae texto de un PDF usando OCR con Tesseract

    Args:
        ruta_pdf: Ruta al archivo PDF
        dpi: Resolución para convertir PDF a imagen (default: 300)

    Returns:
        Texto extraído del PDF
    """
    try:
        logger.info("procesando_pdf")
        total_paginas = int(
            pdfinfo_from_path(ruta_pdf, poppler_path=_poppler_bin).get('Pages', 0)
        )
        if not 1 <= total_paginas <= 20:
            raise ValueError("Cantidad de páginas no permitida")

        texto_completo = ""

        # Renderizar una sola página a la vez evita cargar el PDF completo en
        # memoria (20 páginas a 300 DPI pueden consumir cientos de MB).
        for numero_pagina in range(1, total_paginas + 1):
            imagenes = convert_from_path(
                ruta_pdf,
                dpi=dpi,
                poppler_path=_poppler_bin,
                first_page=numero_pagina,
                last_page=numero_pagina,
                thread_count=1,
            )
            if not imagenes:
                raise ValueError("No fue posible renderizar una página del PDF")
            imagen = imagenes[0]
            try:
                texto = pytesseract.image_to_string(
                    imagen,
                    lang='spa',
                    config=TESSERACT_CONFIG,
                )
                texto_completo += texto + "\n---PÁGINA {} FIN---\n".format(numero_pagina)
            finally:
                imagen.close()

        logger.info("extraccion_pdf_exitosa", extra={"paginas": total_paginas})
        return texto_completo.strip()

    except Exception as e:
        logger.error("extraccion_pdf_fallida", extra={"tipo_error": type(e).__name__})
        return None


def extraer_texto_imagen(ruta_imagen):
    """
    Extrae texto de una imagen usando OCR con Tesseract

    Args:
        ruta_imagen: Ruta al archivo de imagen

    Returns:
        Texto extraído de la imagen
    """
    try:
        logger.info("procesando_imagen")

        from PIL import ImageEnhance, ImageFilter

        imagen = Image.open(ruta_imagen).convert('RGB')

        # Escalar imágenes pequeñas: Tesseract funciona mejor a ~300 DPI.
        # Si el lado más corto tiene menos de 1000px, duplicamos el tamaño.
        ancho, alto = imagen.size
        if min(ancho, alto) < 1000:
            imagen = imagen.resize((ancho * 2, alto * 2), Image.LANCZOS)

        # Convertir a escala de grises para que el realce de contraste
        # sea más efectivo (no se "mezcla" entre canales de color).
        imagen_gris = imagen.convert('L')
        enhancer = ImageEnhance.Contrast(imagen_gris)
        imagen_gris = enhancer.enhance(1.8)

        # Ligero sharpening para bordes de letras más definidos.
        imagen_gris = imagen_gris.filter(ImageFilter.SHARPEN)

        imagen = imagen_gris.convert('RGB')

        texto = pytesseract.image_to_string(
            imagen, lang='spa',
            config=TESSERACT_CONFIG + ' --oem 1'
        )

        logger.info("✓ Extracción de imagen exitosa")
        return texto.strip()

    except Exception as e:
        logger.error("extraccion_imagen_fallida", extra={"tipo_error": type(e).__name__})
        return None


def extraer_texto_documento(ruta_archivo):
    """
    Extrae el texto de un documento (PDF o imagen) usando la fuente más
    confiable disponible: para PDFs intenta primero el texto digital
    embebido (rápido y exacto) y solo recurre a OCR si el PDF resulta
    ser un escaneo/imagen sin capa de texto real. Para imágenes va
    directo a OCR, ya que no existe texto embebido posible.

    Args:
        ruta_archivo: Ruta al archivo (PDF, PNG, JPG, JPEG)

    Returns:
        Texto extraído del documento

    Raises:
        ValueError: Si el formato no es soportado
    """
    extension = ruta_archivo.lower().split('.')[-1]

    if extension in ('png', 'jpg', 'jpeg'):
        return extraer_texto_imagen(ruta_archivo)

    if extension == 'pdf':
        from core.ia.extractor import extraer_texto_pdf as extraer_texto_pdf_digital

        texto_digital = extraer_texto_pdf_digital(ruta_archivo) or ''

        if len(texto_digital.strip()) >= MIN_CARACTERES_TEXTO_DIGITAL:
            logger.info("PDF con texto digital suficiente, se omite OCR")
            return texto_digital

        logger.info("PDF sin texto digital suficiente, usando OCR")
        return extraer_texto_pdf(ruta_archivo)

    raise ValueError(f"Formato no soportado: {extension}")


def procesar_documento(ruta_archivo):
    """
    Procesa cualquier documento (PDF o imagen) y extrae texto
    
    Args:
        ruta_archivo: Ruta al archivo (PDF, PNG, JPG, JPEG)
        
    Returns:
        Texto extraído del documento
        
    Raises:
        ValueError: Si el formato no es soportado
    """
    extension = ruta_archivo.lower().split('.')[-1]
    
    if extension == 'pdf':
        return extraer_texto_pdf(ruta_archivo)
    elif extension in ['png', 'jpg', 'jpeg']:
        return extraer_texto_imagen(ruta_archivo)
    else:
        raise ValueError(f"Formato no soportado: {extension}")


def validar_archivo(archivo):
    """
    Valida que el archivo sea un tipo soportado
    
    Args:
        archivo: Objeto File de Django
        
    Returns:
        Tupla (es_válido, mensaje)
    """
    extension = archivo.name.rsplit('.', 1)[-1].lower()
    extensiones_permitidas = ['pdf', 'png', 'jpg', 'jpeg']
    
    if extension not in extensiones_permitidas:
        return False, f"Extensión no permitida. Use: {', '.join(extensiones_permitidas)}"
    
    # Validar tamaño (máximo 20MB)
    tamaño_max = 20 * 1024 * 1024
    if archivo.size > tamaño_max:
        return False, f"Archivo demasiado grande. Máximo: 20MB"

    posicion_original = archivo.tell()
    try:
        archivo.seek(0)
        contenido = archivo.read()

        if not contenido:
            return False, "El archivo está vacío"

        if extension == 'pdf':
            if not contenido.startswith(b'%PDF-'):
                return False, "El contenido no corresponde a un PDF válido"

            documento = None
            try:
                documento = fitz.open(stream=contenido, filetype='pdf')
                if documento.is_encrypted:
                    return False, "Los PDF protegidos con contraseña no son compatibles"
                if documento.page_count < 1:
                    return False, "El PDF no contiene páginas"
                if documento.page_count > 20:
                    return False, "El PDF supera el máximo de 20 páginas"
            except Exception:
                return False, "El contenido no corresponde a un PDF válido"
            finally:
                if documento is not None:
                    documento.close()

        else:
            firma_correcta = (
                contenido.startswith(b'\x89PNG\r\n\x1a\n')
                if extension == 'png'
                else contenido.startswith(b'\xff\xd8\xff')
            )
            if not firma_correcta:
                return False, "El contenido no corresponde al tipo de imagen indicado"

            try:
                with Image.open(io.BytesIO(contenido)) as imagen:
                    formato_esperado = 'PNG' if extension == 'png' else 'JPEG'
                    if imagen.format != formato_esperado:
                        return False, "El contenido no corresponde al tipo de imagen indicado"
                    ancho, alto = imagen.size
                    if ancho <= 0 or alto <= 0 or ancho > 12000 or alto > 12000:
                        return False, "Las dimensiones de la imagen no son compatibles"
                    if ancho * alto > 25_000_000:
                        return False, "La imagen supera el máximo de 25 megapíxeles"
                    imagen.verify()
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
                return False, "El contenido no corresponde a una imagen válida"

        return True, "Archivo válido"
    finally:
        archivo.seek(posicion_original)
