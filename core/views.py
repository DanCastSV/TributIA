import calendar as cal_lib
import csv
import io
import json
import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.analysis_capacity import CapacidadAnalisisAgotada, reservar_capacidad_analisis
from core.datos_el_salvador import DATOS_EL_SALVADOR
from core.fechas_fiscales import fechas_fiscales_mes
from core.formularios_fiscales import formularios_con_checklist
from core.ocr_utils import validar_archivo
from core.rate_limit import limitar_solicitudes
from core.services.reportes import generar_reporte_anual_pdf
from core.services.analizador import DocumentoNoTributarioError, analizar_documento
from core.services.asistente import responder_con_gemini

from .forms import DocumentoForm, PerfilTributarioForm, RegistroUsuarioForm
from .models import (
    AnalisisDocumento,
    ConversacionAsistente,
    DocumentoTributario,
    EventoCalendario,
    MensajeConversacion,
    PerfilTributario,
    UsoGemini,
)

logger = logging.getLogger(__name__)

_MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

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
        for ev in fechas_fiscales_mes(year, mes):
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

@limitar_solicitudes(
    ambito='registro',
    limite=5,
    ventana_segundos=300,
    clave='ip',
)
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
@limitar_solicitudes(
    ambito='documentos-web',
    limite=6,
    ventana_segundos=300,
    clave='usuario',
)
def documentos(request):

    try:
        perfil = PerfilTributario.objects.get(usuario=request.user)
    except PerfilTributario.DoesNotExist:
        perfil = None

    if request.method == 'POST':

        form = DocumentoForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            try:
                with reservar_capacidad_analisis():
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
                    except Exception as e:
                        logger.error(
                            'analisis_web_fallido',
                            extra={'documento_id': doc.id, 'tipo_error': type(e).__name__},
                        )
                        doc.estado = 'error'
                        doc.save()
                        messages.error(request, f'Ocurrió un error al analizar "{doc.nombre}". Inténtalo de nuevo.')
            except CapacidadAnalisisAgotada:
                logger.warning('analisis_web_rechazado', extra={'tipo_error': 'capacidad_agotada'})
                messages.warning(
                    request,
                    'Hay varios documentos en proceso. Inténtalo nuevamente en unos segundos.'
                )

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
            'perfil': perfil,
        }
    )

MAX_ARCHIVOS_LOTE = 10


