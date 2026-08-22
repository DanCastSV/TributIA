"""
Verificación de correo al registrarse (Fase 2 del patrón NovaTareas).

El token crudo se genera con secrets.token_hex (32 bytes = 64 hex),
solo vive en el enlace del correo enviado; en la base de datos se
guarda únicamente su hash sha256. La ventana de expiración y el
requisito de verificación para poder iniciar sesión son configurables
por variable de entorno (ver settings.py).
"""

import hashlib
import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta

from core.models import EmailVerificationToken

logger = logging.getLogger(__name__)

HORAS_EXPIRACION = getattr(settings, 'EMAIL_VERIFICATION_TOKEN_HORAS', 48)


def _hash_token(token_crudo):
    return hashlib.sha256(token_crudo.encode('utf-8')).hexdigest()


def generar_token_verificacion(usuario):
    """Crea el registro del token y devuelve el valor crudo (para el enlace)."""
    token_crudo = secrets.token_hex(32)
    EmailVerificationToken.objects.create(
        token_hash=_hash_token(token_crudo),
        usuario=usuario,
        expires_at=timezone.now() + timedelta(hours=HORAS_EXPIRACION),
    )
    return token_crudo


def enviar_correo_verificacion(usuario, url_verificacion):
    """
    Envía el correo de verificación. Fail-safe: si el SMTP falla o no
    está configurado, no lanza excepción — devuelve False para que el
    caller decida qué hacer (en el registro, se usa para revertir la
    cuenta recién creada en vez de dejarla huérfana sin forma de
    verificarse).
    """
    cuerpo = (
        f"Hola {usuario.get_full_name() or usuario.username},\n\n"
        "Gracias por registrarte en TributIA. Confirmá tu correo entrando a este enlace:\n\n"
        f"{url_verificacion}\n\n"
        f"El enlace expira en {HORAS_EXPIRACION} horas. "
        "Si no creaste esta cuenta, podés ignorar este correo."
    )
    try:
        enviados = send_mail(
            subject="Verificá tu correo — TributIA",
            message=cuerpo,
            from_email=None,  # usa DEFAULT_FROM_EMAIL
            recipient_list=[usuario.email],
            fail_silently=False,
        )
        return enviados > 0
    except Exception as e:
        logger.error(
            "envio_correo_verificacion_fallido",
            extra={"usuario_id": usuario.id, "tipo_error": type(e).__name__},
        )
        return False


def verificar_token(token_crudo):
    """
    Consume un token (uso único, no expirado) y marca el perfil como
    verificado. Devuelve (True, usuario) si fue válido, (False, None)
    si no existe, ya se usó o expiró.
    """
    if not token_crudo:
        return False, None

    token_hash = _hash_token(token_crudo)
    ahora = timezone.now()

    actualizados = EmailVerificationToken.objects.filter(
        token_hash=token_hash,
        used_at__isnull=True,
        expires_at__gt=ahora,
    ).update(used_at=ahora)

    if not actualizados:
        return False, None

    registro = EmailVerificationToken.objects.select_related('usuario__perfiltributario').get(
        token_hash=token_hash
    )
    perfil = registro.usuario.perfiltributario
    perfil.email_verified_at = ahora
    perfil.save(update_fields=['email_verified_at'])

    return True, registro.usuario
