from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
import json
import calendar as cal_lib
from datetime import date, datetime
from django.db.models import Sum, Q

from .forms import PerfilTributarioForm, RegistroUsuarioForm, DocumentoForm
from .models import (
    PerfilTributario,
    DocumentoTributario,
    AnalisisDocumento,
    ConversacionAsistente,
    MensajeConversacion,
    EventoCalendario,
)

from core.services.analizador import analizar_documento, DocumentoNoTributarioError
from core.services.asistente import responder_con_gemini
from core.datos_el_salvador import DATOS_EL_SALVADOR

_MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

def _fechas_fiscales_mes(year, month):
    """Devuelve las fechas fiscales fijas para el mes indicado."""
    last_day = cal_lib.monthrange(year, month)[1]
    eventos = [
        {
            'titulo': 'Vence retención ISR mensual',
            'tipo': 'fiscal',
            'id': None,
            'descripcion': 'Enterar retenciones de ISR a empleados ante el Ministerio de Hacienda.',
            'day': min(10, last_day),
        },
        {
            'titulo': 'Vence declaración IVA (F-07)',
            'tipo': 'fiscal',
            'id': None,
            'descripcion': 'Últimos 10 días hábiles del mes para presentar y pagar el IVA.',
            'day': min(21, last_day),
        },
    ]
    if month == 4:
        eventos.append({
            'titulo': 'Vence Declaración de Renta (F-11)',
            'tipo': 'fiscal',
            'id': None,
            'descripcion': '120 días hábiles tras el cierre del ejercicio fiscal.',
            'day': 30,
        })
    if month == 12:
        eventos.append({
            'titulo': 'Cierre del ejercicio fiscal',
            'tipo': 'fiscal',
            'id': None,
            'descripcion': 'Fin del año fiscal. Todos los ingresos deben estar registrados.',
            'day': 31,
        })
    return eventos

