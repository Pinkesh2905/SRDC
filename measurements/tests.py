from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from .models import Measurement


class MeasurementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')

    def test_multiple_measurements_allowed(self):
        customer = Customer.objects.create(full_name='Rajesh Kumar', phone='9876543210')
        m1 = Measurement.objects.create(customer=customer, garment_category='shirt', values={'Length': '40'})
        m2 = Measurement.objects.create(customer=customer, garment_category='shirt', values={'Length': '41'})
        self.assertNotEqual(m1.id, m2.id)
        self.assertEqual(Measurement.objects.filter(customer=customer, garment_category='shirt').count(), 2)

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
        customer = Customer.objects.get(phone='+919876543210')
        measurement = Measurement.objects.get(customer=customer, garment_category='shirt')
        self.assertEqual(measurement.values['Length'], '40')
        self.assertEqual(measurement.notes, 'Slim fit')
        self.assertRedirects(
            response,
            f"{reverse('order_create')}?customer_id={customer.id}&measurements={measurement.id}",
            fetch_redirect_response=False,
        )

    def test_duplicate_phone_numbers_kept_separate(self):
        self.client.force_login(self.user)
        # Create Father
        father = Customer.objects.create(full_name='Father Name', phone='+91 98765 43210')
        # Create Son (duplicate phone, different name)
        son = Customer.objects.create(full_name='Son Name', phone='+91 98765 43210')
        
        # Verify they are separate Customer records
        self.assertNotEqual(father.id, son.id)
        self.assertEqual(Customer.objects.filter(phone='+919876543210').count(), 2)
        
        # Load Father via customer_id GET
        response_father = self.client.get(reverse('measurement_profile') + f'?customer_id={father.id}')
        self.assertEqual(response_father.status_code, 200)
        self.assertContains(response_father, 'Father Name')
        
        # Load Son via customer_id GET
        response_son = self.client.get(reverse('measurement_profile') + f'?customer_id={son.id}')
        self.assertEqual(response_son.status_code, 200)
        self.assertContains(response_son, 'Son Name')

    def test_international_phone_number_country_codes(self):
        self.client.force_login(self.user)
        # Post new customer with US country code and local number
        response = self.client.post(reverse('measurement_profile'), {
            'customer_country_code': '+1',
            'customer_phone_local': '2025550143',
            'customer_name': 'US Customer',
            'customer_city': 'New York',
            'garment_block_id': ['1'],
            'garment_type_1': 'pant',
            'measure_1_length': '32',
            'bill_garment': ['1'],
        })
        customer = Customer.objects.get(phone='+12025550143')
        self.assertEqual(customer.full_name, 'US Customer')
        self.assertEqual(customer.city, 'New York')
        measurement = Measurement.objects.get(customer=customer, garment_category='pant')
        self.assertRedirects(
            response,
            f"{reverse('order_create')}?customer_id={customer.id}&measurements={measurement.id}",
            fetch_redirect_response=False,
        )
