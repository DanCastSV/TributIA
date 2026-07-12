"""
Datos tributarios específicos de El Salvador
"""

DATOS_EL_SALVADOR = {
    "pais": "El Salvador",
    "tipo_contribuyente": ["Empleado", "Freelance", "Empresa"],
    
    # Impuestos
    "impuestos": {
        "iva": {
            "tasa": 13,  # porcentaje
            "descripcion": "Impuesto al Valor Agregado",
            "aplicable_a": ["Bienes", "Servicios"],
        },
        "isr": {
            "tasa_min": 5,
            "tasa_max": 30,
            "descripcion": "Impuesto sobre la Renta",
            "tabla_tarifa": [
                {"rango": "0 - 50000", "tasa": 0, "nota": "Exento"},
                {"rango": "50001 - 156000", "tasa": "5%"},
                {"rango": "156001 - 300000", "tasa": "10%"},
                {"rango": "300001+", "tasa": "30%"},
            ]
        },
        "cotizaciones_afiliacion": {
            "empleado": 7.5,  # Porcentaje del salario
            "empleador": 8.75,
            "descripcion": "Cotizaciones al ISSS (Seguro Social)",
        },
        "cuota_afp": {
            "empleado": 10.25,
            "empleador": 8.75,
            "descripcion": "Administradora de Fondos de Pensiones",
        }
    },
    
    # Deducciones permitidas
    "deducciones": {
        "familia": {
            "conyuge": 29000,  # Cantidad deducible
            "hijo": 19000,
            "maximo_hijos": 4,
            "descripcion": "Deducción por cargas familiares",
        },
        "prestamos": {
            "hipotecarios": {
                "tasa_deducible": 30,  # % del interes
                "descripcion": "Intereses hipotecarios deducibles",
            },
            "otros": {
                "maximo": 10000,
                "descripcion": "Otros intereses deducibles",
            }
        },
        "educacion": {
            "maximo": 15000,
            "descripcion": "Gastos de educación propios o dependientes",
        },
        "salud": {
            "maximo": 10000,
            "descripcion": "Gastos de salud y medicina",
        }
    },
    
    # Límites y bases
    "limites": {
        "salario_exento": 156000,  # Salario exento de ISR
        "utilidad_minima": 30000,
        "utilidad_exenta": 15000,
    },
    
    # Tipos de documentos tributarios
    "tipos_documentos": {
        "constancia_salarial": {
            "descripcion": "Constancia de Salario",
            "entidad_emisora": "Empleador",
            "frecuencia": "Anual",
            "uso": "Declaración de renta",
        },
        "declaracion_renta": {
            "descripcion": "Declaración Jurada de Renta",
            "plazo": "Hasta 120 días después del cierre fiscal",
            "entidad": "Ministerio de Hacienda",
        },
        "comprobante_retension": {
            "descripcion": "Comprobante de Retención en la Fuente",
            "entidad_emisora": "Empleador o tercero",
            "uso": "Acreditación de impuestos retenidos",
        },
        "factura": {
            "descripcion": "Comprobante Fiscal",
            "requisitos": ["NIT", "Descripción del bien/servicio", "Montos"],
            "plazo_emision": "Dentro del mes de realizada operación",
        },
    },
    
    # Fechas importantes
    "fechas_clave": {
        "cierre_fiscal": "31 de diciembre",
        "plazo_declaracion": "Hasta 120 días después del cierre",
        "pago_isr": "Cuotas mensuales (si ingresos > 156,000",
        "renovacion_nit": "Anualmente",
    },
    
    # Categorías para clasificación
    "categorias_tributarias": {
        "fechas": {
            "descripcion": "Preguntas sobre fechas límite, plazos de pago",
            "palabras_clave": ["fecha", "plazo", "vencimiento", "límite", "día", "mes"],
        },
        "deducciones": {
            "descripcion": "Preguntas sobre deducciones permitidas",
            "palabras_clave": ["deducción", "deducir", "gasto", "permitido", "acreditar"],
        },
        "calculo": {
            "descripcion": "Preguntas sobre cálculo de impuestos",
            "palabras_clave": ["calcular", "cálculo", "cuánto", "monto", "cantidad", "total"],
        },
        "declaraciones": {
            "descripcion": "Preguntas sobre declaraciones y reportes",
            "palabras_clave": ["declaración", "declarar", "reporte", "formulario", "presentar"],
        }
    }
}


def obtener_categoria_tributaria(texto):
    """
    Clasifica el texto en una categoría tributaria
    
    Args:
        texto: Texto a clasificar
        
    Returns:
        Categoría detectada (str)
    """
    texto_lower = texto.lower()
    
    for categoria, datos in DATOS_EL_SALVADOR["categorias_tributarias"].items():
        for palabra_clave in datos["palabras_clave"]:
            if palabra_clave in texto_lower:
                return categoria
    
    return "tributario"  # Categoría por defecto


def obtener_tasa_isr(salario_anual):
    """
    Calcula la tasa de ISR según el salario anual
    
    Args:
        salario_anual: Salario anual en dólares
        
    Returns:
        Tasa ISR aplicable (%)
    """
    tabla = DATOS_EL_SALVADOR["impuestos"]["isr"]["tabla_tarifa"]
    
    for rango in tabla:
        if salario_anual <= 50000:
            return 0
        elif salario_anual <= 156000:
            return 5
        elif salario_anual <= 300000:
            return 10
        else:
            return 30
    
    return 30


def calcular_retenciones(salario_mensual):
    """
    Calcula las retenciones mensuales (ISSS, AFP, ISR)
    
    Args:
        salario_mensual: Salario mensual en dólares
        
    Returns:
        Dict con desglose de retenciones
    """
    cotizaciones = DATOS_EL_SALVADOR["impuestos"]
    
    retencion_isss = salario_mensual * (cotizaciones["cotizaciones_afiliacion"]["empleado"] / 100)
    retencion_afp = salario_mensual * (cotizaciones["cuota_afp"]["empleado"] / 100)
    
    # ISR se calcula sobre el salario después de ISSS y AFP
    salario_sujeto_isr = salario_mensual - retencion_isss - retencion_afp
    retencion_isr = salario_sujeto_isr * 0.10 if salario_sujeto_isr > 0 else 0
    
    total_retenciones = retencion_isss + retencion_afp + retencion_isr
    salario_neto = salario_mensual - total_retenciones
    
    return {
        "salario_bruto": salario_mensual,
        "retencion_isss": round(retencion_isss, 2),
        "retencion_afp": round(retencion_afp, 2),
        "retencion_isr": round(retencion_isr, 2),
        "total_retenciones": round(total_retenciones, 2),
        "salario_neto": round(salario_neto, 2),
    }
