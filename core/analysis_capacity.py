import fcntl
import logging
import os
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

_LOCK_BASE = int('5452494255544900', 16)
_LOCK_DIR = Path('/tmp/tributia-analysis-capacity')
_MAXIMO_PERMITIDO = 8


class CapacidadAnalisisAgotada(Exception):
    """No hay un slot libre para OCR/Gemini en este momento."""


def _limite_configurado():
    valor = int(getattr(settings, 'TRIBUTIA_MAX_ANALISIS_CONCURRENTES', 2))
    return max(1, min(valor, _MAXIMO_PERMITIDO))


@contextmanager
def _reservar_postgresql(limite):
    lock_id = None
    with connection.cursor() as cursor:
        for indice in range(limite):
            candidato = _LOCK_BASE + indice
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [candidato])
            if cursor.fetchone()[0]:
                lock_id = candidato
                break

    if lock_id is None:
        raise CapacidadAnalisisAgotada

    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [lock_id])
            liberado = cursor.fetchone()[0]
        if not liberado:
            logger.warning('slot_analisis_no_liberado')


@contextmanager
def _reservar_archivo(limite):
    """Fallback local para desarrollo SQLite; producción usa PostgreSQL."""
    _LOCK_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = None
    try:
        for indice in range(limite):
            ruta = _LOCK_DIR / f'slot-{indice}.lock'
            candidato = os.open(ruta, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(candidato, fcntl.LOCK_EX | fcntl.LOCK_NB)
                descriptor = candidato
                break
            except BlockingIOError:
                os.close(candidato)
        if descriptor is None:
            raise CapacidadAnalisisAgotada
        yield
    finally:
        if descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


@contextmanager
def reservar_capacidad_analisis():
    """Reserva sin espera un slot global para OCR/Gemini.

    En PostgreSQL, advisory locks coordinan todos los workers y futuros
    contenedores que compartan la misma base. Si los slots están ocupados,
    el caller debe responder 429 con Retry-After en vez de saturar Gunicorn.
    """
    limite = _limite_configurado()
    if connection.vendor == 'postgresql':
        with _reservar_postgresql(limite):
            yield
    else:
        with _reservar_archivo(limite):
            yield
