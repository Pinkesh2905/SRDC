from django.db import models
from .utils import normalize_phone

class Customer(models.Model):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, db_index=True)
    alt_phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        self.alt_phone = normalize_phone(self.alt_phone) if self.alt_phone else ''
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"
