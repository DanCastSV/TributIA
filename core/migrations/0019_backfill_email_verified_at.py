"""
Backfill: los perfiles creados antes de esta función quedan marcados
como verificados (con la fecha de creación de su cuenta de usuario) —
de lo contrario, activar EMAIL_VERIFICATION_REQUIRED bloquearía a todo
el mundo que ya se había registrado antes de que esto existiera.
"""

from django.db import migrations


def backfill_verificados(apps, schema_editor):
    PerfilTributario = apps.get_model('core', 'PerfilTributario')
    for perfil in PerfilTributario.objects.filter(email_verified_at__isnull=True).select_related('usuario'):
        perfil.email_verified_at = perfil.usuario.date_joined
        perfil.save(update_fields=['email_verified_at'])


def revertir_backfill(apps, schema_editor):
    # No reversible de forma segura (no se puede distinguir un backfill
    # de una verificación real posterior) — no-op a propósito.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_perfiltributario_email_verified_at_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_verificados, revertir_backfill),
    ]
