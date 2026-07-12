from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from .forms import LoginForm


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
        template_name='password_reset.html'
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
        template_name='password_reset_confirm.html'
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
    'centro-analisis/',
    views.centro_analisis,
    name='centro_analisis'
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
    'api/calendario/evento/crear/',
    views.crear_evento,
    name='crear_evento'
),

path(
    'api/calendario/evento/<int:evento_id>/eliminar/',
    views.eliminar_evento,
    name='eliminar_evento'
),

]
if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
