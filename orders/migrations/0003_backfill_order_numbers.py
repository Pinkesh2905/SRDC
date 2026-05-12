from django.db import migrations


def backfill_order_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.filter(order_number='').order_by('id'):
        order.order_number = f"SRD-{order.booking_date:%Y%m%d}-{order.id:03d}"
        order.save(update_fields=['order_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_number_length_default'),
    ]

    operations = [
        migrations.RunPython(backfill_order_numbers, migrations.RunPython.noop),
    ]
