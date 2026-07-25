from django.urls import path

from . import api_views

urlpatterns = [
    path('health/', api_views.health, name='api_health'),
    path('metadata/', api_views.metadata, name='api_metadata'),
    path('analizar-documento/', api_views.analizar_documento_api, name='api_analizar_documento'),
]
