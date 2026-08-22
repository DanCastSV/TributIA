from django.contrib import admin
from .models import DocumentoTributario, AnalisisDocumento, EmailVerificationToken, UsoGemini

admin.site.register(DocumentoTributario)
admin.site.register(AnalisisDocumento)


@admin.register(UsoGemini)
class UsoGeminiAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'tokens_entrada', 'tokens_salida', 'tokens_total', 'creado_en')
    list_filter = ('tipo', 'creado_en')
    search_fields = ('usuario__username',)
    ordering = ('-creado_en',)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'expires_at', 'used_at', 'created_at')
    list_filter = ('used_at',)
    search_fields = ('usuario__username', 'usuario__email')
    ordering = ('-created_at',)
    readonly_fields = ('token_hash',)

# Register your models here.
