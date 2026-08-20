from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from .forms import LoginForm, SolicitudResetPasswordForm, NuevaPasswordForm


urlpatterns = [
    path('', views.home, name='home'),
    path('registro/', views.registro, name='registro'),
    path(
    'login/',
    LoginView.as_view(
        template_name='login.html',
        authentication_form=LoginForm
    ),
    name='login'
),
    path(
    'dashboard/', views.dashboard, name='dashboard'),
    path(
    'logout/', LogoutView.as_view(), name='logout'),
    path(
    'password-reset/',
    auth_views.PasswordResetView.as_view(
        template_name='password_reset.html',
        form_class=SolicitudResetPasswordForm
    ),
    name='password_reset'
),

path(
    'password-reset/done/',
    auth_views.PasswordResetDoneView.as_view(
        template_name='password_reset_done.html'
    ),
    name='password_reset_done'
),

path(
    'reset/<uidb64>/<token>/',
    auth_views.PasswordResetConfirmView.as_view(
        template_name='password_reset_confirm.html',
        form_class=NuevaPasswordForm
    ),
    name='password_reset_confirm'
),

path(
    'reset/done/',
    auth_views.PasswordResetCompleteView.as_view(
        template_name='password_reset_complete.html'
    ),
    name='password_reset_complete'
),
path(
    'perfil/',
    views.perfil,
    name='perfil'
),


path(
    'perfil/editar/',
    views.editar_perfil,
    name='editar_perfil'
),

path(
    'documentos/',
    views.documentos,
    name='documentos'
),

path(
    'documentos/lote/',
    views.subir_documentos_lote,
    name='subir_documentos_lote'
),

path(
    'documento/<int:documento_id>/',
    views.detalle_documento,
    name='detalle_documento'
),

path(
    'documento/<int:documento_id>/eliminar/',
    views.eliminar_documento,
    name='eliminar_documento'
),

path(
    'documentos/eliminar-seleccionados/',
    views.eliminar_documentos_seleccionados,
    name='eliminar_documentos_seleccionados'
),

path(
    'documentos/eliminar-todos/',
    views.eliminar_todos_documentos,
    name='eliminar_todos_documentos'
),

path(
    'documento/<int:documento_id>/descargar/',
    views.descargar_documento,
    name='descargar_documento'
),

path(
    'documento/<int:documento_id>/feedback/',
    views.enviar_feedback_analisis,
    name='enviar_feedback_analisis'
),
path(
    'centro-analisis/',
    views.centro_analisis,
    name='centro_analisis'
),

path(
    'centro-analisis/reporte/',
    views.reporte_anual_pdf,
    name='reporte_anual_pdf'
),

path(
    'centro-analisis/exportar/',
    views.exportar_analisis_csv,
    name='exportar_analisis_csv'
),
path(
    'calendario/',
    views.calendario,
    name='calendario'
),

path(
    'asistente-ia/',
    views.asistente_ia,
    name='asistente_ia'
),

path(
    'api/conversacion/nueva/',
    views.nueva_conversacion,
    name='nueva_conversacion'
),

path(
    'api/chat/mensaje/',
    views.enviar_mensaje,
    name='enviar_mensaje'
),

path(
    'api/conversacion/<int:conversacion_id>/eliminar/',
    views.eliminar_conversacion,
    name='eliminar_conversacion'
),

path(
    'recursos-fiscales/',
    views.recursos_fiscales,
    name='recursos_fiscales'
),

path(
    'como-funciona/',
    views.como_funciona,
    name='como_funciona'
),

path(
    'api/calendario/evento/crear/',
    views.crear_evento,
    name='crear_evento'
),

path(
    'api/calendario/evento/<int:evento_id>/eliminar/',
    views.eliminar_evento,
    name='eliminar_evento'
),

path(
    'uso-gemini/',
    views.uso_gemini_resumen,
    name='uso_gemini_resumen'
),

]
if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