def _calcular_consejo(total_documentos, total_analizados, total_tributarios,
                       total_deducibles, total_deducible_monto, total_pendientes,
                       proximos_eventos, perfil):
    hoy = date.today()

    # 1. Sin documentos
    if total_documentos == 0:
        return {
            'tipo': 'inicio',
            'icono': 'upload',
            'titulo': '¡Empieza subiendo tu primer documento!',
            'mensaje': (
                'Sube una factura, constancia salarial o declaración y TributIA la '
                'analizará automáticamente para decirte si es deducible y cuánto '
                'podrías ahorrar en impuestos.'
            ),
            'accion_url': 'documentos',
            'accion_texto': 'Subir primer documento',
        }

    # 2. Documentos pendientes de análisis
    if total_pendientes > 0:
        return {
            'tipo': 'alerta',
            'icono': 'clock',
            'titulo': f'Tienes {total_pendientes} documento{"s" if total_pendientes > 1 else ""} sin analizar',
            'mensaje': (
                'Abre cada documento en la sección Documentos para activar el '
                'análisis IA. TributIA verificará si son tributarios y si puedes '
                'deducirlos.'
            ),
            'accion_url': 'documentos',
            'accion_texto': 'Ver documentos pendientes',
        }

    # 3. Fecha fiscal urgente (próximos 5 días)
    urgente = next(
        (e for e in proximos_eventos
         if e['tipo'] == 'fiscal' and (e['fecha'] - hoy).days <= 5),
        None
    )
    if urgente:
        dias = (urgente['fecha'] - hoy).days
        return {
            'tipo': 'urgente',
            'icono': 'triangle-alert',
            'titulo': f'Fecha fiscal en {"hoy" if dias == 0 else f"{dias} día{"s" if dias > 1 else ""}"}',
            'mensaje': f'{urgente["titulo"]}. Asegúrate de tener tus documentos listos antes del plazo.',
            'accion_url': 'calendario',
            'accion_texto': 'Ver calendario',
        }

    # 4. Sin documentos tributarios detectados
    if total_tributarios == 0 and total_analizados > 0:
        return {
            'tipo': 'info',
            'icono': 'info',
            'titulo': 'Ninguno de tus documentos es tributario',
            'mensaje': (
                'Los documentos analizados no son fiscales salvadoreños. '
                'Prueba subiendo facturas de consumidor final, créditos fiscales '
                'o constancias de retención para obtener análisis reales.'
            ),
            'accion_url': 'documentos',
            'accion_texto': 'Subir documento fiscal',
        }

    # 5. Sin perfil de salario — no podemos personalizar ISR
    salario_anual = 0
    if perfil and perfil.salario_mensual:
        salario_anual = float(perfil.salario_mensual) * 12

    if total_tributarios > 0 and not salario_anual:
        return {
            'tipo': 'consejo',
            'icono': 'user',
            'titulo': 'Agrega tu salario para consejos personalizados',
            'mensaje': (
                'Con tu salario registrado, TributIA puede calcular exactamente '
                'cuánto ISR pagas, en qué tramo estás y cuánto ahorrarías con '
                'tus documentos deducibles.'
            ),
            'accion_url': 'editar_perfil',
            'accion_texto': 'Completar mi perfil',
        }

    # 6. Tiene deducibles y salario en tramo ISR — calcular ahorro
    if total_deducibles > 0 and salario_anual > 50_000:
        if salario_anual <= 156_000:
            tasa = 5
        elif salario_anual <= 300_000:
            tasa = 10
        else:
            tasa = 30
        ahorro = float(total_deducible_monto) * tasa / 100
        return {
            'tipo': 'oportunidad',
            'icono': 'trending-down',
            'titulo': f'Puedes ahorrar ~${ahorro:,.2f} en ISR',
            'mensaje': (
                f'Tienes ${total_deducible_monto:,.2f} en gastos deducibles. '
                f'Con tu tramo ISR del {tasa}%, presentar estas deducciones en tu '
                f'declaración anual podría reducir tu carga fiscal en ese monto.'
            ),
            'accion_url': 'centro_analisis',
            'accion_texto': 'Ver Centro de Análisis',
        }

    # 7. Tiene tributarios pero ninguno deducible
    if total_tributarios > 0 and total_deducibles == 0:
        return {
            'tipo': 'consejo',
            'icono': 'search',
            'titulo': 'Revisa si tienes gastos deducibles',
            'mensaje': (
                'Tus documentos tributarios no califican como deducibles aún. '
                'Facturas de educación, salud, intereses hipotecarios y cargas '
                'familiares son deducibles del ISR en El Salvador. '
                '¿Tienes alguno de esos gastos?'
            ),
            'accion_url': 'asistente_ia',
            'accion_texto': 'Preguntarle al asistente',
        }

    # 8. Todo en orden — consejo general positivo
    return {
        'tipo': 'excelente',
        'icono': 'circle-check',
        'titulo': 'Tu gestión fiscal está al día',
        'mensaje': (
            f'Tienes {total_tributarios} documento{"s" if total_tributarios > 1 else ""} '
            f'tributario{"s" if total_tributarios > 1 else ""} y '
            f'{total_deducibles} deducible{"s" if total_deducibles > 1 else ""} registrados. '
            'Continúa subiendo documentos para mantener un historial fiscal completo.'
        ),
        'accion_url': 'documentos',
        'accion_texto': 'Subir más documentos',
    }


