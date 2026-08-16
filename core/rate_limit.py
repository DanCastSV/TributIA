import hashlib
import ipaddress
import time
from functools import wraps

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse


_PROXY_CIDRS_POR_DEFECTO = ('127.0.0.0/8', '::1/128')


def _ip_valida(valor):
    try:
        return str(ipaddress.ip_address(valor.strip()))
    except (AttributeError, ValueError):
        return None


def _proxy_confiable(ip_remota):
    ip = _ip_valida(ip_remota)
    if ip is None:
        return False

    redes = getattr(settings, 'TRIBUTIA_TRUSTED_PROXY_CIDRS', _PROXY_CIDRS_POR_DEFECTO)
    try:
        direccion = ipaddress.ip_address(ip)
        return any(direccion in ipaddress.ip_network(red, strict=False) for red in redes)
    except ValueError:
        return False


def _ip_cliente(request):
    """Acepta XFF únicamente desde un proxy directo explícitamente confiable."""
    remota = _ip_valida(request.META.get('REMOTE_ADDR', ''))
    if remota is None:
        return 'desconocida'

    reenviadas = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if reenviadas and _proxy_confiable(remota):
        # El proxy confiable agrega la dirección observada al final de la cadena.
        # Tomar la última evita que el cliente elija el primer XFF arbitrariamente.
        for candidata in reversed(reenviadas.split(',')):
            normalizada = _ip_valida(candidata)
            if normalizada is not None:
                return normalizada
    return remota


def _identificador(request, clave):
    if clave == 'usuario' and request.user.is_authenticated:
        valor = f'usuario:{request.user.pk}'
    else:
        valor = f'ip:{_ip_cliente(request)}'
    return hashlib.sha256(valor.encode('utf-8')).hexdigest()


def _incrementar_contador(ambito, identificador, cubeta):
    """Incrementa atómicamente una cubeta compartida en PostgreSQL/SQLite."""
    llave = hashlib.sha256(f'{ambito}:{identificador}'.encode('utf-8')).hexdigest()
    consulta = '''
        INSERT INTO core_ratelimitbucket (identificador, cubeta, contador)
        VALUES (%s, %s, 1)
        ON CONFLICT (identificador) DO UPDATE SET
            contador = CASE
                WHEN core_ratelimitbucket.cubeta = excluded.cubeta
                THEN core_ratelimitbucket.contador + 1
                ELSE 1
            END,
            cubeta = excluded.cubeta
        RETURNING contador
    '''
    with connection.cursor() as cursor:
        cursor.execute(consulta, [llave, cubeta])
        return int(cursor.fetchone()[0])


def limitar_solicitudes(*, ambito, limite, ventana_segundos, clave='ip', json=False, metodos=('POST',)):
    """Límite compartido por DB, sin Redis ni contadores por worker."""
    def decorador(vista):
        @wraps(vista)
        def envuelta(request, *args, **kwargs):
            if request.method not in metodos:
                return vista(request, *args, **kwargs)

            ahora = int(time.time())
            cubeta = ahora // ventana_segundos
            identificador = _identificador(request, clave)
            contador = _incrementar_contador(ambito, identificador, cubeta)

            if contador <= limite:
                return vista(request, *args, **kwargs)

            reintentar = max(1, ventana_segundos - (ahora % ventana_segundos))
            if json:
                respuesta = JsonResponse(
                    {
                        'error': 'demasiadas_solicitudes',
                        'detalle': 'Has realizado demasiadas solicitudes. Inténtalo más tarde.',
                    },
                    status=429,
                )
            else:
                respuesta = HttpResponse(
                    'Has realizado demasiadas solicitudes. Inténtalo más tarde.',
                    status=429,
                    content_type='text/plain; charset=utf-8',
                )
            respuesta['Retry-After'] = str(reintentar)
            return respuesta

        return envuelta
    return decorador
