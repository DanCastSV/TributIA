"""
Manda un correo a cada usuario con las fechas fiscales (fijas + eventos
propios del calendario) que vencen dentro de los próximos N días.

Uso:
    python manage.py enviar_recordatorios_fiscales
    python manage.py enviar_recordatorios_fiscales --dias 7

No hay scheduler (Celery/cron) integrado en el proyecto todavía, así que
este comando se corre a mano o se agenda externamente (Programador de
Tareas de Windows, cron dentro del contenedor, etc.). No lleva registro
de qué ya se envió: correrlo más de una vez el mismo día reenvía el
correo a quien siga teniendo eventos en la ventana. Para uso automatizado
se recomienda correrlo una sola vez al día.
"""

import logging
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from core.fechas_fiscales import fechas_fiscales_mes
from core.models import EventoCalendario

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envía por email las fechas fiscales (fijas y del calendario) próximas a vencer."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=3,
            help='Ventana de días hacia adelante a revisar (default: 3).',
        )

    def handle(self, *args, **opciones):
        dias = opciones['dias']
        hoy = date.today()
        limite = hoy + timedelta(days=dias)

        fechas_fijas = self._fechas_fijas_en_ventana(hoy, limite)

        enviados = 0
        for usuario in User.objects.exclude(email='').filter(is_active=True):
            eventos_propios = list(
                EventoCalendario.objects
                .filter(usuario=usuario, fecha__gte=hoy, fecha__lte=limite)
                .order_by('fecha')
            )

            if not fechas_fijas and not eventos_propios:
                continue

            cuerpo = self._armar_cuerpo(usuario, fechas_fijas, eventos_propios, hoy)
            send_mail(
                subject='Recordatorio fiscal — TributIA',
                message=cuerpo,
                from_email=None,  # usa DEFAULT_FROM_EMAIL
                recipient_list=[usuario.email],
                fail_silently=False,
            )
            enviados += 1

        logger.info('recordatorios_fiscales_enviados', extra={'total': enviados, 'dias': dias})
        self.stdout.write(self.style.SUCCESS(f'{enviados} correo(s) de recordatorio enviado(s).'))

    def _fechas_fijas_en_ventana(self, hoy, limite):
        candidatas = []
        for mes_offset in range(2):
            mes = (hoy.month - 1 + mes_offset) % 12 + 1
            anio = hoy.year + ((hoy.month - 1 + mes_offset) // 12)
            for ev in fechas_fiscales_mes(anio, mes):
                fecha_ev = date(anio, mes, ev['day'])
                if hoy <= fecha_ev <= limite:
                    candidatas.append({'titulo': ev['titulo'], 'fecha': fecha_ev})
        candidatas.sort(key=lambda e: e['fecha'])
        return candidatas

    def _armar_cuerpo(self, usuario, fechas_fijas, eventos_propios, hoy):
        lineas = [
            f'Hola {usuario.get_full_name() or usuario.username},',
            '',
            'Estas son tus próximas fechas fiscales en TributIA:',
            '',
        ]
        for f in fechas_fijas:
            dias_restantes = (f['fecha'] - hoy).days
            lineas.append(f"- {f['titulo']}: {f['fecha'].strftime('%d/%m/%Y')} ({dias_restantes} día(s))")
        for e in eventos_propios:
            dias_restantes = (e.fecha - hoy).days
            lineas.append(f"- {e.titulo}: {e.fecha.strftime('%d/%m/%Y')} ({dias_restantes} día(s))")

        lineas += ['', 'Revisa tu calendario fiscal en TributIA para más detalle.']
        return '\n'.join(lineas)