@login_required
def dashboard(request):

    documentos = DocumentoTributario.objects.filter(
        usuario=request.user
    )

    analizados = documentos.filter(
        estado='analizado'
    )

    total_documentos = documentos.count()

    total_analizados = analizados.count()

    ultimo_documento = documentos.order_by(
        '-fecha_subida'
    ).first()

    analisis_usuario = AnalisisDocumento.objects.filter(
        documento__usuario=request.user
    )

    total_tributarios = analisis_usuario.filter(
        es_documento_tributario=True
    ).count()

    total_deducibles = analisis_usuario.filter(
        es_deducible=True
    ).count()

    ultimo_analisis = analisis_usuario.filter(
        es_documento_tributario__isnull=False,
        recomendacion_ia__isnull=False
    ).order_by('-fecha_analisis').first()

    # KPIs financieros
    totales = analisis_usuario.aggregate(
        total_facturado=Sum('total'),
        total_iva=Sum('iva'),
        total_deducible_monto=Sum('subtotal', filter=Q(es_deducible=True)),
    )
    total_facturado      = totales['total_facturado'] or 0
    total_iva            = totales['total_iva'] or 0
    total_deducible_monto = totales['total_deducible_monto'] or 0

    # Próximos eventos (usuario + fiscales fijos), los 4 más cercanos
    hoy = date.today()
    eventos_proximos_db = list(
        EventoCalendario.objects
        .filter(usuario=request.user, fecha__gte=hoy)
        .order_by('fecha')[:6]
    )
    # Construir eventos fiscales de este mes y el próximo
    eventos_fiscales = []
    for delta_mes in range(2):
        mes = (hoy.month - 1 + delta_mes) % 12 + 1
        year = hoy.year + ((hoy.month - 1 + delta_mes) // 12)
        for ev in _fechas_fiscales_mes(year, mes):
            ev_date = date(year, mes, ev['day'])
            if ev_date >= hoy:
                eventos_fiscales.append({
                    'titulo': ev['titulo'],
                    'tipo': 'fiscal',
                    'fecha': ev_date,
                })

    # Mezclar y tomar los 4 más próximos
    proximos_combinados = []
    for ev in eventos_proximos_db:
        proximos_combinados.append({
            'titulo': ev.titulo,
            'tipo': ev.tipo,
            'fecha': ev.fecha,
        })
    proximos_combinados += eventos_fiscales
    proximos_combinados.sort(key=lambda e: e['fecha'])
    proximos_eventos = proximos_combinados[:4]

    # Documentos pendientes de analizar
    pendientes = documentos.exclude(estado='analizado')
    primer_pendiente = pendientes.order_by('-fecha_subida').first()
    total_pendientes = pendientes.count()

    # Perfil para el consejo personalizado
    try:
        perfil = PerfilTributario.objects.get(usuario=request.user)
    except PerfilTributario.DoesNotExist:
        perfil = None

    consejo = _calcular_consejo(
        total_documentos=total_documentos,
        total_analizados=total_analizados,
        total_tributarios=total_tributarios,
        total_deducibles=total_deducibles,
        total_deducible_monto=float(total_deducible_monto),
        total_pendientes=total_pendientes,
        proximos_eventos=proximos_eventos,
        perfil=perfil,
    )

    return render(
        request,
        'dashboard.html',
        {
            'total_documentos':       total_documentos,
            'total_analizados':       total_analizados,
            'ultimo_documento':       ultimo_documento,
            'total_tributarios':      total_tributarios,
            'total_deducibles':       total_deducibles,
            'ultimo_analisis':        ultimo_analisis,
            'total_facturado':        total_facturado,
            'total_iva':              total_iva,
            'total_deducible_monto':  total_deducible_monto,
            'proximos_eventos':       proximos_eventos,
            'total_pendientes':       total_pendientes,
            'primer_pendiente':       primer_pendiente,
            'consejo':                consejo,
        }
    )

def home(request):
    return render(request, 'home.html')

def registro(request):

    if request.method == 'POST':

        form = RegistroUsuarioForm(request.POST)

        if form.is_valid():

            usuario = form.save()

            PerfilTributario.objects.create(
                usuario=usuario
            )

            return redirect('login')

    else:

        form = RegistroUsuarioForm()

    return render(
        request,
        'registro.html',
        {'form': form}
    )

@login_required
def perfil(request):

    perfil = PerfilTributario.objects.get(
        usuario=request.user
    )

    campos = [
        perfil.dui,
        perfil.nit,
        perfil.telefono,
        perfil.salario_mensual,
        perfil.actividad_economica
    ]

    completos = sum(bool(c) for c in campos)

    porcentaje = int(
        (completos / len(campos)) * 100
    )

    return render(
        request,
        'perfil.html',
        {
            'perfil': perfil,
            'porcentaje': porcentaje
        }
    )

@login_required
def editar_perfil(request):

    perfil = PerfilTributario.objects.get(
        usuario=request.user
    )

    if request.method == "POST":

        form = PerfilTributarioForm(
            request.POST,
            instance=perfil
        )

        if form.is_valid():

            form.save()

            return redirect('perfil')

    else:

        form = PerfilTributarioForm(
            instance=perfil
        )

    return render(
        request,
        'editar_perfil.html',
        {
            'form': form
        }
    )

@login_required
def documentos(request):

    if request.method == 'POST':

        form = DocumentoForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            doc = form.save(commit=False)
            doc.usuario = request.user
            doc.save()

            try:
                analizar_documento(doc)
                messages.success(request, f'"{doc.nombre}" fue analizado correctamente.')
            except DocumentoNoTributarioError as e:
                messages.warning(
                    request,
                    f'El documento "{doc.nombre}" fue rechazado: {e} No se guardó en el sistema.'
                )
            except Exception:
                doc.estado = 'error'
                doc.save()
                messages.error(request, f'Ocurrió un error al analizar "{doc.nombre}". Inténtalo de nuevo.')

            return redirect('documentos')

    else:
        form = DocumentoForm()

    qs = DocumentoTributario.objects.filter(
        usuario=request.user
    ).order_by('-fecha_subida')

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'documentos.html',
        {
            'form': form,
            'documentos': page_obj,
            'page_obj': page_obj,
        }
    )

