from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Crea grupos, asigna permisos y genera usuarios de demostración'

    def handle(self, *args, **options):
        self.stdout.write('Configurando módulo de seguridad...\n')
        self._setup_groups()
        self._setup_users()
        self.stdout.write(self.style.SUCCESS('\nConfiguración completada exitosamente.'))
        self.stdout.write('\nUsuarios de demostración:')
        self.stdout.write('  administrador / Admin1234!')
        self.stdout.write('  gerente       / Gerente1234!')
        self.stdout.write('  comprador     / Compras1234!')
        self.stdout.write('  vendedor      / Ventas1234!')

    def _get_perms(self, app_label, model_names, actions=None):
        actions = actions or ['view', 'add', 'change', 'delete']
        perms = []
        for model_name in model_names:
            for action in actions:
                perm = Permission.objects.filter(
                    content_type__app_label=app_label,
                    codename=f'{action}_{model_name}',
                ).first()
                if perm:
                    perms.append(perm)
        return perms

    def _export_perm(self):
        perm = Permission.objects.filter(content_type__app_label='billing', codename='can_export').first()
        return [perm] if perm else []

    def _setup_groups(self):
        billing_all = ['brand', 'productgroup', 'supplier', 'product',
                       'customer', 'customerprofile', 'invoice', 'invoicedetail']
        purchasing_all = ['purchase', 'purchasedetail']
        cobros_all = ['cobrofactura']
        pagos_all = ['pagocompra']

        # ── Administrador: acceso total ──────────────────────────────────────
        admin_grp, _ = Group.objects.get_or_create(name='Administrador')
        perms = (
            self._get_perms('billing', billing_all) +
            self._get_perms('purchasing', purchasing_all) +
            self._get_perms('cobros', cobros_all) +
            self._get_perms('pagos', pagos_all) +
            self._export_perm()
        )
        admin_grp.permissions.set(perms)
        self.stdout.write(f'  [OK] Grupo Administrador  ({len(perms)} permisos)')

        # ── Gerente: solo lectura en todo ────────────────────────────────────
        gerente_grp, _ = Group.objects.get_or_create(name='Gerente')
        perms = (
            self._get_perms('billing', billing_all, ['view']) +
            self._get_perms('purchasing', purchasing_all, ['view']) +
            self._get_perms('cobros', cobros_all, ['view']) +
            self._get_perms('pagos', pagos_all, ['view']) +
            self._export_perm()
        )
        gerente_grp.permissions.set(perms)
        self.stdout.write(f'  [OK] Grupo Gerente        ({len(perms)} permisos)')

        # ── Compras: proveedores + compras + pagos (cuentas por pagar); vista de catálogos ──
        compras_grp, _ = Group.objects.get_or_create(name='Compras')
        perms = (
            self._get_perms('billing', ['brand', 'productgroup', 'product'], ['view']) +
            self._get_perms('billing', ['supplier'], ['view', 'add', 'change', 'delete']) +
            self._get_perms('purchasing', purchasing_all) +
            self._get_perms('pagos', pagos_all) +
            self._export_perm()
        )
        compras_grp.permissions.set(perms)
        self.stdout.write(f'  [OK] Grupo Compras        ({len(perms)} permisos)')

        # ── Ventas: clientes + facturas + cobros (cuentas por cobrar); vista de catálogos ──
        ventas_grp, _ = Group.objects.get_or_create(name='Ventas')
        perms = (
            self._get_perms('billing', ['brand', 'productgroup', 'product', 'supplier'], ['view']) +
            self._get_perms('billing', ['customer', 'customerprofile',
                                        'invoice', 'invoicedetail']) +
            self._get_perms('cobros', cobros_all) +
            self._export_perm()
        )
        ventas_grp.permissions.set(perms)
        self.stdout.write(f'  [OK] Grupo Ventas         ({len(perms)} permisos)')

    def _setup_users(self):
        self.stdout.write('\nCreando usuarios de demostración:')
        users_data = [
            ('administrador', 'Admin1234!',    'Administrador', True),
            ('gerente',       'Gerente1234!',  'Gerente',       False),
            ('comprador',     'Compras1234!',  'Compras',       False),
            ('vendedor',      'Ventas1234!',   'Ventas',        False),
        ]
        for username, password, group_name, is_staff in users_data:
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.is_staff = is_staff
            user.save()
            group = Group.objects.get(name=group_name)
            user.groups.set([group])
            action = 'creado' if created else 'actualizado'
            self.stdout.write(f'  [OK] {username} ({action}) -> grupo {group_name}')
