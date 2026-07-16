from django.apps import apps
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.views import LoginView
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from billing.whatsapp_client import WhatsAppServiceError
from shared.decorators import staff_required
from .emails import send_password_reset_code_email
from .forms import (LoginOTPForm, PasswordResetCodeForm, PasswordResetRequestForm,
                     RoleAwareAuthenticationForm, SignUpForm, UserCreateForm, UserEditForm)
from .models import LOGIN_OTP_VALID_MINUTES, LoginOTPCode, PasswordResetCode
from .whatsapp import send_login_otp_whatsapp


def _user_requiere_2fa(user) -> bool:
    try:
        return user.profile.requiere_2fa()
    except Exception:
        return False


def _iniciar_2fa(request, user, next_url: str):
    """Genera OTP, lo guarda en BD, lo envía por WhatsApp y deja al usuario pendiente en sesión."""
    otp = LoginOTPCode.generar_para(user)
    send_login_otp_whatsapp(user, otp)
    request.session['pending_2fa_user_id'] = user.pk
    request.session['pending_2fa_next'] = next_url or '/'


class RoleAwareLoginView(LoginView):
    form_class = RoleAwareAuthenticationForm

    def form_valid(self, form):
        user = form.get_user()
        if _user_requiere_2fa(user):
            next_url = self.get_redirect_url() or '/'
            try:
                _iniciar_2fa(self.request, user, next_url)
            except WhatsAppServiceError as e:
                messages.error(
                    self.request,
                    f'No se pudo enviar el código por WhatsApp: {e}. '
                    '¿Está corriendo whatsapp_service y el WhatsApp vinculado?',
                )
                return redirect('login')
            except Exception:
                messages.error(
                    self.request,
                    'No se pudo enviar el código por WhatsApp. Verifica el microservicio (:5004).',
                )
                return redirect('login')
            messages.success(
                self.request,
                'Te enviamos un código temporal a tu WhatsApp. Ingrésalo para continuar.',
            )
            return redirect('security:login_2fa')
        return super().form_valid(form)


@require_http_methods(['GET', 'POST'])
def login_2fa(request):
    """Paso 2 del login: validar código OTP recibido por WhatsApp."""
    user_id = request.session.get('pending_2fa_user_id')
    if not user_id:
        messages.error(request, 'Primero inicia sesión con tu usuario y contraseña.')
        return redirect('login')

    user = User.objects.filter(pk=user_id, is_active=True).select_related('profile').first()
    if not user or not _user_requiere_2fa(user):
        request.session.pop('pending_2fa_user_id', None)
        request.session.pop('pending_2fa_next', None)
        messages.error(request, 'La verificación en dos pasos no está disponible para esta cuenta.')
        return redirect('login')

    profile = user.profile
    phone_mask = profile.telefono_enmascarado()

    if request.method == 'POST' and request.POST.get('action') == 'resend':
        try:
            _iniciar_2fa(request, user, request.session.get('pending_2fa_next', '/'))
            messages.success(request, 'Te reenviamos un nuevo código por WhatsApp.')
        except WhatsAppServiceError as e:
            messages.error(request, f'No se pudo reenviar el código: {e}')
        except Exception:
            messages.error(request, 'No se pudo reenviar el código. Revisa whatsapp_service.')
        return redirect('security:login_2fa')

    if request.method == 'POST':
        form = LoginOTPForm(request.POST)
        if form.is_valid():
            otp = LoginOTPCode.objects.filter(
                user=user,
                code=form.cleaned_data['code'],
                used=False,
            ).order_by('-created_at').first()
            if not otp or not otp.is_valid():
                form.add_error('code', 'El código es incorrecto o ya venció. Solicita uno nuevo.')
            else:
                otp.used = True
                otp.save(update_fields=['used'])
                next_url = request.session.pop('pending_2fa_next', '/') or '/'
                request.session.pop('pending_2fa_user_id', None)
                auth_login(request, user)
                messages.success(request, f'Bienvenido, {user.get_full_name() or user.username}.')
                return redirect(next_url)
    else:
        form = LoginOTPForm()

    return render(request, 'registration/login_2fa.html', {
        'form': form,
        'phone_mask': phone_mask,
        'username': user.username,
        'valid_minutes': LOGIN_OTP_VALID_MINUTES,
    })


def role_select(request):
    return render(request, 'registration/role_select.html')


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Tu cuenta fue creada. Un administrador debe activarla y asignarte un rol antes de que puedas ingresar.',
            )
            return redirect('login')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


def password_reset_request(request):
    """Paso 1: el usuario ingresa su correo y, si existe una cuenta activa
    con ese correo, se le envía un código de 6 dígitos. Por seguridad se
    muestra siempre el mismo mensaje, exista o no la cuenta, para no revelar
    qué correos están registrados."""
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user:
                reset_code = PasswordResetCode.generar_para(user)
                try:
                    send_password_reset_code_email(user, reset_code)
                except Exception:
                    messages.error(request, 'No se pudo enviar el correo. Intenta de nuevo más tarde.')
                    return render(request, 'registration/password_reset_request.html', {'form': form})
            request.session['password_reset_email'] = email
            messages.success(request, 'Si el correo está registrado, te enviamos un código de verificación.')
            return redirect('security:password_reset_verify')
    else:
        form = PasswordResetRequestForm()
    return render(request, 'registration/password_reset_request.html', {'form': form})


