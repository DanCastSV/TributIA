"""
Catálogo de formularios del Ministerio de Hacienda de El Salvador (usado
en la sección Recursos Fiscales), con las palabras clave por documento
requerido que alimentan el checklist: si alguna keyword aparece en el
tipo de documento detectado por Gemini o en el nombre que el usuario le
dio a un documento ya analizado, ese ítem se marca como cubierto.

Es una coincidencia aproximada por texto, no una verificación exhaustiva
(varios ítems, como "NIT del contribuyente", son datos y no un tipo de
documento identificable, así que quedan sin keywords a propósito y
siempre se muestran como pendientes de revisión manual).
"""

FORMULARIOS = [
    {
        'codigo': 'F-07',
        'nombre': 'Declaración y Pago del IVA',
        'periodicidad': 'Mensual',
        'descripcion': 'Declaración del Impuesto a la Transferencia de Bienes Muebles y Prestación de Servicios (IVA 13%). Debe presentarse dentro de los primeros 10 días hábiles del mes siguiente.',
        'documentos': [
            {'texto': 'Libro de compras IVA (comprobantes de crédito fiscal recibidos)', 'keywords': ['crédito fiscal', 'credito fiscal']},
            {'texto': 'Libro de ventas IVA (facturas y comprobantes emitidos)', 'keywords': ['factura']},
            {'texto': 'Comprobantes de retención del 1% recibidos', 'keywords': ['retención', 'retencion']},
            {'texto': 'NIT y NRC del contribuyente', 'keywords': []},
            {'texto': 'Estados de cuenta bancarios del período', 'keywords': ['estado de cuenta', 'bancario']},
        ],
        'icono': 'receipt',
        'url': 'https://www.mh.gob.sv/',
        'url_label': 'Ver en sitio del Ministerio de Hacienda',
    },
    {
        'codigo': 'F-11',
        'nombre': 'Declaración del Impuesto sobre la Renta',
        'periodicidad': 'Anual (120 días hábiles tras el cierre del ejercicio)',
        'descripcion': 'Declaración anual del ISR para personas naturales y jurídicas. El ejercicio fiscal cierra el 31 de diciembre. Se presenta generalmente en abril del año siguiente.',
        'documentos': [
            {'texto': 'Constancia de salario o ingresos del año (emitida por el empleador)', 'keywords': ['constancia salarial', 'constancia de salario', 'constancia de ingresos']},
            {'texto': 'Comprobantes de deducciones: gastos de salud, educación, intereses hipotecarios', 'keywords': ['salud', 'educación', 'educacion', 'hipotecario', 'hipotecaria']},
            {'texto': 'Certificados de retención de ISR recibidos', 'keywords': ['retención', 'retencion', 'isr']},
            {'texto': 'Información de cargas familiares (cónyuge, hijos)', 'keywords': []},
            {'texto': 'NIT del contribuyente y de dependientes', 'keywords': []},
            {'texto': 'Estados financieros (para empresas y profesionales independientes)', 'keywords': ['estado financiero', 'estados financieros']},
        ],
        'icono': 'file-check',
        'url': 'https://www.mh.gob.sv/',
        'url_label': 'Ver en sitio del Ministerio de Hacienda',
    },
    {
        'codigo': 'F-14',
        'nombre': 'Declaración del Pago a Cuenta e ISR Retenido',
        'periodicidad': 'Mensual',
        'descripcion': 'Pago mensual del 1.75% sobre ingresos brutos (pago a cuenta del ISR anual) y entero de las retenciones de ISR realizadas a empleados y terceros.',
        'documentos': [
            {'texto': 'Planilla de sueldos del mes con retenciones ISR calculadas', 'keywords': ['planilla', 'constancia salarial']},
            {'texto': 'Registros de ingresos brutos del mes', 'keywords': []},
            {'texto': 'Comprobantes de retenciones efectuadas a terceros', 'keywords': ['retención', 'retencion']},
            {'texto': 'NIT del agente de retención', 'keywords': []},
        ],
        'icono': 'dollar-sign',
        'url': 'https://www.mh.gob.sv/',
        'url_label': 'Ver en sitio del Ministerio de Hacienda',
    },
    {
        'codigo': 'F-910',
        'nombre': 'Informe Mensual de Retenciones, Percepciones y Anticipo a Cuenta del IVA',
        'periodicidad': 'Mensual',
        'descripcion': 'Informe de las retenciones del 1% de IVA efectuadas a proveedores, percepciones cobradas a clientes y anticipos a cuenta. Aplica a grandes contribuyentes y contribuyentes designados.',
        'documentos': [
            {'texto': 'Comprobantes de retención del 1% emitidos y recibidos', 'keywords': ['retención', 'retencion']},
            {'texto': 'Registro de compras a proveedores del período', 'keywords': ['factura', 'crédito fiscal', 'credito fiscal']},
            {'texto': 'NIT de los proveedores a quienes se retuvo', 'keywords': []},
            {'texto': 'Comprobantes de crédito fiscal del período', 'keywords': ['crédito fiscal', 'credito fiscal']},
        ],
        'icono': 'percent',
        'url': 'https://www.mh.gob.sv/',
        'url_label': 'Ver en sitio del Ministerio de Hacienda',
    },
    {
        'codigo': 'F-930',
        'nombre': 'Declaración de Renta para Personas Naturales Asalariadas',
        'periodicidad': 'Anual (simplificada)',
        'descripcion': 'Versión simplificada del F-11 para empleados en relación de dependencia que solo perciben salarios. Solo aplica si los ingresos superan $50,000 anuales o si se desean aplicar deducciones adicionales.',
        'documentos': [
            {'texto': 'Constancia de sueldo anual emitida por el patrono', 'keywords': ['constancia salarial', 'constancia de sueldo']},
            {'texto': 'DUI y NIT del empleado', 'keywords': []},
            {'texto': 'Comprobantes de deducciones adicionales (salud, educación, préstamos)', 'keywords': ['salud', 'educación', 'educacion', 'préstamo', 'prestamo']},
            {'texto': 'Datos de cargas familiares si aplica', 'keywords': []},
        ],
        'icono': 'user',
        'url': 'https://www.mh.gob.sv/',
        'url_label': 'Ver en sitio del Ministerio de Hacienda',
    },
    {
        'codigo': 'F-456',
        'nombre': 'Solicitud de Inscripción / Actualización en el Registro Tributario',
        'periodicidad': 'Una sola vez (o al actualizar datos)',
        'descripcion': 'Formulario para inscribirse como contribuyente, obtener el NIT, registrar o modificar actividad económica, y actualizar información en el Ministerio de Hacienda.',
        'documentos': [
            {'texto': 'DUI vigente del solicitante o representante legal', 'keywords': []},
            {'texto': 'NIT (si ya está inscrito y desea actualizar)', 'keywords': []},
            {'texto': 'Escritura de constitución (para personas jurídicas)', 'keywords': ['escritura de constitución', 'escritura de constitucion']},
            {'texto': 'Credencial del representante legal', 'keywords': ['credencial']},
            {'texto': 'Contrato de arrendamiento o título de propiedad del local (dirección fiscal)', 'keywords': ['contrato de arrendamiento', 'título de propiedad', 'titulo de propiedad']},
        ],
        'icono': 'landmark',
        'url': 'https://www.mh.gob.sv/',
        'url_label': 'Ver en sitio del Ministerio de Hacienda',
    },
]


def formularios_con_checklist(analisis_usuario):
    """
    Devuelve FORMULARIOS con cada documento marcado como `cubierto`
    (bool) según si alguna de sus keywords aparece en el tipo de
    documento detectado o en el nombre de algún AnalisisDocumento del
    usuario, más un contador `cubiertos`/`total` por formulario.
    """
    haystack = ' | '.join(
        f"{a.tipo_documento_detectado or ''} {a.documento.nombre}".lower()
        for a in analisis_usuario
    )

    resultado = []
    for formulario in FORMULARIOS:
        items = []
        cubiertos = 0
        for doc in formulario['documentos']:
            cubierto = bool(doc['keywords']) and any(kw in haystack for kw in doc['keywords'])
            if cubierto:
                cubiertos += 1
            items.append({'texto': doc['texto'], 'cubierto': cubierto})

        nuevo = dict(formulario)
        nuevo['documentos'] = items
        nuevo['cubiertos'] = cubiertos
        nuevo['total'] = len(items)
        resultado.append(nuevo)

    return resultado
