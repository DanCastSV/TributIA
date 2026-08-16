"""
Fechas fiscales fijas de El Salvador (ISR mensual, IVA F-07, Renta F-11,
cierre de ejercicio). Punto único de verdad: lo usan tanto la vista del
calendario (core/views.py) como el comando de recordatorios por email
(core/management/commands/enviar_recordatorios_fiscales.py).
"""

import calendar as cal_lib


def fechas_fiscales_mes(year, month):
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
