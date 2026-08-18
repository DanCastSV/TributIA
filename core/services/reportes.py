"""
Generación del reporte anual en PDF (Centro de Análisis). Usa PyMuPDF
(fitz), que ya es dependencia del proyecto para OCR/extracción de texto
(core/ocr_utils.py, core/ia/extractor.py) y también sabe escribir PDFs,
así que no hace falta agregar reportlab/weasyprint solo para esto.
"""

from collections import Counter

import fitz

from core.datos_el_salvador import obtener_tasa_isr
from core.models import AnalisisDocumento

ANCHO_PAGINA = 595   # A4 en puntos
ALTO_PAGINA = 842
MARGEN = 50

_MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]


def _nueva_pagina(doc):
    pagina = doc.new_page(width=ANCHO_PAGINA, height=ALTO_PAGINA)
    return pagina, MARGEN


def generar_reporte_anual_pdf(usuario, anio):
    """
    Arma el resumen anual de un usuario: resumen ejecutivo con la fórmula
    de ISR aplicada, desglose por tipo de documento, tendencia mensual,
    metodología/trazabilidad del análisis IA (modelo usado, confianza
    promedio y su distribución), y el detalle de cada documento
    analizado en `anio`.

    Devuelve los bytes del PDF.
    """
    analisis = list(
        AnalisisDocumento.objects
        .filter(documento__usuario=usuario, fecha_analisis__year=anio)
        .select_related('documento')
        .order_by('fecha_analisis')
    )

    total_documentos = len(analisis)
    total_deducible = sum((a.total or 0) for a in analisis if a.es_deducible)

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

    def titulo_seccion(texto):
        escribir(texto, tamano=14, negrita=True, salto=20)

    # ── Encabezado ──────────────────────────────────────────────
    escribir(f"TributIA — Reporte anual {anio}", tamano=18, negrita=True, salto=26)
    escribir(f"Usuario: {usuario.get_full_name() or usuario.username}", tamano=11)
    escribir(f"Correo: {usuario.email or 'No registrado'}", tamano=11, salto=26)

    # ── Resumen ejecutivo ───────────────────────────────────────
    titulo_seccion("Resumen ejecutivo")
    escribir(f"Documentos analizados en {anio}: {total_documentos}")
    escribir(f"Total deducible: ${total_deducible:,.2f}")
    if perfil and perfil.salario_mensual:
        escribir(
            f"Tramo aplicable: {tasa_isr}% (según salario mensual registrado en el perfil)"
        )
        escribir(
            f"Ahorro = ${total_deducible:,.2f} x {tasa_isr}% = ${ahorro_isr:,.2f}",
            salto=26,
        )
    else:
        escribir(
            "Ahorro ISR: agrega tu salario mensual en tu perfil para estimarlo.",
            salto=26,
        )

    # ── Desglose por tipo de documento ──────────────────────────
    titulo_seccion("Desglose por tipo de documento")
    if not analisis:
        escribir("Sin documentos este año.", salto=26)
    else:
        conteo_por_tipo = Counter(a.tipo_documento_detectado or 'Sin clasificar' for a in analisis)
        monto_por_tipo = Counter()
        for a in analisis:
            monto_por_tipo[a.tipo_documento_detectado or 'Sin clasificar'] += float(a.total or 0)

        for tipo, cantidad in conteo_por_tipo.most_common():
            escribir(
                f"{tipo}: {cantidad} documento{'s' if cantidad != 1 else ''} — ${monto_por_tipo[tipo]:,.2f}",
                tamano=10, salto=15,
            )
        y += 10

    # ── Tendencia mensual ────────────────────────────────────────
    titulo_seccion("Tendencia mensual")
    conteo_mensual = Counter(a.fecha_analisis.month for a in analisis)
    monto_mensual = Counter()
    for a in analisis:
        monto_mensual[a.fecha_analisis.month] += float(a.total or 0)

    if not analisis:
        escribir("Sin documentos este año.", salto=26)
    else:
        for mes in range(1, 13):
            if conteo_mensual[mes] == 0:
                continue
            escribir(
                f"{_MESES_ES[mes]}: {conteo_mensual[mes]} documento{'s' if conteo_mensual[mes] != 1 else ''} — ${monto_mensual[mes]:,.2f}",
                tamano=10, salto=15,
            )
        y += 10

    # ── Metodología y trazabilidad ───────────────────────────────
    titulo_seccion("Metodología y trazabilidad")
    escribir(
        "Pipeline de análisis: OCR (Tesseract/PyMuPDF) -> extracción por reglas y spaCy",
        tamano=10, salto=14,
    )
    escribir(
        "(fallback) -> Google Gemini (fuente principal de verdad para clasificación y montos).",
        tamano=10, salto=18,
    )

    if analisis:
        modelos_usados = sorted({a.modelo_ia for a in analisis if a.modelo_ia})
        escribir(
            f"Modelo(s) IA usado(s) en estos documentos: {', '.join(modelos_usados) if modelos_usados else 'no registrado'}",
            tamano=10, salto=15,
        )

        confianzas = [a.confianza_clasificacion for a in analisis]
        confianza_prom = sum(confianzas) / len(confianzas)
        altas = sum(1 for c in confianzas if c >= 0.7)
        medias = sum(1 for c in confianzas if 0.4 <= c < 0.7)
        bajas = sum(1 for c in confianzas if c < 0.4)

        escribir(f"Confianza de clasificación promedio: {confianza_prom * 100:.0f}%", tamano=10, salto=15)
        escribir(
            f"Distribución: Alta (>=70%) {altas} — Media (40-70%) {medias} — Baja (<40%) {bajas}",
            tamano=10, salto=26,
        )
    else:
        y += 26

    # ── Detalle de documentos ────────────────────────────────────
    titulo_seccion("Detalle de documentos")
    if not analisis:
        escribir("No hay documentos analizados en este año.")
    else:
        escribir("Empresa / Fecha / Tipo / Confianza / Total / Deducible", tamano=9.5,
                  color=(0.4, 0.4, 0.4), salto=16)
        for a in analisis:
            deducible = "Sí" if a.es_deducible else "No" if a.es_deducible is False else "—"
            total_txt = f"${a.total:,.2f}" if a.total is not None else "—"
            linea = (
                f"{(a.nombre_empresa or a.documento.nombre)[:30]}  |  "
                f"{a.fecha_documento or a.fecha_analisis.strftime('%d/%m/%Y')}  |  "
                f"{(a.tipo_documento_detectado or '—')[:22]}  |  "
                f"{a.confianza_clasificacion * 100:.0f}%  |  "
                f"{total_txt}  |  {deducible}"
            )
            escribir(linea, tamano=9.5, salto=15)

    return doc.tobytes()