@login_required
@require_http_methods(['POST'])
def eliminar_documento(request, documento_id):
    documento = get_object_or_404(
        DocumentoTributario,
        id=documento_id,
        usuario=request.user
    )
    # Eliminar el archivo físico del disco
    if documento.archivo:
        try:
            documento.archivo.delete(save=False)
        except Exception:
            pass
    documento.delete()
    return redirect('documentos')


@login_required
def detalle_documento(request, documento_id):

    documento = get_object_or_404(
        DocumentoTributario,
        id=documento_id,
        usuario=request.user
    )

    if not documento.archivo or not documento.archivo.name:
        documento.delete()
        messages.warning(request, 'El documento no tenía archivo asociado y fue eliminado.')
        return redirect('documentos')

    analisis = AnalisisDocumento.objects.filter(
        documento=documento
    ).first()

    return render(
        request,
        'detalle_documento.html',
        {
            'documento': documento,
            'analisis': analisis
        }
    )

@login_required
def centro_analisis(request):
    documentos = DocumentoTributario.objects.filter(usuario=request.user)
    analisis   = AnalisisDocumento.objects.filter(documento__usuario=request.user)

    # ── Conteos básicos ──────────────────────────────────────────
    total_documentos = documentos.count()
    total_analizados = documentos.filter(estado='analizado').count()
    total_error      = documentos.filter(estado='error').count()

    # ── Montos financieros ───────────────────────────────────────
    totales = analisis.aggregate(
        total_facturado=Sum('total'),
        total_iva=Sum('iva'),
        total_subtotal=Sum('subtotal'),
    )
    total_facturado = totales['total_facturado'] or 0
    total_iva       = totales['total_iva']       or 0

    total_deducible = (
        analisis.filter(es_deducible=True)
        .aggregate(monto=Sum('total'))['monto'] or 0
    )

    # ── Clasificación tributaria ──────────────────────────────────
    count_tributario    = analisis.filter(es_documento_tributario=True).count()
    count_no_tributario = analisis.filter(es_documento_tributario=False).count()
    count_sin_clasif    = analisis.filter(es_documento_tributario__isnull=True).count()

    count_deducible     = analisis.filter(es_deducible=True).count()
    count_no_deducible  = analisis.filter(es_deducible=False).count()
    count_sin_deducible = analisis.filter(es_deducible__isnull=True).count()

    # ── Porcentajes para barras de progreso ───────────────────────
    def _pct(a, b):
        return int(a / b * 100) if b else 0

    pct_analizados = _pct(total_analizados, total_documentos)
    pct_tributario = _pct(count_tributario, total_analizados)
    clasificados   = count_deducible + count_no_deducible
    pct_deducible  = _pct(count_deducible, clasificados)

    # ── Ahorro ISR estimado ───────────────────────────────────────
    # Usa la tasa marginal del salario anual del usuario
    tasa_isr = 0
    salario_anual = 0
    try:
        perfil = PerfilTributario.objects.get(usuario=request.user)
        salario_anual = float(perfil.salario_mensual or 0) * 12
        if salario_anual > 300_000:
            tasa_isr = 30
        elif salario_anual > 156_000:
            tasa_isr = 10
        elif salario_anual > 50_000:
            tasa_isr = 5
    except PerfilTributario.DoesNotExist:
        pass

    ahorro_isr = float(total_deducible) * (tasa_isr / 100)
    tiene_salario = salario_anual > 0

    # ── Tabla completa de análisis (paginada) ─────────────────────
    todos = analisis.select_related('documento').order_by('-fecha_analisis')
    paginator = Paginator(todos, 10)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'centro_analisis.html', {
        # Conteos
        'total_documentos': total_documentos,
        'total_analizados': total_analizados,
        'total_error':      total_error,
        # Montos
        'total_facturado':  total_facturado,
        'total_iva':        total_iva,
        'total_deducible':  total_deducible,
        # Clasificación
        'count_tributario':    count_tributario,
        'count_no_tributario': count_no_tributario,
        'count_sin_clasif':    count_sin_clasif,
        'count_deducible':     count_deducible,
        'count_no_deducible':  count_no_deducible,
        'count_sin_deducible': count_sin_deducible,
        # Porcentajes
        'pct_analizados': pct_analizados,
        'pct_tributario': pct_tributario,
        'pct_deducible':  pct_deducible,
        # ISR
        'tasa_isr':     tasa_isr,
        'ahorro_isr':   ahorro_isr,
        'tiene_salario': tiene_salario,
        # Tabla
        'page_obj': page_obj,
    })

