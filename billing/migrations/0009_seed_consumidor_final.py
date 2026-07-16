from django.db import migrations


def create_consumidor_final(apps, schema_editor):
    Customer = apps.get_model('billing', 'Customer')
    CustomerProfile = apps.get_model('billing', 'CustomerProfile')
    customer, _ = Customer.objects.get_or_create(
        dni='9999999999999',
        defaults={
            'first_name': 'Consumidor',
            'last_name': 'Final',
            'is_generic': True,
            'is_active': True,
        },
    )
    if not customer.is_generic:
        customer.is_generic = True
        customer.save(update_fields=['is_generic'])
    CustomerProfile.objects.get_or_create(
        customer=customer,
        defaults={'taxpayer_type': 'final', 'payment_terms': 'cash'},
    )


def remove_consumidor_final(apps, schema_editor):
    Customer = apps.get_model('billing', 'Customer')
    Customer.objects.filter(dni='9999999999999', is_generic=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0008_customer_is_generic'),
    ]

    operations = [
        migrations.RunPython(create_consumidor_final, remove_consumidor_final),
    ]
