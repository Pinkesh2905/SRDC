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
    measurement_ids = post_data.getlist('item_measurement_id[]')
    items = []
    # Track measurement IDs already assigned in this order to prevent sharing
    used_measurement_ids = set()

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
        if rate < 0:
            raise ValidationError('Item rate cannot be negative.')

        garment_category = categories[index] if index < len(categories) else ''
        all_categories = dict(get_all_garment_categories()).keys()
        if garment_category and garment_category not in all_categories:
            raise ValidationError('Invalid garment category selected.')

        measurement_id = measurement_ids[index] if index < len(measurement_ids) else ''
        measurement = None
        if measurement_id:
            try:
                measurement = Measurement.objects.filter(id=measurement_id, customer=customer).first()
            except ValueError:
                pass
        
        if not measurement and garment_category:
            measurement = Measurement.objects.filter(
                customer=customer,
                garment_category=garment_category,
            ).order_by('-updated_at').first()

        # If this measurement was already assigned to a previous item in this
        # order, clone it so each item gets its own distinct record.
        if measurement and measurement.id in used_measurement_ids:
            measurement = Measurement.objects.create(
                customer=customer,
                garment_category=measurement.garment_category,
                values=dict(measurement.values) if measurement.values else {},
                notes=measurement.notes,
                is_sample_product=measurement.is_sample_product,
            )

        if measurement:
            used_measurement_ids.add(measurement.id)

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
    is_urgent = is_red_flagged and (post_data.get('is_urgent') == 'on')

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
        is_urgent=is_urgent,
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
        if not order.is_red_flagged:
            order.is_urgent = False
            changed.append('is_urgent')
        changed.append('is_red_flagged')
        
    if 'toggle_urgent' in post_data and order.is_red_flagged:
        order.is_urgent = not order.is_urgent
        changed.append('is_urgent')

    total_discount = post_data.get('total_discount')
    if total_discount is not None:
        discount = money(total_discount)
        if discount > order.subtotal:
            raise ValidationError('Discount cannot be greater than subtotal.')
        
        order.discount_amount = discount.quantize(MONEY)
        
        if order.is_buy_back:
            order.final_amount = (order.subtotal - order.deposit_amount - order.discount_amount).quantize(MONEY)
        else:
            order.final_amount = (order.subtotal - order.discount_amount).quantize(MONEY)
            
        order.grand_total = (order.final_amount - order.advance_paid).quantize(MONEY)
        changed.extend(['discount_amount', 'final_amount', 'grand_total'])

    additional_discount = post_data.get('additional_discount')
    if additional_discount:
        discount = money(additional_discount)
        if discount <= 0:
            raise ValidationError('Discount must be greater than 0.')
        if discount > order.balance_due:
            raise ValidationError('Discount cannot be greater than the balance due.')
            
        order.discount_amount = (order.discount_amount + discount).quantize(MONEY)
        
        if order.is_buy_back:
            order.final_amount = (order.subtotal - order.deposit_amount - order.discount_amount).quantize(MONEY)
        else:
            order.final_amount = (order.subtotal - order.discount_amount).quantize(MONEY)
            
        order.grand_total = (order.final_amount - order.advance_paid).quantize(MONEY)
        changed.extend(['discount_amount', 'final_amount', 'grand_total'])

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

@transaction.atomic
def update_order_info_from_post(order, post_data):
    # Update customer details
    customer = order.customer
    customer_changed = False
    
    new_name = post_data.get('customer_name')
    if new_name and new_name.strip() != customer.full_name:
        customer.full_name = new_name.strip()
        customer_changed = True
        
    new_phone = post_data.get('customer_phone')
    if not new_phone or not new_phone.strip():
        cc = post_data.get('customer_country_code', '').strip()
        pl = post_data.get('customer_phone_local', '').strip()
        if pl:
            if cc and not cc.startswith('+'):
                cc = '+' + cc
            new_phone = cc + pl
        else:
            new_phone = ''

    from customers.utils import normalize_phone
    normalized_new_phone = normalize_phone(new_phone)
    if normalized_new_phone and normalized_new_phone != customer.phone:
        customer.phone = normalized_new_phone
        customer_changed = True
        
    new_city = post_data.get('customer_city')
    if new_city is not None and new_city.strip() != customer.city:
        customer.city = new_city.strip()
        customer_changed = True
        
    if customer_changed:
        customer.save(update_fields=['full_name', 'phone', 'city', 'updated_at'])

    # Update order metadata
    order_changed = []
    
    new_notes = post_data.get('notes')
    if new_notes is not None:
        new_notes = new_notes.strip()
        if new_notes != order.notes:
            order.notes = new_notes
            order_changed.append('notes')
            
    salesperson_id = post_data.get('salesperson')
    if salesperson_id:
        try:
            sp = Salesperson.objects.get(id=salesperson_id, is_active=True)
            if order.salesperson != sp:
                order.salesperson = sp
                order_changed.append('salesperson')
        except Salesperson.DoesNotExist:
            raise ValidationError('Invalid salesperson selected.')
            
    if order_changed:
        order.save(update_fields=order_changed + ['updated_at'])
        
    return order


