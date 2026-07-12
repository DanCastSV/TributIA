from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.forms import ModelForm
from .models import PerfilTributario
from .models import DocumentoTributario



class RegistroUsuarioForm(UserCreationForm):

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'input-modern',
            'placeholder': 'correo@ejemplo.com',
            'autocomplete': 'email',
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'input-modern',
            'placeholder': 'Nombre de usuario',
            'autocomplete': 'username',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'input-modern',
            'placeholder': 'Contraseña',
            'autocomplete': 'new-password',
            'id': 'id_password1',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'input-modern',
            'placeholder': 'Confirmar contraseña',
            'autocomplete': 'new-password',
        })
        # Quitar el help_text por defecto de Django (se muestra en la UI propia)
        self.fields['username'].help_text = ''
        self.fields['password1'].help_text = ''
        self.fields['password2'].help_text = ''

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo electrónico.')
        return email

class PerfilTributarioForm(ModelForm):

    class Meta:

        model = PerfilTributario

        fields = [
            'dui',
            'nit',
            'telefono',
            'salario_mensual',
            'actividad_economica',
            'tipo_contribuyente'
        ]

        widgets = {
            'dui': forms.TextInput(attrs={'class': 'input-modern'}),
            'nit': forms.TextInput(attrs={'class': 'input-modern'}),
            'telefono': forms.TextInput(attrs={'class': 'input-modern'}),
            'salario_mensual': forms.NumberInput(attrs={'class': 'input-modern'}),
            'actividad_economica': forms.TextInput(attrs={'class': 'input-modern'}),
            'tipo_contribuyente': forms.Select(attrs={'class': 'input-modern'}),
        }

class DocumentoForm(forms.ModelForm):

    class Meta:

        model = DocumentoTributario

        fields = [
            'nombre',
            'archivo'
        ]

        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'input-modern',
                'placeholder': 'Nombre del documento'
            }),
            'archivo': forms.ClearableFileInput(attrs={
                'class': 'visually-hidden-file-input',
                'id': 'id_archivo',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
        }

from django.contrib.auth.forms import AuthenticationForm
from django import forms

class LoginForm(AuthenticationForm):

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'input-modern',
                'placeholder': 'Usuario'
            }
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'input-modern',
                'placeholder': 'Contraseña'
            }
        )
    )