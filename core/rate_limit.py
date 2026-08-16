import hashlib
import time
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


def _ip_cliente(request):
    # La aplicación solo escucha detrás del proxy declarado; Caddy reemplaza
    # X-Forwarded-For. Se conserva REMOTE_ADDR como fallback local.
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if reenviada:
        return reenviada.split(',', 1)[0].strip()
    return request.META.get('REMOTE_ADDR', 'desconocida')


def _identificador(request, clave):
    if clave == 'usuario' and request.user.is_authenticated:
        valor = f'usuario:{request.user.pk}'
    else:
        valor = f'ip:{_ip_cliente(request)}'
    return hashlib.sha256(valor.encode('utf-8')).hexdigest()


def limitar_solicitudes(*, ambito, limite, ventana_segundos, clave='ip', json=False, metodos=('POST',)):
    """Límite ligero para la demo, sin Redis ni servicios adicionales.

    Django LocMemCache mantiene un contador por worker. En producción hay tres
    workers, así que este control es deliberadamente conservador y se combina
    con Cloudflare/Caddy; evita ráfagas accidentales sin añadir infraestructura.
    """
    def decorador(vista):
        @wraps(vista)
        def envuelta(request, *args, **kwargs):
            if request.method not in metodos:
                return vista(request, *args, **kwargs)

            ahora = int(time.time())
            cubeta = ahora // ventana_segundos
            identificador = _identificador(request, clave)
            llave = f'tributia:rate:{ambito}:{identificador}:{cubeta}'

            if cache.add(llave, 1, timeout=ventana_segundos + 5):
                contador = 1
            else:
                try:
                    contador = cache.incr(llave)
                except ValueError:
                    cache.set(llave, 1, timeout=ventana_segundos + 5)
                    contador = 1

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
