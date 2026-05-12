from django.contrib import admin

from .models import Salesperson


@admin.register(Salesperson)
class SalespersonAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'employee_code', 'phone', 'is_active', 'joined_on')
    list_filter = ('is_active',)
    search_fields = ('full_name', 'employee_code', 'phone')
