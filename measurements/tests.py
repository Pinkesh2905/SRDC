from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from .models import Measurement


class MeasurementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')

    def test_one_measurement_per_customer_and_garment(self):
        customer = Customer.objects.create(full_name='Rajesh Kumar', phone='9876543210')
        Measurement.objects.create(customer=customer, garment_category='shirt', values={'Length': '40'})
        with self.assertRaises(IntegrityError):
            Measurement.objects.create(customer=customer, garment_category='shirt', values={'Length': '41'})

    def test_measurement_post_creates_customer_and_redirects_to_billing(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('measurement_profile'), {
            'customer_phone': '+91 98765 43210',
            'customer_name': 'Rajesh Kumar',
            'customer_city': 'Jaipur',
            'garment_block_id': ['1'],
            'garment_type_1': 'shirt',
            'measure_1_length': '40',
            'measure_1_chest': '38',
            'bill_garment': ['1'],
            'notes_1': 'Slim fit',
        })
        customer = Customer.objects.get(phone='9876543210')
        measurement = Measurement.objects.get(customer=customer, garment_category='shirt')
        self.assertEqual(measurement.values['Length'], '40')
        self.assertEqual(measurement.notes, 'Slim fit')
        self.assertRedirects(
            response,
            f"{reverse('order_create')}?customer_id={customer.id}&garments=shirt",
            fetch_redirect_response=False,
        )