@transaction.atomic
def update_order_item_from_post(item, post_data):
    # Update Item details
    item_changed = []
    
    desc = post_data.get('description')
    if desc is not None:
        desc = desc.strip()
        if desc != item.description:
            item.description = desc
            item_changed.append('description')
            
    qty_str = post_data.get('quantity')
    if qty_str:
        try:
            qty = int(qty_str)
            if qty < 1:
                raise ValidationError('Quantity must be at least 1.')
            if qty != item.quantity:
                item.quantity = qty
                item_changed.append('quantity')
        except ValueError:
            raise ValidationError('Quantity must be a whole number.')
            
    rate_str = post_data.get('rate')
    if rate_str:
        rate = money(rate_str)
        if rate <= 0:
            raise ValidationError('Rate must be greater than 0.')
        if rate != item.rate:
            item.rate = rate
            item_changed.append('rate')
            
    if 'quantity' in item_changed or 'rate' in item_changed:
        item.total_amount = (Decimal(item.quantity) * item.rate).quantize(MONEY)
        item_changed.append('total_amount')
        
    if item_changed:
        item.save(update_fields=item_changed)
        
        # Recalculate order totals
        order = item.order
        subtotal = sum(i.total_amount for i in order.items.all())
        order.subtotal = subtotal
        
        if order.is_buy_back:
            order.deposit_amount = (subtotal / Decimal('2')).quantize(MONEY)
            order.final_amount = (subtotal - order.deposit_amount - order.discount_amount).quantize(MONEY)
        else:
            order.final_amount = (subtotal - order.discount_amount).quantize(MONEY)
            
        order.grand_total = (order.final_amount - order.advance_paid).quantize(MONEY)
        order.save(update_fields=['subtotal', 'deposit_amount', 'final_amount', 'grand_total', 'updated_at'])

    # Update associated Measurement
    if item.measurement:
        measurement = item.measurement
        
        # Check if this measurement is shared by other OrderItems.
        # If so, clone it first so edits don't affect the other items.
        shared_count = OrderItem.objects.filter(measurement=measurement).exclude(id=item.id).count()
        if shared_count > 0:
            # Clone the measurement into a new independent record
            measurement = Measurement.objects.create(
                customer=measurement.customer,
                garment_category=measurement.garment_category,
                values=dict(measurement.values) if measurement.values else {},
                notes=measurement.notes,
                is_sample_product=measurement.is_sample_product,
            )
            item.measurement = measurement
            item.save(update_fields=['measurement'])
        
        m_changed = False
        
        m_notes = post_data.get('measurement_notes')
        if m_notes is not None:
            m_notes = m_notes.strip()
            if m_notes != measurement.notes:
                measurement.notes = m_notes
                m_changed = True
                
        # Update JSON values
        from measurements.models import get_all_garment_parameters
        all_params = get_all_garment_parameters()
        params = all_params.get(item.garment_category, [])
        
        values_updated = False
        is_sample = post_data.get('is_sample_product') == 'on'
        if is_sample != measurement.is_sample_product:
            measurement.is_sample_product = is_sample
            m_changed = True
            if is_sample:
                measurement.values = {}
                values_updated = False # Don't process individual params if clearing

        if not is_sample:
            for param in params:
                val = post_data.get(f'measure_{param}')
                if val is not None:
                    val = val.strip()
                    if measurement.values.get(param) != val:
                        measurement.values[param] = val
                        values_updated = True
                    
        if values_updated:
            m_changed = True
            
        if m_changed:
            measurement.save(update_fields=['notes', 'values', 'is_sample_product', 'updated_at'])
            
    return item
