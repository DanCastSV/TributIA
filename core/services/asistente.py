import logging

import google.generativeai as genai
from django.conf import settings

from core.models import AnalisisDocumento, MensajeConversacion, PerfilTributario
from core.datos_el_salvador import DATOS_EL_SALVADOR

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GEMINI_API_KEY)

# Cuántos pares usuario/asistente atrás incluir como memoria de la conversación.
MAX_PARES_HISTORIAL = 10

# Caracteres del resumen_ia de cada documento incluidos en el contexto.
MAX_CHARS_RESUMEN_DOC = 250


def _contexto_perfil(usuario):
    """Construye un resumen del perfil tributario del usuario para el system prompt."""
    try:
        perfil = PerfilTributario.objects.get(usuario=usuario)
    except PerfilTributario.DoesNotExist:
        return "Perfil tributario no configurado."

    tipos = {
        'empleado':  'Empleado en relación de dependencia',
        'freelance': 'Trabajador independiente / Freelance',
        'empresa':   'Empresa / Persona jurídica',
        'otro':      'Otro',
    }

    partes = [
        f"Nombre: {usuario.get_full_name() or usuario.username}",
        f"Tipo de contribuyente: {tipos.get(perfil.tipo_contribuyente, perfil.tipo_contribuyente)}",
    ]

    if perfil.actividad_economica:
        partes.append(f"Actividad económica: {perfil.actividad_economica}")

    if perfil.salario_mensual:
        salario_anual = float(perfil.salario_mensual) * 12
        partes.append(f"Salario mensual: ${perfil.salario_mensual:,.2f}")
        partes.append(f"Salario anual estimado: ${salario_anual:,.2f}")

        if salario_anual <= 50_000:
            tramo = "Exento de ISR (≤ $50,000 anuales)"
            tasa  = 0
        elif salario_anual <= 156_000:
            tramo = "Tramo 5% ISR ($50,001 – $156,000)"
            tasa  = 5
        elif salario_anual <= 300_000:
            tramo = "Tramo 10% ISR ($156,001 – $300,000)"
            tasa  = 10
        else:
            tramo = "Tramo 30% ISR (más de $300,000)"
            tasa  = 30

        partes.append(f"Tramo ISR actual: {tramo}")
        if tasa > 0:
            partes.append(f"Tasa marginal ISR: {tasa}%")
            partes.append(
                f"Ahorro por cada $1,000 deducidos: ${tasa * 10:.0f}"
            )
    else:
        partes.append("Salario: no registrado en el perfil")

    partes.append(f"NIT registrado: {'Sí' if perfil.nit else 'No'}")
    partes.append(f"DUI registrado: {'Sí' if perfil.dui else 'No'}")

    return "\n".join(partes)


def _contexto_documentos(usuario):
    analisis_qs = (
        AnalisisDocumento.objects
        .filter(documento__usuario=usuario)
        .select_related('documento')
        .order_by('-fecha_analisis')[:15]
    )

    if not analisis_qs.exists():
        return "El usuario no ha subido ni analizado documentos todavía."

    partes = []
    for a in analisis_qs:
        tributario = (
            "Sí" if a.es_documento_tributario is True
            else "No" if a.es_documento_tributario is False
            else "No determinado"
        )
        deducible = (
            "Sí" if a.es_deducible is True
            else "No" if a.es_deducible is False
            else "No determinado"
        )

        linea = f"• {a.documento.nombre} ({a.tipo_documento_detectado or a.documento.get_tipo_documento_display()})"

        montos = []
        if a.subtotal:
            montos.append(f"Subtotal ${a.subtotal}")
        if a.iva:
            montos.append(f"IVA ${a.iva}")
        if a.total:
            montos.append(f"Total ${a.total}")
        if montos:
            linea += " — " + ", ".join(montos)

        linea += f" | Tributario: {tributario}, Deducible: {deducible}"

        if a.resumen_ia:
            linea += f"\n  Resumen: {a.resumen_ia[:MAX_CHARS_RESUMEN_DOC]}"

        partes.append(linea)

    return "\n".join(partes)


