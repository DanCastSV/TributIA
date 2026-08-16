"""
Generación del reporte anual en PDF (Centro de Análisis). Usa PyMuPDF
(fitz), que ya es dependencia del proyecto para OCR/extracción de texto
(core/ocr_utils.py, core/ia/extractor.py) y también sabe escribir PDFs,
así que no hace falta agregar reportlab/weasyprint solo para esto.
"""

import fitz

from core.datos_el_salvador import obtener_tasa_isr
from core.models import AnalisisDocumento

ANCHO_PAGINA = 595   # A4 en puntos
ALTO_PAGINA = 842
MARGEN = 50


def _nueva_pagina(doc):
    pagina = doc.new_page(width=ANCHO_PAGINA, height=ALTO_PAGINA)
    return pagina, MARGEN


def generar_reporte_anual_pdf(usuario, anio):
    """
    Arma el resumen anual de un usuario: total de documentos, total
    deducible, ahorro ISR estimado (usando el salario de su perfil si lo
    tiene) y el detalle de cada documento analizado en `anio`.

    Devuelve los bytes del PDF.
    """
    analisis = (
        AnalisisDocumento.objects
        .filter(documento__usuario=usuario, fecha_analisis__year=anio)
        .select_related('documento')
        .order_by('fecha_analisis')
    )

    total_documentos = analisis.count()
    total_deducible = sum(
        (a.total or 0) for a in analisis if a.es_deducible
    )

    perfil = getattr(usuario, 'perfiltributario', None)
    tasa_isr = 0
    ahorro_isr = 0
    if perfil and perfil.salario_mensual:
        salario_anual = float(perfil.salario_mensual) * 12
        tasa_isr = obtener_tasa_isr(salario_anual)
        ahorro_isr = float(total_deducible) * tasa_isr / 100

    doc = fitz.open()
    pagina, y = _nueva_pagina(doc)

    def escribir(texto, tamano=11, negrita=False, color=(0.1, 0.1, 0.1), salto=18):
        nonlocal pagina, y
        if y > ALTO_PAGINA - MARGEN:
            pagina, y = _nueva_pagina(doc)
        pagina.insert_text((MARGEN, y), texto, fontsize=tamano,
                            fontname="hebo" if negrita else "helv", color=color)
        y += salto

    escribir(f"TributIA — Reporte anual {anio}", tamano=18, negrita=True, salto=26)
    escribir(f"Usuario: {usuario.get_full_name() or usuario.username}", tamano=11)
    escribir(f"Correo: {usuario.email or 'No registrado'}", tamano=11, salto=26)

    escribir("Resumen", tamano=14, negrita=True, salto=20)
    escribir(f"Documentos analizados en {anio}: {total_documentos}")
    escribir(f"Total deducible: ${total_deducible:,.2f}")
    if perfil and perfil.salario_mensual:
        escribir(f"Tasa marginal ISR (según salario del perfil): {tasa_isr}%")
        escribir(f"Ahorro estimado de ISR: ${ahorro_isr:,.2f}", salto=26)
    else:
        escribir(
            "Ahorro ISR: agrega tu salario mensual en tu perfil para estimarlo.",
            salto=26,
        )

    escribir("Detalle de documentos", tamano=14, negrita=True, salto=20)
    if not analisis.exists():
        escribir("No hay documentos analizados en este año.")
    else:
        escribir("Empresa / Fecha / Tipo / Total / Deducible", tamano=9.5,
                  color=(0.4, 0.4, 0.4), salto=16)
        for a in analisis:
            deducible = "Sí" if a.es_deducible else "No" if a.es_deducible is False else "—"
            total_txt = f"${a.total:,.2f}" if a.total is not None else "—"
            linea = (
                f"{(a.nombre_empresa or a.documento.nombre)[:35]}  |  "
                f"{a.fecha_documento or a.fecha_analisis.strftime('%d/%m/%Y')}  |  "
                f"{(a.tipo_documento_detectado or '—')[:25]}  |  "
                f"{total_txt}  |  {deducible}"
            )
            escribir(linea, tamano=9.5, salto=15)

    return doc.tobytes()
