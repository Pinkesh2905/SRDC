from django.db import migrations, models


def dedupe_measurements(apps, schema_editor):
    Measurement = apps.get_model('measurements', 'Measurement')
    seen = set()
    for measurement in Measurement.objects.order_by('customer_id', 'garment_category', '-updated_at', '-id'):
        key = (measurement.customer_id, measurement.garment_category)
        if key in seen:
            measurement.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('measurements', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(dedupe_measurements, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='measurement',
            constraint=models.UniqueConstraint(
                fields=('customer', 'garment_category'),
                name='unique_measurement_per_customer_garment',
            ),
        ),
    ]