@login_required
def calendario(request):
    today = date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        year, month = today.year, today.month

    try:
        dia_buscado = int(request.GET.get('dia', 0))
    except (ValueError, TypeError):
        dia_buscado = 0

    # Navegación mes anterior / siguiente
    prev_month = month - 1 if month > 1 else 12
    prev_year  = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year  = year if month < 12 else year + 1

    # Eventos del usuario este mes
    eventos_usuario = EventoCalendario.objects.filter(
        usuario=request.user,
        fecha__year=year,
        fecha__month=month,
    )

    # Agrupar por día
    eventos_por_dia = {}
    for ev in _fechas_fiscales_mes(year, month):
        eventos_por_dia.setdefault(ev['day'], []).append(ev)
    for ev in eventos_usuario:
        eventos_por_dia.setdefault(ev.fecha.day, []).append({
            'titulo': ev.titulo,
            'tipo': ev.tipo,
            'id': ev.id,
            'descripcion': ev.descripcion,
            'day': ev.fecha.day,
        })

    # Construir semanas (empieza en domingo)
    cal = cal_lib.Calendar(firstweekday=6)
    semanas = []
    for semana in cal.monthdayscalendar(year, month):
        dias = []
        for day in semana:
            if day == 0:
                dias.append(None)
            else:
                current = date(year, month, day)
                dias.append({
                    'day': day,
                    'is_today': current == today,
                    'is_past': current < today,
                    'eventos': eventos_por_dia.get(day, []),
                })
        semanas.append(dias)

    imp = DATOS_EL_SALVADOR['impuestos']
    ded = DATOS_EL_SALVADOR['deducciones']
    tasas = [
        {'label': 'IVA',              'valor': f"{imp['iva']['tasa']}%",                          'nota': 'Sobre bienes y servicios'},
        {'label': 'ISR mínimo',       'valor': f"{imp['isr']['tasa_min']}%",                       'nota': 'Renta $50,001–$156,000'},
        {'label': 'ISR máximo',       'valor': f"{imp['isr']['tasa_max']}%",                       'nota': 'Renta > $300,000'},
        {'label': 'ISSS empleado',    'valor': f"{imp['cotizaciones_afiliacion']['empleado']}%",   'nota': 'Del salario bruto'},
        {'label': 'AFP empleado',     'valor': f"{imp['cuota_afp']['empleado']}%",                 'nota': 'Del salario bruto'},
        {'label': 'Deducción educación', 'valor': f"${ded['educacion']['maximo']:,}",              'nota': 'Máximo anual'},
        {'label': 'Deducción salud',  'valor': f"${ded['salud']['maximo']:,}",                     'nota': 'Máximo anual'},
    ]

    return render(request, 'calendario.html', {
        'semanas': semanas,
        'year': year,
        'month': month,
        'month_name': _MESES_ES[month],
        'today': today,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'eventos_mes': list(eventos_usuario.order_by('fecha')),
        'tasas': tasas,
        'dia_buscado': dia_buscado,
    })


