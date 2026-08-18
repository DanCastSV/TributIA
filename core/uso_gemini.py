"""
Registra cuántos tokens consume cada llamada a Gemini, por usuario, para
poder ver el gasto de cuota por perfil (Google solo expone un total
agregado por proyecto, no desglosado por usuario de la app).

registrar_uso_gemini() se llama justo después de cada respuesta exitosa
de Gemini (análisis de documento y chat del asistente). Nunca debe poder
romper el flujo principal: si `usuario` es None, o la respuesta no trae
`usage_metadata` (puede pasar con mocks en tests, o si el SDK cambia),
simplemente no registra nada y sigue.
"""

import logging

from core.models import UsoGemini

logger = logging.getLogger(__name__)


def registrar_uso_gemini(usuario, tipo, response):
    if usuario is None:
        return

    try:
        uso = response.usage_metadata
        UsoGemini.objects.create(
            usuario=usuario,
            tipo=tipo,
            tokens_entrada=uso.prompt_token_count or 0,
            tokens_salida=uso.candidates_token_count or 0,
            tokens_total=uso.total_token_count or 0,
        )
    except Exception as e:
        logger.warning(
            'registro_uso_gemini_fallido',
            extra={'tipo_error': type(e).__name__},
        )
