from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from measurements.models import Measurement, get_all_garment_categories
from salesperson.models import Salesperson
from .models import Order, OrderItem, OrderStatus, OrderType, PaymentMethod


MONEY = Decimal('0.01')


def money(value, default='0'):
    if value in (None, ''):
        value = default
    try:
        amount = Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValidationError('Enter a valid amount.')
    if amount < 0:
        raise ValidationError('Amounts cannot be negative.')
    return amount


def parse_items(post_data, customer):
    categories = post_data.getlist('item_garment_category[]')
    descriptions = post_data.getlist('item_description[]')
    qtys = post_data.getlist('item_qty[]')
    rates = post_data.getlist('item_rate[]')
    items = []

    for index, description in enumerate(descriptions):
        description = (description or '').strip()
        if not description:
            continue

        try:
            quantity = int(qtys[index] if index < len(qtys) and qtys[index] else 1)
        except ValueError:
            raise ValidationError('Quantity must be a whole number.')
        if quantity < 1:
            raise ValidationError('Quantity must be at least 1.')

        rate = money(rates[index] if index < len(rates) else 0)
        if rate <= 0:
            raise ValidationError('Item rate must be greater than 0.')

        garment_category = categories[index] if index < len(categories) else ''
        all_categories = dict(get_all_garment_categories()).keys()
        if garment_category and garment_category not in all_categories:
            raise ValidationError('Invalid garment category selected.')

        measurement = None
        if garment_category:
            measurement = Measurement.objects.filter(
                customer=customer,
                garment_category=garment_category,
            ).order_by('-updated_at').first()

        items.append({
            'garment_category': garment_category or None,
            'measurement': measurement,
            'description': description,
            'quantity': quantity,
            'rate': rate,
            'total_amount': (Decimal(quantity) * rate).quantize(MONEY),
        })

    if not items:
        raise ValidationError('Add at least one billable item.')

    return items


def order_date(value, default):
    if not value:
        return default
    parsed = parse_date(value)
    if not parsed:
        raise ValidationError('Enter a valid date.')
    return parsed


def salesperson_from_post(post_data):
    salesperson_id = post_data.get('salesperson')
    if not salesperson_id:
        return None
    try:
        return Salesperson.objects.get(id=salesperson_id, is_active=True)
    except (Salesperson.DoesNotExist, ValueError):
        raise ValidationError('Invalid salesperson selected.')


@transaction.atomic
def create_order_from_post(post_data, customer):
    items = parse_items(post_data, customer)
    salesperson = salesperson_from_post(post_data)
    subtotal = sum((item['total_amount'] for item in items), Decimal('0.00')).quantize(MONEY)
    
    discount = money(post_data.get('discount'))
    is_buy_back = post_data.get('is_buy_back') == 'on'
    deposit_amount = Decimal('0.00')
    is_deposit_paid = False

    if is_buy_back:
        discount = Decimal('0.00')
        deposit_amount = (subtotal / Decimal('2')).quantize(MONEY)
        is_deposit_paid = post_data.get('is_deposit_paid') == 'on'
        final_amount = (subtotal - deposit_amount).quantize(MONEY)
    else:
        if discount > subtotal:
            raise ValidationError('Discount cannot be greater than subtotal.')
        final_amount = (subtotal - discount).quantize(MONEY)
    advance_paid = money(post_data.get('advance_paid'))
    if advance_paid > final_amount:
        raise ValidationError('Advance paid cannot be greater than the final amount.')
    payment_method = post_data.get('payment_method') or PaymentMethod.CASH
    if payment_method not in PaymentMethod.values:
        raise ValidationError('Invalid payment method.')

    today = timezone.localdate()
    delivery_date = order_date(post_data.get('delivery_date'), today + timedelta(days=7))
    if delivery_date < today:
        raise ValidationError('Delivery date cannot be in the past.')
    requested_order_type = post_data.get('order_type') or OrderType.STITCHING
    if requested_order_type not in OrderType.values:
        raise ValidationError('Invalid order type.')
    order_type = requested_order_type
    return_date_str = post_data.get('return_date')
    return_date = None
    if return_date_str:
        return_date = order_date(return_date_str, delivery_date)
        if return_date < delivery_date:
            raise ValidationError('Return date cannot be before delivery date.')
    balance_due = (final_amount - advance_paid).quantize(MONEY)
    is_red_flagged = post_data.get('is_red_flagged') == 'on'

    order = Order.objects.create(
        order_number=f"TMP-{uuid4().hex[:12]}",
        customer=customer,
        salesperson=salesperson,
        order_type=order_type,
        subtotal=subtotal,
        discount_amount=discount,
        deposit_amount=deposit_amount,
        is_buy_back=is_buy_back,
        is_deposit_paid=is_deposit_paid,
        final_amount=final_amount,
        advance_paid=advance_paid,
        payment_method=payment_method,
        grand_total=balance_due,
        booking_date=today,
        delivery_date=delivery_date,
        return_date=return_date,
        notes=(post_data.get('notes') or '').strip(),
        is_red_flagged=is_red_flagged,
    )
    order.assign_order_number()

    for index, item in enumerate(items):
        order_item = OrderItem.objects.create(order=order, **item)

    return order



@transaction.atomic
def update_order_from_post(order, post_data):
    changed = []
    new_status = post_data.get('status')
    if new_status:
        if new_status not in OrderStatus.values:
            raise ValidationError('Invalid order status.')
        order.status = new_status
        changed.append('status')

    if 'toggle_red_flag' in post_data:
        order.is_red_flagged = not order.is_red_flagged
        changed.append('is_red_flagged')

    additional_payment = post_data.get('additional_payment')
    if additional_payment:
        payment = money(additional_payment)
        if payment <= 0:
            raise ValidationError('Payment must be greater than 0.')
        if payment > order.balance_due:
            raise ValidationError('Payment cannot be greater than the balance due.')
        
        new_payment_method = post_data.get('payment_method')
        if new_payment_method:
            if new_payment_method not in PaymentMethod.values:
                raise ValidationError('Invalid payment method.')
            order.payment_method = new_payment_method
            changed.append('payment_method')

        order.advance_paid = (order.advance_paid + payment).quantize(MONEY)
        order.grand_total = order.balance_due
        changed.extend(['advance_paid', 'grand_total'])

    if changed:
        order.save(update_fields=list(dict.fromkeys(changed + ['updated_at'])))
    return order