def password_reset_verify(request):
    """Paso 2: el usuario ingresa el código recibido y su nueva contraseña."""
    email = request.session.get('password_reset_email')
    if not email:
        messages.error(request, 'Primero solicita un código de restablecimiento.')
        return redirect('security:password_reset_request')
    if request.method == 'POST':
        form = PasswordResetCodeForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            reset_code = None
            if user:
                reset_code = PasswordResetCode.objects.filter(
                    user=user, code=form.cleaned_data['code'], used=False,
                ).order_by('-created_at').first()
            if not reset_code or not reset_code.is_valid():
                form.add_error('code', 'El código es incorrecto o ya venció. Solicita uno nuevo.')
            else:
                user.set_password(form.cleaned_data['new_password1'])
                user.save()
                reset_code.used = True
                reset_code.save(update_fields=['used'])
                del request.session['password_reset_email']
                messages.success(request, 'Tu contraseña fue restablecida. Ya puedes iniciar sesión.')
                return redirect('login')
    else:
        form = PasswordResetCodeForm()
    return render(request, 'registration/password_reset_verify.html', {'form': form, 'email': email})


# ── Usuarios ───────────────────────────────────────────────────────────────

@staff_required
def user_list(request):
    qs = User.objects.prefetch_related('groups').order_by('username')
    q         = request.GET.get('q', '').strip()
    group_id  = request.GET.get('group', '')
    status    = request.GET.get('status', '')
    if q:
        qs = qs.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) |
            Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if group_id:
        qs = qs.filter(groups__id=group_id)
    if status == '1':
        qs = qs.filter(is_active=True)
    elif status == '0':
        qs = qs.filter(is_active=False)

    all_groups  = Group.objects.annotate(user_count=Count('user')).order_by('name')
    total       = User.objects.count()
    total_active   = User.objects.filter(is_active=True).count()
    total_inactive = User.objects.filter(is_active=False).count()

    paginator = Paginator(qs, 10)
    page = request.GET.get('page')
    try:
        users = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        users = paginator.page(1)
    p = request.GET.copy(); p.pop('page', None); qs_str = p.urlencode()
    return render(request, 'security/user_list.html', {
        'users': users,
        'all_groups': all_groups,
        'paginator': paginator,
        'page_obj': users,
        'is_paginated': paginator.num_pages > 1,
        'filter_qs_pfx': (qs_str + '&') if qs_str else '',
        'params': request.GET,
        'elided_page_range': paginator.get_elided_page_range(users.number, on_each_side=2, on_ends=1),
        'total': total,
        'total_active': total_active,
        'total_inactive': total_inactive,
    })


@staff_required
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Usuario "{user.username}" creado exitosamente.')
            return redirect('security:user_list')
    else:
        form = UserCreateForm()
    return render(request, 'security/user_form.html', {
        'form': form,
        'title': 'Nuevo Usuario',
        'is_create': True,
    })


@staff_required
def user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para editar una cuenta de superusuario.')
        return redirect('security:user_list')
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario "{user_obj.username}" actualizado.')
            return redirect('security:user_list')
    else:
        form = UserEditForm(instance=user_obj)
    return render(request, 'security/user_form.html', {
        'form': form,
        'title': f'Editar — {user_obj.username}',
        'user_obj': user_obj,
        'is_create': False,
    })


@staff_required
def user_toggle(request, pk):
    if request.method == 'POST':
        user_obj = get_object_or_404(User, pk=pk)
        if user_obj == request.user:
            messages.error(request, 'No puedes desactivar tu propia cuenta.')
        elif user_obj.is_superuser and not request.user.is_superuser:
            messages.error(request, 'No tienes permiso para desactivar una cuenta de superusuario.')
        else:
            user_obj.is_active = not user_obj.is_active
            user_obj.save()
            estado = 'activado' if user_obj.is_active else 'desactivado'
            messages.success(request, f'Usuario "{user_obj.username}" {estado}.')
    return redirect('security:user_list')


@staff_required
def user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj == request.user:
        messages.error(request, 'No puedes eliminar tu propia cuenta.')
        return redirect('security:user_list')
    if user_obj.is_superuser and not request.user.is_superuser:
        messages.error(request, 'No tienes permiso para eliminar una cuenta de superusuario.')
        return redirect('security:user_list')
    if request.method == 'POST':
        username = user_obj.username
        user_obj.delete()
        messages.success(request, f'Usuario "{username}" eliminado.')
        return redirect('security:user_list')
    return render(request, 'security/user_confirm_delete.html', {'object': user_obj})


# ── Grupos ─────────────────────────────────────────────────────────────────

