from django.contrib import admin
from .models import DocumentoTributario, AnalisisDocumento, UsoGemini

admin.site.register(DocumentoTributario)
admin.site.register(AnalisisDocumento)


@admin.register(UsoGemini)
class UsoGeminiAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'tokens_entrada', 'tokens_salida', 'tokens_total', 'creado_en')
    list_filter = ('tipo', 'creado_en')
    search_fields = ('usuario__username',)
    ordering = ('-creado_en',)

# Register your models here.
