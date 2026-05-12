from django.db import models


class Salesperson(models.Model):
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    employee_code = models.CharField(max_length=30, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    joined_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return self.full_name
