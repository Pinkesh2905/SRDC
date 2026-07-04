from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from measurements.models import Measurement
from salesperson.models import Salesperson
from .models import Order, OrderItem
from .services import create_order_from_post


class OrderServiceTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(full_name='Rajesh Kumar', phone='+91 98765 43210')
        Measurement.objects.create(
            customer=self.customer,
            garment_category='shirt',
            values={'Length': '40', 'Chest': '38'},
        )

    def test_order_item_uses_decimal_total(self):
        order = Order.objects.create(
            order_number='TMP-test',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
        )
        item = OrderItem.objects.create(
            order=order,
            garment_category='shirt',
            description='Shirt',
            quantity=2,
            rate=Decimal('499.50'),
            total_amount=Decimal('0.00'),
        )
        self.assertEqual(item.total_amount, Decimal('999.00'))

    def test_server_recomputes_totals_and_ignores_hidden_values(self):
        from django.http import QueryDict

        query = QueryDict('', mutable=True)
        query.setlist('item_garment_category[]', ['shirt'])
        query.setlist('item_description[]', ['Shirt'])
        query.setlist('item_qty[]', ['2'])
        query.setlist('item_rate[]', ['500.00'])
        query['subtotal'] = '1.00'
        query['final_amount'] = '1.00'
        query['grand_total'] = '1.00'
        query['discount'] = '100.00'
        query['advance_paid'] = '200.00'
        query['notes'] = 'Urgent'
        order = create_order_from_post(query, self.customer)

        self.assertEqual(order.subtotal, Decimal('1000.00'))
        self.assertEqual(order.discount_amount, Decimal('100.00'))
        self.assertEqual(order.final_amount, Decimal('900.00'))
        self.assertEqual(order.advance_paid, Decimal('200.00'))
        self.assertEqual(order.grand_total, Decimal('700.00'))
        self.assertRegex(order.order_number, r'^SRD-\d{8}-\d{3}$')

    def test_discount_and_advance_cannot_exceed_order_value(self):
        from django.core.exceptions import ValidationError
        from django.http import QueryDict

        query = QueryDict('', mutable=True)
        query.setlist('item_garment_category[]', ['shirt'])
        query.setlist('item_description[]', ['Shirt'])
        query.setlist('item_qty[]', ['1'])
        query.setlist('item_rate[]', ['100.00'])
        query['discount'] = '101.00'

        with self.assertRaises(ValidationError):
            create_order_from_post(query, self.customer)


class OrderViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='pass')
        self.customer = Customer.objects.create(full_name='Amit Shah', phone='9999999999')

    def test_order_pages_require_login(self):
        response = self.client.get(reverse('order_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_order_post_creates_items_and_redirects_to_print(self):
        self.client.force_login(self.user)
        salesperson = Salesperson.objects.create(full_name='Kiran Patel', employee_code='SP-001')
        response = self.client.post(reverse('order_create'), {
            'customer_id': self.customer.id,
            'salesperson': salesperson.id,
            'item_garment_category[]': ['pant'],
            'item_description[]': ['Pant'],
            'item_qty[]': ['1'],
            'item_rate[]': ['800.00'],
            'discount': '50.00',
            'advance_paid': '100.00',
        })
        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_print', args=[order.id]))
        self.assertEqual(order.final_amount, Decimal('750.00'))
        self.assertEqual(order.balance_due, Decimal('650.00'))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.salesperson, salesperson)

    def test_order_print_includes_salesperson(self):
        self.client.force_login(self.user)
        salesperson = Salesperson.objects.create(full_name='Meera Shah', employee_code='SP-002')
        order = Order.objects.create(
            order_number='SRD-20260503-010',
            customer=self.customer,
            salesperson=salesperson,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
            final_amount=Decimal('500.00'),
            grand_total=Decimal('500.00'),
        )

        response = self.client.get(reverse('order_print', args=[order.id]))

        self.assertContains(response, 'Salesperson')
        self.assertContains(response, salesperson.full_name)

    def test_order_detail_rejects_payment_above_balance(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='SRD-20260503-001',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
            final_amount=Decimal('500.00'),
            advance_paid=Decimal('100.00'),
            grand_total=Decimal('400.00'),
        )
        self.client.post(reverse('order_detail', args=[order.id]), {'additional_payment': '500.00'})
        order.refresh_from_db()
        self.assertEqual(order.advance_paid, Decimal('100.00'))
        self.assertEqual(order.grand_total, Decimal('400.00'))

    def test_order_list_filters_by_exact_delivery_and_return_dates(self):
        self.client.force_login(self.user)
        matching = Order.objects.create(
            order_number='SRD-20260503-001',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
            return_date='2026-05-12',
        )
        Order.objects.create(
            order_number='SRD-20260503-002',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-11',
            return_date='2026-05-12',
        )

        response = self.client.get(reverse('order_list'), {
            'delivery_date': '2026-05-10',
            'return_date': '2026-05-12',
        })

        self.assertContains(response, matching.order_number)
        self.assertNotContains(response, 'SRD-20260503-002')

    def test_order_list_print_uses_same_filters(self):
        self.client.force_login(self.user)
        matching = Order.objects.create(
            order_number='SRD-20260503-003',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
            grand_total=Decimal('1200.00'),
        )
        Order.objects.create(
            order_number='SRD-20260503-004',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-11',
            grand_total=Decimal('900.00'),
        )

        response = self.client.get(reverse('order_list_print'), {'delivery_date': '2026-05-10'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Filtered Orders & Bills List')
        self.assertContains(response, matching.order_number)
        self.assertContains(response, 'Rs 1200.00')
        self.assertNotContains(response, 'SRD-20260503-004')

    def test_api_update_order_shortcut_status_success(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='SRD-20260503-100',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
            status='pending',
        )
        response = self.client.post(reverse('api_update_order_shortcut', args=[order.id]), {
            'status': 'in_progress'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'in_progress')
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_progress')

    def test_api_update_order_shortcut_payment_success(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='SRD-20260503-101',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
            final_amount=Decimal('1000.00'),
            advance_paid=Decimal('200.00'),
            grand_total=Decimal('800.00'),
        )
        response = self.client.post(reverse('api_update_order_shortcut', args=[order.id]), {
            'payment_amount': '300.00',
            'payment_method': 'upi'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['grand_total'], '500.00')
        order.refresh_from_db()
        self.assertEqual(order.advance_paid, Decimal('500.00'))
        self.assertEqual(order.grand_total, Decimal('500.00'))
        self.assertEqual(order.payment_method, 'upi')

    def test_api_update_order_shortcut_validation_error(self):
        self.client.force_login(self.user)
        order = Order.objects.create(
            order_number='SRD-20260503-102',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
            final_amount=Decimal('1000.00'),
            advance_paid=Decimal('200.00'),
            grand_total=Decimal('800.00'),
        )
        # Payment above balance due
        response = self.client.post(reverse('api_update_order_shortcut', args=[order.id]), {
            'payment_amount': '900.00',
            'payment_method': 'upi'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('errors', data)

    def test_order_creation_with_duplicate_categories_and_different_measurements(self):
        self.client.force_login(self.user)
        salesperson = Salesperson.objects.create(full_name='Kiran Patel', employee_code='SP-001')
        
        # Create 2 distinct measurements for self.customer for garment_category = 'shirt'
        m1 = Measurement.objects.create(
            customer=self.customer,
            garment_category='shirt',
            values={'Length': '40', 'Chest': '38'},
            notes='Shirt 1'
        )
        m2 = Measurement.objects.create(
            customer=self.customer,
            garment_category='shirt',
            values={'Length': '42', 'Chest': '40'},
            notes='Shirt 2'
        )
        
        # Post to order_create, passing item_measurement_id[] explicitly
        response = self.client.post(reverse('order_create'), {
            'customer_id': self.customer.id,
            'salesperson': salesperson.id,
            'item_garment_category[]': ['shirt', 'shirt'],
            'item_measurement_id[]': [str(m1.id), str(m2.id)],
            'item_description[]': ['Shirt style A', 'Shirt style B'],
            'item_qty[]': ['1', '1'],
            'item_rate[]': ['800.00', '900.00'],
            'discount': '0.00',
            'advance_paid': '100.00',
        })
        
        # Assert order was created and redirected
        order = Order.objects.get(customer=self.customer)
        self.assertRedirects(response, reverse('order_print', args=[order.id]))
        self.assertEqual(order.items.count(), 2)
        
        # Verify items point to distinct measurement records
        items = list(order.items.order_by('id'))
        self.assertEqual(items[0].measurement.id, m1.id)
        self.assertEqual(items[0].measurement.notes, 'Shirt 1')
        self.assertEqual(items[1].measurement.id, m2.id)
        self.assertEqual(items[1].measurement.notes, 'Shirt 2')

    def test_order_creation_fallback_clones_shared_measurements(self):
        self.client.force_login(self.user)
        salesperson = Salesperson.objects.create(full_name='Kiran Patel', employee_code='SP-001')
        
        # Only 1 shirt measurement exists
        m = Measurement.objects.create(
            customer=self.customer,
            garment_category='shirt',
            values={'Length': '40', 'Chest': '38'},
            notes='Original Shirt'
        )
        
        # Post 2 shirt items, both without explicit measurement IDs
        response = self.client.post(reverse('order_create'), {
            'customer_id': self.customer.id,
            'salesperson': salesperson.id,
            'item_garment_category[]': ['shirt', 'shirt'],
            'item_measurement_id[]': ['', ''],
            'item_description[]': ['Shirt A', 'Shirt B'],
            'item_qty[]': ['1', '1'],
            'item_rate[]': ['800.00', '900.00'],
            'discount': '0.00',
            'advance_paid': '100.00',
        })
        
        order = Order.objects.get(customer=self.customer)
        items = list(order.items.order_by('id'))
        self.assertEqual(len(items), 2)
        
        # First item should use the original measurement
        self.assertEqual(items[0].measurement.id, m.id)
        # Second item should use a cloned, separate measurement
        self.assertNotEqual(items[1].measurement.id, m.id)
        self.assertEqual(items[1].measurement.garment_category, 'shirt')
        self.assertEqual(items[1].measurement.values, m.values)

    def test_order_item_edit_clones_shared_measurement(self):
        self.client.force_login(self.user)
        
        # Create a single shared measurement
        m = Measurement.objects.create(
            customer=self.customer,
            garment_category='shirt',
            values={'Length': '40', 'Chest': '38'},
            notes='Shared Shirt'
        )
        
        order = Order.objects.create(
            order_number='SRD-test-edit',
            customer=self.customer,
            booking_date='2026-05-03',
            delivery_date='2026-05-10',
        )
        
        # 2 OrderItems share the same measurement ID
        item1 = OrderItem.objects.create(
            order=order,
            garment_category='shirt',
            measurement=m,
            description='Shirt 1',
            quantity=1,
            rate=Decimal('500.00'),
            total_amount=Decimal('500.00')
        )
        item2 = OrderItem.objects.create(
            order=order,
            garment_category='shirt',
            measurement=m,
            description='Shirt 2',
            quantity=1,
            rate=Decimal('500.00'),
            total_amount=Decimal('500.00')
        )
        
        # Post edit to item2 only, changing Length from 40 to 42
        response = self.client.post(reverse('order_item_edit', args=[order.id, item2.id]), {
            'description': 'Shirt 2 Updated',
            'quantity': '1',
            'rate': '500.00',
            'is_sample_product': 'off',
            'measure_Length': '42',
            'measure_Chest': '38',
            'measurement_notes': 'Only item 2 updated'
        })
        
        # Verify item2's measurement is cloned and updated, while item1 is unchanged
        item1.refresh_from_db()
        item2.refresh_from_db()
        
        self.assertNotEqual(item1.measurement.id, item2.measurement.id)
        
        # Item 1 measurement remains 40
        self.assertEqual(item1.measurement.values.get('Length'), '40')
        self.assertEqual(item1.measurement.notes, 'Shared Shirt')
        
        # Item 2 measurement is now 42
        self.assertEqual(item2.measurement.values.get('Length'), '42')
        self.assertEqual(item2.measurement.notes, 'Only item 2 updated')

