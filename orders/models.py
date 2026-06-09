from django.db import models
from django.utils import timezone
from customers.models import Customer
from measurements.models import GarmentCategory, Measurement
from salesperson.models import Salesperson

class OrderType(models.TextChoices):
    STITCHING = 'stitching', 'Fresh Stitching'
    RENTAL = 'rental', 'Rental'

class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    READY = 'ready', 'Ready for Pickup'
    DELIVERED = 'delivered', 'Delivered'
    RETURNED = 'returned', 'Returned (Rental)'
    CANCELLED = 'cancelled', 'Cancelled'

class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    UPI = 'upi', 'UPI / QR Code'
    CARD = 'card', 'Credit / Debit Card'
    BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'

class Order(models.Model):
    order_number = models.CharField(max_length=30, unique=True, editable=False, blank=True, default='')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    salesperson = models.ForeignKey(Salesperson, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.STITCHING)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    
    booking_date = models.DateField()
    delivery_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)  # For rentals
    notes = models.TextField(blank=True)

    is_red_flagged = models.BooleanField(
        default=False,
        verbose_name="Red Flag (Outsource Required)",
        help_text="Mark if the garment/catalog is unavailable in-store and must be ordered from a 3rd party."
    )
    is_urgent = models.BooleanField(
        default=False,
        verbose_name="Urgent",
        help_text="Mark if this outsourced order requires urgent processing."
    )
    is_buy_back = models.BooleanField(
        default=False,
        verbose_name="Buy Back",
        help_text="Check if this order is a buy back."
    )
    # Billing Totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_deposit_paid = models.BooleanField(default=False)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # GST Placeholder
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance_due(self):
        return max(self.final_amount - self.advance_paid, 0)

    def assign_order_number(self):
        if not self.pk:
            raise ValueError('Order must be saved before assigning an order number.')
        if self.order_number and not self.order_number.startswith('TMP-'):
            return
        date_value = self.booking_date or timezone.localdate()
        self.order_number = f"SRD-{date_value:%Y%m%d}-{self.pk:03d}"
        self.save(update_fields=['order_number'])

    def __str__(self):
        return f"{self.order_number} - {self.customer.full_name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    garment_category = models.CharField(max_length=50, null=True, blank=True)
    measurement = models.ForeignKey(Measurement, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_amount = self.quantity * self.rate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} ({self.quantity})"
