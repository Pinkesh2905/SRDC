from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_date
from measurements.models import get_all_garment_categories
from customers.models import Customer
from salesperson.models import Salesperson
from .models import Order, OrderItem, OrderStatus, OrderType
from .services import create_order_from_post, update_order_from_post, update_order_info_from_post, update_order_item_from_post

@login_required
def order_create(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        customer = get_object_or_404(Customer, id=customer_id)
        try:
            order = create_order_from_post(request.POST, customer)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            garments = ','.join(request.POST.getlist('item_garment_category[]'))
            measurements = ','.join(request.POST.getlist('item_measurement_id[]'))
            return redirect(f"{reverse('order_create')}?customer_id={customer.id}&garments={garments}&measurements={measurements}")
        return redirect(reverse('order_print', args=[order.id]))

    customer_id = request.GET.get('customer_id')
    garments_qs = request.GET.get('garments', '')
    measurements_qs = request.GET.get('measurements', '')
    
    if not customer_id:
        # If accessed directly, redirect back to measurements profile
        return redirect(reverse('measurement_profile'))
        
    customer = get_object_or_404(Customer, id=customer_id)
    order_type = request.GET.get('order_type') or OrderType.STITCHING
    
    # Generate temporary order number for display (will be finalized on save)
    today = timezone.localdate().strftime('%Y%m%d')
    mock_order_id = f"SRD-{today}-auto"

    from measurements.models import Measurement
    # Build initial list of items
    selected_items = []
    all_cats = dict(get_all_garment_categories())

    if measurements_qs:
        measurement_ids = [x.strip() for x in measurements_qs.split(',') if x.strip()]
        for m_id in measurement_ids:
            try:
                m = Measurement.objects.get(id=m_id, customer=customer)
                label = all_cats.get(m.garment_category, m.garment_category.title())
                selected_items.append({
                    'type': m.garment_category,
                    'label': label,
                    'qty': 1,
                    'rate': '',
                    'measurement_id': m.id
                })
            except (Measurement.DoesNotExist, ValueError):
                continue
    else:
        garment_types = garments_qs.split(',') if garments_qs else []
        for gtype in garment_types:
            if not gtype: continue
            label = all_cats.get(gtype, gtype.title())
            selected_items.append({
                'type': gtype,
                'label': label,
                'qty': 1,
                'rate': '',
                'measurement_id': ''
            })

    context = {
        'customer': customer,
        'order_number': mock_order_id,
        'selected_items': selected_items,
        'order_types': OrderType.choices,
        'current_order_type': order_type,
        'salespeople': Salesperson.objects.filter(is_active=True),
    }
    return render(request, 'orders/order_form.html', context)


def num2words(num):
    # Very basic Indian numbering system converter up to Crores
    under_20 = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['Zero', 'Ten', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

    if num == 0: return under_20[0]
    
    def convert(n):
        if n < 20:
            return under_20[n]
        if n < 100:
            return tens[n // 10] + ('' if n % 10 == 0 else ' ' + under_20[n % 10])
        if n < 1000:
            return under_20[n // 100] + ' Hundred' + ('' if n % 100 == 0 else ' and ' + convert(n % 100))
        if n < 100000:
            return convert(n // 1000) + ' Thousand' + ('' if n % 1000 == 0 else ' ' + convert(n % 1000))
        if n < 10000000:
            return convert(n // 100000) + ' Lakh' + ('' if n % 100000 == 0 else ' ' + convert(n % 100000))
        return convert(n // 10000000) + ' Crore' + ('' if n % 10000000 == 0 else ' ' + convert(n % 10000000))
    
    return convert(int(num)) + ' Only'

@login_required
def order_print(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = order.items.all()
    
    # Get measurements for each item in the order
    measurements = []
    from measurements.models import get_all_garment_parameters, get_all_garment_categories
    all_params = get_all_garment_parameters()
    all_cats = dict(get_all_garment_categories())

    for item in items:
        m = item.measurement
        if m:
            params = all_params.get(m.garment_category, [])
            ordered_values = []
            for p in params:
                ordered_values.append({'label': p, 'value': m.values.get(p, '-')})
            
            measurements.append({
                'category_display': all_cats.get(m.garment_category, m.garment_category.title()),
                'data': ordered_values,
                'notes': m.notes,
                'is_sample_product': m.is_sample_product
            })
        elif item.garment_category:
            # Fallback for legacy items
            from measurements.models import Measurement
            m = Measurement.objects.filter(customer=order.customer, garment_category=item.garment_category).order_by('-updated_at').first()
            if m:
                params = all_params.get(item.garment_category, [])
                ordered_values = []
                for p in params:
                    ordered_values.append({'label': p, 'value': m.values.get(p, '-')})
                
                measurements.append({
                    'category_display': all_cats.get(item.garment_category, item.garment_category.title()),
                    'data': ordered_values,
                    'notes': m.notes,
                    'is_sample_product': m.is_sample_product
                })
                
    amount_in_words = num2words(order.final_amount)

    # Limit table rows to 6 (items + fillers) to prevent A5 page overflow
    max_total_rows = 6
    num_items = len(items)
    num_fillers = max(0, max_total_rows - num_items)
    filler_rows = range(num_fillers)

    # Chunk measurements into groups of max 3 items
    measurement_groups = [measurements[i:i+3] for i in range(0, len(measurements), 3)]

    context = {
        'order': order,
        'items': items,
        'measurements': measurements,
        'measurement_groups': measurement_groups,
        'filler_rows': filler_rows,
        'amount_in_words': amount_in_words,
    }
    return render(request, 'orders/order_print.html', context)

def filtered_orders_from_request(request):
    orders = Order.objects.select_related('customer').all().order_by('-created_at')
    
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)

    q = (request.GET.get('q') or '').strip()
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q)
            | Q(customer__full_name__icontains=q)
            | Q(customer__phone__icontains=q)
        )

    red_flag = request.GET.get('red_flag')
    if red_flag == '1':
        orders = orders.filter(is_red_flagged=True)

    delivery_date_str = request.GET.get('delivery_date') or request.GET.get('delivery_from')
    return_date_str = request.GET.get('return_date') or request.GET.get('return_from')
    
    delivery_date = parse_date(delivery_date_str) if delivery_date_str else None
    return_date = parse_date(return_date_str) if return_date_str else None

    if delivery_date:
        orders = orders.filter(delivery_date=delivery_date)
    if return_date:
        orders = orders.filter(return_date=return_date)

    due = request.GET.get('due')
    today = timezone.localdate()
    if due == 'balance':
        orders = orders.filter(grand_total__gt=0)
    elif due == 'today':
        orders = orders.filter(delivery_date=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED])
    elif due == 'overdue':
        orders = orders.filter(delivery_date__lt=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED])

    return orders, {
        'current_status': status,
        'statuses': OrderStatus.choices,
        'q': q,
        'delivery_date': delivery_date,
        'return_date': return_date,
        'due': due,
        'red_flag': red_flag,
    }


@login_required
def order_list(request):
    orders, filters_context = filtered_orders_from_request(request)

    context = {
        'orders': orders,
        **filters_context,
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def order_list_print(request):
    orders, filters_context = filtered_orders_from_request(request)
    generated_at = timezone.localtime()
    total_amount = sum(order.final_amount for order in orders)

    context = {
        'orders': orders,
        'generated_at': generated_at,
        'total_amount': total_amount,
        **filters_context,
    }
    return render(request, 'orders/order_list_print.html', context)

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        try:
            update_order_from_post(order, request.POST)
            messages.success(request, 'Order updated.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        return redirect('order_detail', order_id=order.id)
        
    items = order.items.all()
    
    from measurements.models import get_all_garment_parameters
    context = {
        'order': order,
        'items': items,
        'statuses': OrderStatus.choices,
        'balance_due': order.balance_due,
        'salespeople': Salesperson.objects.filter(is_active=True),
        'garment_parameters': get_all_garment_parameters(),
    }
    return render(request, 'orders/order_detail.html', context)


@login_required
def delivery_schedule(request):
    from django.db.models import Sum, Count
    today = timezone.localdate()

    from django.utils.dateparse import parse_date
    
    # Parse filter inputs
    filter_date_str = request.GET.get('date', '')
    filter_from_str = request.GET.get('from', '')
    filter_to_str = request.GET.get('to', '')
    
    filter_date = parse_date(filter_date_str) if filter_date_str else None
    filter_from = parse_date(filter_from_str) if filter_from_str else None
    filter_to = parse_date(filter_to_str) if filter_to_str else None
    
    filter_status = request.GET.get('status', '')
    q = (request.GET.get('q') or '').strip()

    orders = Order.objects.select_related('customer').prefetch_related('items').order_by('delivery_date', 'customer__full_name')

    # Default: if no filters at all, show next 30 days + overdue
    if not any([filter_date_str, filter_from_str, filter_to_str, filter_status, q]):
        orders = orders.exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED])
    else:
        if filter_date:
            orders = orders.filter(delivery_date=filter_date)
        if filter_from:
            orders = orders.filter(delivery_date__gte=filter_from)
        if filter_to:
            orders = orders.filter(delivery_date__lte=filter_to)
        if filter_status:
            orders = orders.filter(status=filter_status)
        if q:
            orders = orders.filter(
                Q(order_number__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__phone__icontains=q)
            )

    # Group orders by delivery_date
    from collections import defaultdict
    grouped = defaultdict(list)
    for order in orders:
        grouped[order.delivery_date].append(order)

    # Sort groups: overdue first, then ascending
    def sort_key(d):
        return (0 if d < today else 1, d)

    grouped_sorted = sorted(grouped.items(), key=lambda x: sort_key(x[0]))

    # Summary stats
    total_orders = orders.count()
    overdue_count = orders.filter(delivery_date__lt=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED]).count()
    due_today_count = orders.filter(delivery_date=today).exclude(status__in=[OrderStatus.DELIVERED, OrderStatus.CANCELLED]).count()
    total_balance = sum(o.balance_due for o in orders)

    context = {
        'grouped_orders': grouped_sorted,
        'today': today,
        'filter_date': filter_date,
        'filter_from': filter_from,
        'filter_to': filter_to,
        'filter_status': filter_status,
        'statuses': OrderStatus.choices,
        'q': q,
        'total_orders': total_orders,
        'overdue_count': overdue_count,
        'due_today_count': due_today_count,
        'total_balance': total_balance,
    }
    return render(request, 'orders/delivery_schedule.html', context)


@login_required
def order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        order_number = order.order_number
        customer_name = order.customer.full_name
        order.delete()  # CASCADE deletes OrderItems automatically
        messages.success(request, f'Order {order_number} for {customer_name} has been permanently deleted.')
        return redirect('order_list')
    # If GET, just redirect back (no GET-based deletion)
    return redirect('order_detail', order_id=order_id)

@login_required
def order_edit_info(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == 'POST':
        try:
            update_order_info_from_post(order, request.POST)
            messages.success(request, 'Order info updated.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('order_detail', order_id=order_id)

@login_required
def order_item_edit(request, order_id, item_id):
    order = get_object_or_404(Order, id=order_id)
    item = get_object_or_404(OrderItem, id=item_id, order=order)
    if request.method == 'POST':
        try:
            update_order_item_from_post(item, request.POST)
            messages.success(request, f'Item "{item.description}" updated.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return redirect('order_detail', order_id=order_id)


@login_required
@require_POST
def api_update_order_shortcut(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Extract data from POST
    status = request.POST.get('status')
    payment_amount_str = request.POST.get('payment_amount')
    payment_method = request.POST.get('payment_method')
    
    post_data = {}
    if status:
        post_data['status'] = status
    if payment_amount_str:
        post_data['additional_payment'] = payment_amount_str
    if payment_method:
        post_data['payment_method'] = payment_method
        
    errors = []
    if post_data:
        try:
            update_order_from_post(order, post_data)
        except ValidationError as exc:
            errors.extend(exc.messages)
            
    if errors:
        return JsonResponse({'success': False, 'errors': errors})
        
    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'grand_total': str(order.grand_total),
        'status': order.status,
        'status_display': order.get_status_display(),
        'advance_paid': str(order.advance_paid),
        'payment_method': order.payment_method,
        'payment_method_display': order.get_payment_method_display(),
    })