@staff_required
def group_list(request):
    groups = list(
        Group.objects
        .prefetch_related('permissions__content_type', 'user_set')
        .annotate(user_count=Count('user', distinct=True),
                  perm_count=Count('permissions', distinct=True))
        .order_by('name')
    )
    for g in groups:
        g.perm_sections = _group_permission_sections(g)
        g.has_export = g.permissions.filter(codename='can_export').exists()
    return render(request, 'security/group_list.html', {'groups': groups})


PERMISSION_ACTIONS = ['view', 'add', 'change', 'delete']
PERMISSION_ACTION_LABELS = {'view': 'Ver', 'add': 'Crear', 'change': 'Editar', 'delete': 'Eliminar'}
PERMISSION_ACTION_ICONS = {'view': 'eye', 'add': 'plus-circle', 'change': 'pencil', 'delete': 'trash3'}
PERMISSION_ACTION_CSS = {'view': 'pb-view', 'add': 'pb-add', 'change': 'pb-change', 'delete': 'pb-delete'}
PERMISSION_APPS = {
    'billing': ('Ventas y Facturación', ['brand', 'productgroup', 'supplier', 'product',
                                          'customer', 'customerprofile', 'invoice']),
    'purchasing': ('Compras', ['purchase']),
}


def _group_permission_sections(group):
    """Resume los permisos de un grupo por módulo, con etiquetas legibles en español."""
    by_model = {}
    for p in group.permissions.all():
        ct = p.content_type
        by_model.setdefault((ct.app_label, ct.model), set()).add(p.codename.split('_', 1)[0])

    sections = []
    for app_label, (app_display, model_names) in PERMISSION_APPS.items():
        rows = []
        for model_name in model_names:
            actions_present = by_model.get((app_label, model_name))
            if not actions_present:
                continue
            model_class = apps.get_model(app_label, model_name)
            actions = [
                {'label': PERMISSION_ACTION_LABELS[a],
                 'icon': PERMISSION_ACTION_ICONS[a],
                 'css': PERMISSION_ACTION_CSS[a]}
                for a in PERMISSION_ACTIONS if a in actions_present
            ]
            rows.append({'label': model_class._meta.verbose_name_plural.capitalize(), 'actions': actions})
        if rows:
            sections.append({'app_display': app_display, 'rows': rows})
    return sections


def _get_export_permission():
    return Permission.objects.filter(content_type__app_label='billing', codename='can_export').first()


def _permission_matrix():
    """Arma la matriz de permisos (módulo x acción) para las apps del sistema."""
    perms = Permission.objects.filter(
        content_type__app_label__in=PERMISSION_APPS.keys()
    ).select_related('content_type')
    lookup = {(p.content_type.app_label, p.codename): p for p in perms}

    sections = []
    for app_label, (app_display, model_names) in PERMISSION_APPS.items():
        rows = []
        for model_name in model_names:
            model_class = apps.get_model(app_label, model_name)
            rows.append({
                'label': model_class._meta.verbose_name_plural.capitalize(),
                'perms': [lookup.get((app_label, f'{action}_{model_name}')) for action in PERMISSION_ACTIONS],
            })
        sections.append({'app_display': app_display, 'rows': rows})
    return sections


@staff_required
def group_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'El nombre del grupo es obligatorio.')
        elif Group.objects.filter(name__iexact=name).exists():
            messages.error(request, f'Ya existe un grupo llamado "{name}".')
        else:
            group = Group.objects.create(name=name)
            perm_ids = request.POST.getlist('perms')
            group.permissions.set(Permission.objects.filter(id__in=perm_ids))
            messages.success(request, f'Grupo "{group.name}" creado con {group.permissions.count()} permisos.')
            return redirect('security:group_list')
    return render(request, 'security/group_form.html', {
        'group': None,
        'perm_sections': _permission_matrix(),
        'current_ids': set(),
        'action_headers': [(a, PERMISSION_ACTION_LABELS[a]) for a in PERMISSION_ACTIONS],
        'export_perm': _get_export_permission(),
        'title': 'Nuevo Grupo',
        'is_create': True,
    })


@staff_required
def group_edit(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'El nombre del grupo es obligatorio.')
        elif Group.objects.exclude(pk=group.pk).filter(name__iexact=name).exists():
            messages.error(request, f'Ya existe un grupo llamado "{name}".')
        else:
            group.name = name
            group.save()
            perm_ids = request.POST.getlist('perms')
            group.permissions.set(Permission.objects.filter(id__in=perm_ids))
            messages.success(request, f'Permisos de "{group.name}" actualizados ({group.permissions.count()}).')
            return redirect('security:group_list')
    return render(request, 'security/group_form.html', {
        'group': group,
        'perm_sections': _permission_matrix(),
        'current_ids': set(group.permissions.values_list('id', flat=True)),
        'action_headers': [(a, PERMISSION_ACTION_LABELS[a]) for a in PERMISSION_ACTIONS],
        'export_perm': _get_export_permission(),
        'title': f'Permisos — {group.name}',
        'is_create': False,
    })
