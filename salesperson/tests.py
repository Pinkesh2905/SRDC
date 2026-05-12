from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Salesperson


class SalespersonDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('salesperson_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_dashboard_lists_salespeople(self):
        self.client.force_login(self.user)
        Salesperson.objects.create(full_name='Kiran Patel', employee_code='SP-001')

        response = self.client.get(reverse('salesperson_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Salesperson Analysis')
        self.assertContains(response, 'Kiran Patel')

    def test_dashboard_can_create_salesperson(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('salesperson_dashboard'), {
            'full_name': 'Meera Shah',
            'employee_code': 'SP-002',
            'phone': '9999999999',
        })

        self.assertRedirects(response, reverse('salesperson_dashboard'))
        self.assertTrue(Salesperson.objects.filter(full_name='Meera Shah').exists())
