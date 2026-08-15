"""
Middleware de observabilidad (Semana 5): registra un evento por cada
request con request_id, ruta, método, status y duración total. No
registra cuerpo, headers, cookies ni querystring — evita loguear datos
sensibles (sesión, CSRF token, contraseñas, archivos subidos).
"""

import logging
import time
import uuid

from core.logging_context import request_id_var

logger = logging.getLogger("tributia.requests")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)
        request.request_id = request_id
        inicio = time.monotonic()

        try:
            response = self.get_response(request)

            duracion_ms = round((time.monotonic() - inicio) * 1000, 1)
            response["X-Request-ID"] = request_id

            nivel = logging.INFO if response.status_code < 500 else logging.ERROR
            logger.log(
                nivel,
                "request_completada",
                extra={
                    "request_id": request_id,
                    "metodo": request.method,
                    "ruta": request.path,
                    "status": response.status_code,
                    "duracion_ms": duracion_ms,
                },
            )

            return response
        finally:
            # Se resetea después de loguear: el filtro que inyecta
            # request_id en cada log (core/logging_context.py) lee esta
            # contextvar, así que si se resetea antes del logger.log()
            # de arriba, ese log específico queda con request_id=None.
            request_id_var.reset(token)