@login_required
@require_http_methods(['POST'])
@limitar_solicitudes(
    ambito='documentos-lote',
    limite=3,
    ventana_segundos=300,
    clave='usuario',
)
def subir_documentos_lote(request):
    """
    Carga múltiple: sube y analiza hasta MAX_ARCHIVOS_LOTE archivos en un
    solo request. Vista separada de `documentos()` (no una extracción de
    esa función) para no tocar su lógica ya cubierta por
    tests/test_hotfix_uploads.py y tests/test_hotfix_concurrency.py.
    """
    archivos = request.FILES.getlist('archivos')

    if not archivos:
        messages.warning(request, 'No seleccionaste ningún archivo.')
        return redirect('documentos')

    ignorados = max(0, len(archivos) - MAX_ARCHIVOS_LOTE)
    archivos = archivos[:MAX_ARCHIVOS_LOTE]

    analizados = 0
    rechazados = 0
    con_error = 0
    detenido_por_capacidad = False

    for archivo in archivos:
        es_valido, mensaje_validacion = validar_archivo(archivo)
        if not es_valido:
            rechazados += 1
            continue

        try:
            with reservar_capacidad_analisis():
                doc = DocumentoTributario.objects.create(
                    usuario=request.user,
                    nombre=archivo.name,
                    archivo=archivo,
                )
                try:
                    analizar_documento(doc)
                    analizados += 1
                except DocumentoNoTributarioError:
                    rechazados += 1
                except Exception as e:
                    logger.error(
                        'analisis_lote_fallido',
                        extra={'documento_id': doc.id, 'tipo_error': type(e).__name__},
                    )
                    doc.estado = 'error'
                    doc.save()
                    con_error += 1
        except CapacidadAnalisisAgotada:
            logger.warning('analisis_lote_rechazado', extra={'tipo_error': 'capacidad_agotada'})
            detenido_por_capacidad = True
            break

    partes = []
    if analizados:
        partes.append(f'{analizados} analizado{"s" if analizados != 1 else ""}')
    if rechazados:
        partes.append(f'{rechazados} rechazado{"s" if rechazados != 1 else ""} (no tributario o inválido)')
    if con_error:
        partes.append(f'{con_error} con error')

    resumen = ', '.join(partes) if partes else 'no se procesó ningún archivo'
    mensaje = f'Carga múltiple: {resumen}.'
    if detenido_por_capacidad:
        mensaje += ' Hay varios documentos en proceso; el resto del lote no se procesó, inténtalo de nuevo en unos segundos.'
    if ignorados:
        mensaje += f' Se ignoraron {ignorados} archivo{"s" if ignorados != 1 else ""} por superar el máximo de {MAX_ARCHIVOS_LOTE} por carga.'

    nivel = messages.WARNING if (rechazados or con_error or detenido_por_capacidad or ignorados) else messages.SUCCESS
    messages.add_message(request, nivel, mensaje)

    return redirect('documentos')


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
        except Exception as e:
            logger.warning(
                'eliminacion_archivo_fallida',
                extra={'documento_id': documento.id, 'tipo_error': type(e).__name__},
            )
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
@require_http_methods(['POST'])
def enviar_feedback_analisis(request, documento_id):
    documento = get_object_or_404(
        DocumentoTributario,
        id=documento_id,
        usuario=request.user
    )
    analisis = get_object_or_404(AnalisisDocumento, documento=documento)

    valor = request.POST.get('feedback')
    if valor not in dict(AnalisisDocumento.FEEDBACK_CHOICES):
        return JsonResponse({'error': 'valor_invalido'}, status=400)

    analisis.feedback_usuario = valor
    analisis.feedback_comentario = request.POST.get('comentario', '').strip()[:2000] if valor == 'incorrecto' else ''
    analisis.save(update_fields=['feedback_usuario', 'feedback_comentario', 'actualizado_en'])

    return JsonResponse({
        'estado': 'guardado',
        'feedback_usuario': analisis.feedback_usuario,
    })


@login_required
def descargar_documento(request, documento_id):
    """
    Sirve el archivo de un documento solo a su propietario. Reemplaza el
    uso directo de `documento.archivo.url` en los templates: esa URL
    apunta a MEDIA_ROOT, que no tiene ninguna verificación de dueño por sí
    misma (solo esta vista la tiene, vía el filtro usuario=request.user).
    """
    documento = get_object_or_404(
        DocumentoTributario,
        id=documento_id,
        usuario=request.user
    )

    if not documento.archivo or not documento.archivo.name or not os.path.exists(documento.archivo.path):
        raise Http404("Archivo no encontrado")

    nombre_archivo = os.path.basename(documento.archivo.name)

    response = FileResponse(
        documento.archivo.open('rb'),
        as_attachment=False,
        filename=nombre_archivo,
    )
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, max-age=0, no-store'
    return response


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
    perfil = None
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

    # ── Años disponibles para el reporte anual ─────────────────────
    anios_disponibles = list(
        analisis.dates('fecha_analisis', 'year', order='DESC')
    )
    anios_disponibles = [d.year for d in anios_disponibles]

    # ── Tendencia mensual del año actual ───────────────────────────
    anio_actual = date.today().year
    por_mes = (
        analisis.filter(fecha_analisis__year=anio_actual)
        .annotate(mes=TruncMonth('fecha_analisis'))
        .values('mes')
        .annotate(
            total_mes=Sum('total'),
            deducible_mes=Sum('total', filter=Q(es_deducible=True)),
        )
    )
    montos_por_mes = {p['mes'].month: float(p['total_mes'] or 0) for p in por_mes}
    monto_maximo_mes = max(montos_por_mes.values()) if montos_por_mes else 0
    tendencia_mensual = [
        {
            'mes': _MESES_ES[m][:3],
            'monto': montos_por_mes.get(m, 0),
            'pct': _pct(montos_por_mes.get(m, 0), monto_maximo_mes) if monto_maximo_mes else 0,
        }
        for m in range(1, 13)
    ]

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
        # Perfil (para prellenar el simulador)
        'perfil': perfil,
        # Reporte anual y tendencia
        'anios_disponibles': anios_disponibles,
        'anio_actual': anio_actual,
        'tendencia_mensual': tendencia_mensual,
        # Tabla
        'page_obj': page_obj,
    })


