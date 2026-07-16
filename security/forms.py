from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User, Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import UserProfile

ROLE_GROUP_MAP = {
    'administrador': 'Administrador',
    'gerente': 'Gerente',
    'vendedor': 'Ventas',
    'comprador': 'Compras',
}
ROLE_LABELS = {
    'administrador': 'Administrador',
    'gerente': 'Gerente',
    'vendedor': 'Vendedor',
    'comprador': 'Comprador',
}


class RoleAwareAuthenticationForm(AuthenticationForm):
    """AuthenticationForm que, tras verificar usuario/contraseña, da un mensaje
    específico según el caso: cuenta inactiva, cuenta sin rol asignado, o rol
    seleccionado en la pantalla de perfiles que no coincide con el grupo real
    del usuario. Los superusuarios quedan exentos de las dos últimas."""

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError(
                'Tu cuenta aún no ha sido activada. Un administrador debe aprobar tu '
                'solicitud de acceso antes de que puedas ingresar.',
                code='inactive',
            )
        if not user.is_superuser and not user.groups.exists():
            raise ValidationError(
                'Tu cuenta no tiene un rol asignado todavía. Contacta a un '
                'administrador para que te asigne uno.',
                code='no_role',
            )
        role = self.request.GET.get('role') if self.request else None
        if role and not user.is_superuser:
            group_name = ROLE_GROUP_MAP.get(role)
            if group_name and not user.groups.filter(name=group_name).exists():
                raise ValidationError(
                    f'Esta cuenta no pertenece al perfil "{ROLE_LABELS.get(role, role)}". '
                    'Elige el perfil correcto o inicia sesión con la cuenta correspondiente.',
                    code='role_mismatch',
                )


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tu@correo.com', 'autocomplete': 'email'}),
    )


class PasswordResetCodeForm(forms.Form):
    code = forms.CharField(
        label='Código de verificación',
        max_length=6, min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': '000000', 'autocomplete': 'one-time-code',
            'inputmode': 'numeric', 'pattern': '[0-9]{6}',
        }),
    )
    new_password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mínimo 8 caracteres', 'autocomplete': 'new-password'}),
    )
    new_password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repite la contraseña', 'autocomplete': 'new-password'}),
    )

    def clean_code(self):
        code = self.cleaned_data.get('code', '')
        if not code.isdigit():
            raise ValidationError('El código debe tener 6 dígitos.')
        return code

    def clean_new_password2(self):
        p1 = self.cleaned_data.get('new_password1')
        p2 = self.cleaned_data.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError('Las contraseñas no coinciden.')
        if p1:
            validate_password(p1)
        return p2


class LoginOTPForm(forms.Form):
    code = forms.CharField(
        label='Código de WhatsApp',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'autofocus': True,
        }),
    )

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code.isdigit() or len(code) != 6:
            raise ValidationError('El código debe tener exactamente 6 dígitos.')
        return code


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True, label='Nombres')
    last_name = forms.CharField(max_length=100, required=True, label='Apellidos')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_active = False
        if commit:
            user.save()
        return user


_INPUT  = {'class': 'form-control'}
_SELECT = {'class': 'form-select'}
_PWD    = {'class': 'form-control'}


def _normalizar_telefono(valor: str) -> str:
    return ''.join(c for c in (valor or '') if c.isdigit())


class UserCreateForm(forms.ModelForm):
    group = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by('name'),
        label='Grupo / Rol',
        empty_label='Sin grupo',
        widget=forms.Select(attrs=_SELECT),
    )
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={**_PWD, 'placeholder': 'Mínimo 8 caracteres'}),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={**_PWD, 'placeholder': 'Repite la contraseña'}),
    )
    phone = forms.CharField(
        label='Teléfono WhatsApp',
        required=True,
        max_length=15,
        widget=forms.TextInput(attrs={
            **_INPUT,
            'placeholder': 'Ej: 0991234567',
            'inputmode': 'numeric',
            'autocomplete': 'tel',
        }),
        help_text='Se usará para enviar el código de autenticación en dos pasos.',
    )
    two_factor_enabled = forms.BooleanField(
        label='Autenticación en dos pasos (WhatsApp)',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')
        widgets = {
            'username':   forms.TextInput(attrs={**_INPUT, 'placeholder': 'Nombre de usuario'}),
            'first_name': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Nombres'}),
            'last_name':  forms.TextInput(attrs={**_INPUT, 'placeholder': 'Apellidos'}),
            'email':      forms.EmailInput(attrs={**_INPUT, 'placeholder': 'correo@ejemplo.com'}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean_phone(self):
        phone = _normalizar_telefono(self.cleaned_data.get('phone', ''))
        if len(phone) < 9:
            raise ValidationError('Ingresa un número de teléfono válido (mín. 9 dígitos).')
        return phone

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('two_factor_enabled') and not cleaned.get('phone'):
            self.add_error('phone', 'El teléfono es obligatorio si activas la autenticación en dos pasos.')
        return cleaned

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError('Las contraseñas no coinciden.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            group = self.cleaned_data.get('group')
            user.groups.set([group] if group else [])
            phone = self.cleaned_data.get('phone') or ''
            two_fa = bool(self.cleaned_data.get('two_factor_enabled')) and bool(phone)
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'phone': phone, 'two_factor_enabled': two_fa},
            )
        return user


class UserEditForm(forms.ModelForm):
    group = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by('name'),
        label='Grupo / Rol',
        required=False,
        empty_label='Sin grupo',
        widget=forms.Select(attrs=_SELECT),
    )
    new_password = forms.CharField(
        label='Nueva contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={**_PWD, 'placeholder': 'Dejar en blanco para no cambiar'}),
    )
    phone = forms.CharField(
        label='Teléfono WhatsApp',
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            **_INPUT,
            'placeholder': 'Ej: 0991234567',
            'inputmode': 'numeric',
            'autocomplete': 'tel',
        }),
    )
    two_factor_enabled = forms.BooleanField(
        label='Autenticación en dos pasos (WhatsApp)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'is_active')
        widgets = {
            'first_name': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Nombres'}),
            'last_name':  forms.TextInput(attrs={**_INPUT, 'placeholder': 'Apellidos'}),
            'email':      forms.EmailInput(attrs={**_INPUT, 'placeholder': 'correo@ejemplo.com'}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['group'].initial = self.instance.groups.first()
            profile = getattr(self.instance, 'profile', None)
            if profile:
                self.fields['phone'].initial = profile.phone
                self.fields['two_factor_enabled'].initial = profile.two_factor_enabled

    def clean_phone(self):
        phone = _normalizar_telefono(self.cleaned_data.get('phone', ''))
        if phone and len(phone) < 9:
            raise ValidationError('Ingresa un número de teléfono válido (mín. 9 dígitos).')
        return phone

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('two_factor_enabled') and not cleaned.get('phone'):
            self.add_error(
                'phone',
                'Para activar la autenticación en dos pasos debes registrar un teléfono WhatsApp.',
            )
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get('new_password')
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
            group = self.cleaned_data.get('group')
            user.groups.set([group] if group else [])
            phone = self.cleaned_data.get('phone') or ''
            two_fa = bool(self.cleaned_data.get('two_factor_enabled')) and bool(phone)
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'phone': phone, 'two_factor_enabled': two_fa},
            )
        return user