@login_required
@require_http_methods(['POST'])
def crear_evento(request):
    titulo      = request.POST.get('titulo', '').strip()
    fecha_str   = request.POST.get('fecha', '')
    tipo        = request.POST.get('tipo', 'recordatorio')
    descripcion = request.POST.get('descripcion', '').strip()
    year        = request.POST.get('year', '')
    month       = request.POST.get('month', '')

    ev_year, ev_month = year, month
    if titulo and fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            EventoCalendario.objects.create(
                usuario=request.user,
                titulo=titulo,
                fecha=fecha,
                tipo=tipo,
                descripcion=descripcion,
            )
            ev_year  = ev_year  or str(fecha.year)
            ev_month = ev_month or str(fecha.month)
        except ValueError:
            pass

    return redirect(f'/calendario/?year={ev_year}&month={ev_month}')


@login_required
@require_http_methods(['POST'])
def eliminar_evento(request, evento_id):
    evento = get_object_or_404(EventoCalendario, id=evento_id, usuario=request.user)
    ev_year, ev_month = evento.fecha.year, evento.fecha.month
    evento.delete()
    return redirect(f'/calendario/?year={ev_year}&month={ev_month}')

@login_required
def recursos_fiscales(request):
    FORMULARIOS = [
        {
            'codigo': 'F-07',
            'nombre': 'Declaración y Pago del IVA',
            'periodicidad': 'Mensual',
            'descripcion': 'Declaración del Impuesto a la Transferencia de Bienes Muebles y Prestación de Servicios (IVA 13%). Debe presentarse dentro de los primeros 10 días hábiles del mes siguiente.',
            'documentos': [
                'Libro de compras IVA (comprobantes de crédito fiscal recibidos)',
                'Libro de ventas IVA (facturas y comprobantes emitidos)',
                'Comprobantes de retención del 1% recibidos',
                'NIT y NRC del contribuyente',
                'Estados de cuenta bancarios del período',
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
                'Constancia de salario o ingresos del año (emitida por el empleador)',
                'Comprobantes de deducciones: gastos de salud, educación, intereses hipotecarios',
                'Certificados de retención de ISR recibidos',
                'Información de cargas familiares (cónyuge, hijos)',
                'NIT del contribuyente y de dependientes',
                'Estados financieros (para empresas y profesionales independientes)',
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
                'Planilla de sueldos del mes con retenciones ISR calculadas',
                'Registros de ingresos brutos del mes',
                'Comprobantes de retenciones efectuadas a terceros',
                'NIT del agente de retención',
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
                'Comprobantes de retención del 1% emitidos y recibidos',
                'Registro de compras a proveedores del período',
                'NIT de los proveedores a quienes se retuvo',
                'Comprobantes de crédito fiscal del período',
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
                'Constancia de sueldo anual emitida por el patrono',
                'DUI y NIT del empleado',
                'Comprobantes de deducciones adicionales (salud, educación, préstamos)',
                'Datos de cargas familiares si aplica',
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
                'DUI vigente del solicitante o representante legal',
                'NIT (si ya está inscrito y desea actualizar)',
                'Escritura de constitución (para personas jurídicas)',
                'Credencial del representante legal',
                'Contrato de arrendamiento o título de propiedad del local (dirección fiscal)',
            ],
            'icono': 'landmark',
            'url': 'https://www.mh.gob.sv/',
            'url_label': 'Ver en sitio del Ministerio de Hacienda',
        },
    ]
    return render(request, 'recursos_fiscales.html', {'formularios': FORMULARIOS})


