from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'city', 'email', 'created_at', 'updated_at')
    search_fields = ('full_name', 'phone', 'alt_phone', 'email', 'city')
    list_filter = ('city', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
