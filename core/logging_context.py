"""
Correlación de logs por solicitud (request_id).

Usa contextvars en vez de pasar request_id como parámetro por cada
función de core/services e core/ia, para no ensuciar sus firmas. El
middleware fija el valor al inicio de cada request; el filtro lo inyecta
automáticamente en cualquier log emitido durante esa misma request,
incluido dentro del pipeline de análisis (analizador.py) y los logs
internos de Django.
"""

import contextvars
import logging

request_id_var = contextvars.ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True
