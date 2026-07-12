"""
Utilidades para extracción de texto desde PDF e imágenes
"""

import glob
import shutil

import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import logging

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
        logger.info(f"Procesando PDF: {ruta_pdf}")
        imagenes = convert_from_path(ruta_pdf, dpi=dpi, poppler_path=_poppler_bin)
        texto_completo = ""

        for idx, imagen in enumerate(imagenes):
            logger.info(f"Extrayendo página {idx + 1}/{len(imagenes)}")
            texto = pytesseract.image_to_string(imagen, lang='spa', config=TESSERACT_CONFIG)
            texto_completo += texto + "\n---PÁGINA {} FIN---\n".format(idx + 1)

        logger.info("✓ Extracción de PDF exitosa")
        return texto_completo.strip()

    except Exception as e:
        logger.error(f"Error extrayendo PDF: {str(e)}")
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
        logger.info(f"Procesando imagen: {ruta_imagen}")

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
        logger.error(f"Error extrayendo imagen: {str(e)}")
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
    extension = archivo.name.split('.')[-1].lower()
    extensiones_permitidas = ['pdf', 'png', 'jpg', 'jpeg']
    
    if extension not in extensiones_permitidas:
        return False, f"Extensión no permitida. Use: {', '.join(extensiones_permitidas)}"
    
    # Validar tamaño (máximo 20MB)
    tamaño_max = 20 * 1024 * 1024
    if archivo.size > tamaño_max:
        return False, f"Archivo demasiado grande. Máximo: 20MB"
    
    return True, "Archivo válido"
