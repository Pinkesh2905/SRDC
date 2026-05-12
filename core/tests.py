from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class CoreViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_dashboard_loads_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
