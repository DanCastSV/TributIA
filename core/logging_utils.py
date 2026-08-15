"""
Formatter de logging que serializa cada línea como JSON, para que los
logs sean legibles por máquina (grep/jq) y por humanos a la vez. Toma
cualquier campo pasado vía logger.info(..., extra={...}) y lo agrega tal
cual al JSON de salida, junto con los campos estándar (timestamp, nivel,
logger, mensaje) y el request_id inyectado por RequestIdFilter.
"""

import json
import logging

_CAMPOS_RESERVADOS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}


class JSONFormatter(logging.Formatter):
    def format(self, record):
        datos = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }

        for clave, valor in vars(record).items():
            if clave not in _CAMPOS_RESERVADOS:
                datos[clave] = valor

        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)

        return json.dumps(datos, ensure_ascii=False, default=str)