def _sistema(contexto_perfil, contexto_docs):
    ded = DATOS_EL_SALVADOR["deducciones"]
    imp = DATOS_EL_SALVADOR["impuestos"]

    return f"""Eres TributIA, un asistente experto en tributación de El Salvador integrado en una plataforma de gestión fiscal.

PERFIL DEL USUARIO (usa estos datos para personalizar tus respuestas)
{contexto_perfil}

MARCO FISCAL VIGENTE EN EL SALVADOR
- IVA: {imp['iva']['tasa']}% sobre bienes y servicios.
- ISR personas naturales:
  • Hasta $50,000 anuales: exento
  • $50,001 – $156,000: 5% sobre el exceso de $50,000
  • $156,001 – $300,000: 10% sobre el exceso de $156,000
  • Más de $300,000: 30% sobre el exceso de $300,000
- ISSS (empleado): {imp['cotizaciones_afiliacion']['empleado']}% del salario; empleador: {imp['cotizaciones_afiliacion']['empleador']}%
- AFP (empleado): {imp['cuota_afp']['empleado']}%; empleador: {imp['cuota_afp']['empleador']}%
- Deducciones ISR permitidas:
  • Educación propia o de dependientes: hasta ${ded['educacion']['maximo']:,}/año
  • Salud y medicina: hasta ${ded['salud']['maximo']:,}/año
  • Intereses hipotecarios: {ded['prestamos']['hipotecarios']['tasa_deducible']}% del interés es deducible
  • Otros intereses de préstamos: hasta ${ded['prestamos']['otros']['maximo']:,}
  • Cónyuge: ${ded['familia']['conyuge']:,} | Cada hijo: ${ded['familia']['hijo']:,} (máx. {ded['familia']['maximo_hijos']} hijos)
- Cierre del ejercicio fiscal: 31 de diciembre.
- Plazo para declarar renta: 120 días hábiles después del cierre.
- Entidad reguladora: Ministerio de Hacienda de El Salvador.

DOCUMENTOS DEL USUARIO YA ANALIZADOS POR EL SISTEMA
{contexto_docs}

INSTRUCCIONES DE COMPORTAMIENTO
- Responde SIEMPRE en español.
- Usa el perfil del usuario para dar respuestas personalizadas: cálculos de ISR, retenciones, deducciones y ahorro deben basarse en su salario y tipo de contribuyente reales, no en valores genéricos.
- Si el usuario pregunta cuánto ISR paga, cuánto puede ahorrar, o cuánto le retienen, calcula con los datos de su perfil.
- Si la pregunta NO está relacionada con tributación, impuestos, documentos fiscales o finanzas personales en El Salvador: NO la respondas. Indica amablemente que solo puedes ayudar con temas tributarios.
- Si el usuario pregunta sobre sus documentos, basa tu respuesta en los datos listados arriba, no en suposiciones.
- Sé claro y conciso. Usa listas cuando ayuden a la claridad.
- No inventes cifras, tasas ni leyes que no estén en este contexto."""


def _historial_gemini(conversacion):
    """Convierte los últimos mensajes de la BD al formato history de Gemini."""
    # Tomar los últimos N mensajes (orden descendente para el LIMIT, luego invertir).
    mensajes = list(
        MensajeConversacion.objects
        .filter(conversacion=conversacion)
        .order_by('-creado_en')
        [:MAX_PARES_HISTORIAL * 2]
    )
    mensajes.reverse()

    history = []
    for msg in mensajes:
        role = "user" if msg.rol == "usuario" else "model"
        history.append({"role": role, "parts": [msg.contenido]})

    return history


def responder_con_gemini(conversacion, pregunta):
    """
    Genera una respuesta del asistente con:
    - System prompt con las reglas fiscales de El Salvador.
    - Contexto de los documentos analizados del usuario.
    - Historial de la conversación actual (multi-turno / memoria).
    """
    try:
        usuario = conversacion.usuario
        contexto_perfil = _contexto_perfil(usuario)
        contexto_docs   = _contexto_documentos(usuario)
        historial       = _historial_gemini(conversacion)

        modelo = genai.GenerativeModel(
            "models/gemini-2.5-flash-lite",
            system_instruction=_sistema(contexto_perfil, contexto_docs)
        )

        chat = modelo.start_chat(history=historial)
        respuesta = chat.send_message(pregunta)

        return respuesta.text

    except Exception as e:
        logger.error(f"Error en asistente Gemini: {str(e)}")
        return (
            "Lo siento, ocurrió un error al procesar tu consulta. "
            "Por favor intenta de nuevo en un momento."
        )
