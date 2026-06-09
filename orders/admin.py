from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_amount',)
    fields = ('garment_category', 'measurement', 'description', 'quantity', 'rate', 'total_amount')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'customer',
        'status',
        'is_red_flagged',
        'is_urgent',
        'booking_date',
        'delivery_date',
        'final_amount',
        'advance_paid',
        'grand_total',
    )
    list_filter = ('status', 'is_red_flagged', 'is_urgent', 'order_type', 'booking_date', 'delivery_date')
    search_fields = ('order_number', 'customer__full_name', 'customer__phone')
    readonly_fields = ('order_number', 'subtotal', 'final_amount', 'grand_total', 'created_at', 'updated_at')
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'description', 'garment_category', 'quantity', 'rate', 'total_amount')
    search_fields = ('order__order_number', 'description', 'order__customer__full_name')
    list_filter = ('garment_category',)
