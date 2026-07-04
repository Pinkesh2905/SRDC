"""
One-time management command to fix existing orders where multiple OrderItems
share the same Measurement record. Each item should have its own distinct
Measurement so that editing one doesn't affect the other.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from orders.models import OrderItem
from measurements.models import Measurement


class Command(BaseCommand):
    help = 'Fix orders where multiple items share the same Measurement record by cloning.'

    def handle(self, *args, **options):
        # Find all Measurement IDs that are referenced by more than one OrderItem
        shared = (
            OrderItem.objects
            .filter(measurement__isnull=False)
            .values('measurement_id')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
        )

        total_cloned = 0
        for entry in shared:
            m_id = entry['measurement_id']
            items = list(OrderItem.objects.filter(measurement_id=m_id).select_related('measurement'))
            if len(items) <= 1:
                continue

            original = items[0].measurement
            self.stdout.write(f"Measurement #{m_id} ({original.garment_category}) shared by {len(items)} items")

            # Keep the first item linked to the original, clone for the rest
            for item in items[1:]:
                clone = Measurement.objects.create(
                    customer=original.customer,
                    garment_category=original.garment_category,
                    values=dict(original.values) if original.values else {},
                    notes=original.notes,
                    is_sample_product=original.is_sample_product,
                )
                item.measurement = clone
                item.save(update_fields=['measurement'])
                total_cloned += 1
                self.stdout.write(
                    f"  -> Cloned Measurement #{m_id} -> #{clone.id} for OrderItem #{item.id} "
                    f"(Order #{item.order.order_number})"
                )

        if total_cloned == 0:
            self.stdout.write(self.style.SUCCESS("No shared measurements found. All orders are clean."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. Cloned {total_cloned} measurement(s)."))
