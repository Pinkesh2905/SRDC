from django.contrib import admin
from .models import Measurement


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ('customer', 'garment_category', 'updated_at')
    search_fields = ('customer__full_name', 'customer__phone', 'garment_category', 'notes')
    list_filter = ('garment_category', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
