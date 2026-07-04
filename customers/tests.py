from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from measurements.models import Measurement
from .models import Customer


class CustomerViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')
        self.customer = Customer.objects.create(full_name='Rajesh Kumar', phone='+91 98765 43210', city='Jaipur')
        Measurement.objects.create(customer=self.customer, garment_category='shirt', values={'Length': '40'})

    def test_customer_pages_require_login(self):
        response = self.client.get(reverse('customer_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_phone_lookup_normalizes_phone_and_returns_measurements(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('api_get_customer_by_phone', args=['+91-98765-43210']))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['customer']['phone'], '+919876543210')
        self.assertEqual(data['measurements']['shirt']['values']['Length'], '40')