@login_required
def reporte_anual_pdf(request):
    try:
        anio = int(request.GET.get('anio', date.today().year))
    except (TypeError, ValueError):
        anio = date.today().year

    pdf_bytes = generar_reporte_anual_pdf(request.user, anio)

    respuesta = HttpResponse(pdf_bytes, content_type='application/pdf')
    respuesta['Content-Disposition'] = f'attachment; filename="tributia-{anio}.pdf"'
    return respuesta


@login_required
def exportar_analisis_csv(request):
    try:
        anio = int(request.GET.get('anio', date.today().year))
    except (TypeError, ValueError):
        anio = date.today().year

    analisis = (
        AnalisisDocumento.objects
        .filter(documento__usuario=request.user, fecha_analisis__year=anio)
        .select_related('documento')
        .order_by('fecha_analisis')
    )

    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow([
        'ID', 'Empresa', 'Cliente', 'Fecha documento', 'Número documento',
        'Tipo detectado', 'Categoría detectada',
        'NIT tradicional', 'Identificador homologado', 'NRC', 'Teléfono', 'Correo', 'Giro', 'Dirección',
        'Subtotal', 'IVA', 'Otros cargos', 'Total',
        'Tributario', 'Deducible', 'Justificación deducible',
        'Confianza clasificación', 'Modelo IA', 'Fecha de análisis',
    ])
    for a in analisis:
        escritor.writerow([
            a.documento_id,
            a.nombre_empresa or a.documento.nombre,
            a.nombre_cliente or '',
            a.fecha_documento or '',
            a.numero_documento or '',
            a.tipo_documento_detectado or '',
            a.categoria_detectada or '',
            a.nit_tradicional or '',
            a.identificador_homologado or '',
            a.nrc or '',
            a.telefono or '',
            a.correo or '',
            a.giro or '',
            a.direccion_detectada or '',
            a.subtotal if a.subtotal is not None else '',
            a.iva if a.iva is not None else '',
            a.otros_cargos if a.otros_cargos is not None else '',
            a.total if a.total is not None else '',
            'Sí' if a.es_documento_tributario else 'No' if a.es_documento_tributario is False else '',
            'Sí' if a.es_deducible else 'No' if a.es_deducible is False else '',
            a.justificacion_deducible or '',
            a.confianza_clasificacion,
            a.modelo_ia or '',
            a.fecha_analisis.strftime('%d/%m/%Y'),
        ])

    respuesta = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="tributia-{anio}.csv"'
    return respuesta


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
    for ev in fechas_fiscales_mes(year, month):
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
    analisis_usuario = AnalisisDocumento.objects.filter(
        documento__usuario=request.user
    ).select_related('documento')

    formularios = formularios_con_checklist(analisis_usuario)

    return render(request, 'recursos_fiscales.html', {'formularios': formularios})


@login_required
def como_funciona(request):
    return render(request, 'como_funciona.html')


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

    try:
        perfil = PerfilTributario.objects.get(usuario=request.user)
    except PerfilTributario.DoesNotExist:
        perfil = None

    return render(
        request,
        "asistente_ia.html",
        {
            "conversacion": conversacion,
            "conversaciones": conversaciones,
            "mensajes": mensajes,
            "perfil": perfil,
        }
    )