@login_required
def asistente_ia(request):
    """
    Vista del asistente IA con historial de conversaciones
    """

    # ==========================================
    # OBTENER CONVERSACIÓN ACTUAL
    # ==========================================

    conversacion_id = request.GET.get(
        "conversacion_id"
    )

    conversacion = None

    if conversacion_id:

        conversacion = (
            ConversacionAsistente.objects
            .filter(
                id=conversacion_id,
                usuario=request.user
            )
            .first()
        )

    # Si no existe la conversación solicitada
    # cargar la más reciente

    if not conversacion:

        conversacion = (
            ConversacionAsistente.objects
            .filter(
                usuario=request.user
            )
            .order_by("-actualizada_en")
            .first()
        )

    # Si no existe ninguna conversación
    # crear una nueva automáticamente

    if not conversacion:

        conversacion = (
            ConversacionAsistente.objects
            .create(
                usuario=request.user,
                titulo="Primera conversación"
            )
        )

    # ==========================================
    # LISTADO DE CONVERSACIONES
    # ==========================================

    conversaciones = (
        ConversacionAsistente.objects
        .filter(
            usuario=request.user
        )
        .order_by(
            "-actualizada_en"
        )
    )

    # ==========================================
    # MENSAJES DE LA CONVERSACIÓN
    # ==========================================

    mensajes = (
        MensajeConversacion.objects
        .filter(
            conversacion=conversacion
        )
        .order_by(
            "creado_en"
        )
    )

    return render(
        request,
        "asistente_ia.html",
        {
            "conversacion": conversacion,
            "conversaciones": conversaciones,
            "mensajes": mensajes,
        }
    )


@login_required
@require_http_methods(["POST"])
def enviar_mensaje(request):
    """Endpoint AJAX: recibe pregunta, llama a Gemini, devuelve JSON."""
    try:
        data = json.loads(request.body)
        pregunta = data.get("pregunta", "").strip()
        conversacion_id = data.get("conversacion_id")
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": "Petición inválida"}, status=400)

    if not pregunta:
        return JsonResponse({"error": "Pregunta vacía"}, status=400)

    conversacion = get_object_or_404(
        ConversacionAsistente,
        id=conversacion_id,
        usuario=request.user,
    )

    MensajeConversacion.objects.create(
        conversacion=conversacion,
        rol="usuario",
        contenido=pregunta,
    )

    respuesta = responder_con_gemini(conversacion, pregunta)

    MensajeConversacion.objects.create(
        conversacion=conversacion,
        rol="asistente",
        contenido=respuesta,
    )

    if conversacion.mensajes.count() <= 2:
        conversacion.titulo = pregunta[:50]
        conversacion.save()
    else:
        conversacion.save()  # actualiza actualizada_en

    from django.utils import timezone
    hora = timezone.localtime(timezone.now()).strftime("%H:%M")

    return JsonResponse({"respuesta": respuesta, "hora": hora, "titulo": conversacion.titulo})


@login_required
@require_http_methods(["POST"])
def nueva_conversacion(request):
    """API para crear nueva conversación"""
    conversacion = ConversacionAsistente.objects.create(
        usuario=request.user,
        titulo="Nueva conversación"
    )
    return JsonResponse({
        'id': conversacion.id,
        'titulo': conversacion.titulo,
        'url': f'/asistente-ia/?conversacion_id={conversacion.id}'
    })


@login_required
@require_http_methods(["DELETE"])
def eliminar_conversacion(request, conversacion_id):
    """API para eliminar conversación"""
    conversacion = get_object_or_404(
        ConversacionAsistente,
        id=conversacion_id,
        usuario=request.user
    )
    conversacion.delete()
    return JsonResponse({'estado': 'eliminado'})