@login_required
@require_http_methods(["POST"])
@limitar_solicitudes(
    ambito='chat-gemini',
    limite=12,
    ventana_segundos=300,
    clave='usuario',
    json=True,
)
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
    if len(pregunta) > 2000:
        return JsonResponse({"error": "La pregunta es demasiado larga"}, status=400)

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


@staff_member_required
def uso_gemini_resumen(request):
    """
    Panel de administración (no enlazado en el sidebar) para ver cuántos
    tokens de Gemini consume cada usuario, y qué tan cerca está el
    proyecto de los límites del tier gratuito (RPD/RPM/TPM). Google no
    desglosa nada de esto por usuario de la app, solo un total por
    proyecto — por eso se registra localmente en core/uso_gemini.py.
    """
    ahora = timezone.now()
    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    def _total_tokens(qs):
        return qs.aggregate(total=Sum('tokens_total'))['total'] or 0

    todos = UsoGemini.objects.all()

    totales = {
        'hoy': _total_tokens(todos.filter(creado_en__date=hoy)),
        'semana': _total_tokens(todos.filter(creado_en__date__gte=inicio_semana)),
        'mes': _total_tokens(todos.filter(creado_en__year=hoy.year, creado_en__month=hoy.month)),
    }

    por_usuario = (
        todos.values('usuario__username')
        .annotate(llamadas=Count('id'), tokens=Sum('tokens_total'))
        .order_by('-tokens')
    )

    # ── Límites del tier gratuito (RPD diario, RPM/TPM por minuto) ──
    limite_rpd = getattr(settings, 'TRIBUTIA_GEMINI_RPD_LIMITE', 20)
    limite_rpm = getattr(settings, 'TRIBUTIA_GEMINI_RPM_LIMITE', 10)
    limite_tpm = getattr(settings, 'TRIBUTIA_GEMINI_TPM_LIMITE', 250_000)

    hace_un_minuto = ahora - timedelta(minutes=1)
    ultimo_minuto = todos.filter(creado_en__gte=hace_un_minuto)

    solicitudes_hoy = todos.filter(creado_en__date=hoy).count()
    solicitudes_ultimo_minuto = ultimo_minuto.count()
    tokens_ultimo_minuto = _total_tokens(ultimo_minuto)

    def _pct(usado, limite):
        return min(100, round(usado / limite * 100)) if limite else 0

    # El RPD de Gemini se reinicia a medianoche hora Pacífico.
    pacifico = ZoneInfo('America/Los_Angeles')
    ahora_pacifico = ahora.astimezone(pacifico)
    proximo_reset_pacifico = (ahora_pacifico + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    proximo_reset_local = proximo_reset_pacifico.astimezone(ZoneInfo(settings.TIME_ZONE))
    segundos_para_reset = int((proximo_reset_pacifico - ahora).total_seconds())
    horas_para_reset, resto = divmod(max(0, segundos_para_reset), 3600)
    minutos_para_reset = resto // 60

    limites = {
        'rpd': {'usado': solicitudes_hoy, 'limite': limite_rpd, 'pct': _pct(solicitudes_hoy, limite_rpd)},
        'rpm': {'usado': solicitudes_ultimo_minuto, 'limite': limite_rpm, 'pct': _pct(solicitudes_ultimo_minuto, limite_rpm)},
        'tpm': {'usado': tokens_ultimo_minuto, 'limite': limite_tpm, 'pct': _pct(tokens_ultimo_minuto, limite_tpm)},
        'reset_local': proximo_reset_local,
        'reset_en': f'{horas_para_reset}h {minutos_para_reset}min',
    }

    return render(request, 'uso_gemini.html', {
        'totales': totales,
        'por_usuario': por_usuario,
        'limites': limites,
    })


