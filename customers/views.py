from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from .models import Customer
from .utils import normalize_phone
from measurements.models import Measurement

@login_required
def api_get_customer_by_phone(request, phone):
    phone = normalize_phone(phone)
    customer = Customer.objects.filter(phone=phone).order_by('-updated_at').first()
    if not customer and not phone.startswith('+'):
        customer = Customer.objects.filter(phone__endswith=phone).order_by('-updated_at').first()

    if customer:
        measurements = Measurement.objects.filter(customer=customer)
        
        measurement_data = {}
        measurement_list = []
        for m in measurements:
            measurement_data[m.garment_category] = {
                'id': m.id,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_sample_product
            }
            measurement_list.append({
                'id': m.id,
                'category': m.garment_category,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_sample_product
            })

        return JsonResponse({
            'success': True,
            'customer': {
                'id': customer.id,
                'full_name': customer.full_name,
                'phone': customer.phone,
                'city': customer.city or '',
            },
            'measurements': measurement_data,
            'measurement_list': measurement_list,
        })
    else:
        return JsonResponse({'success': False, 'message': 'Customer not found'})

@login_required
def api_search_customers(request):
    """Search customers by name or phone. Returns up to 10 results."""
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    normalized_q = normalize_phone(q)
    customers = Customer.objects.filter(
        Q(full_name__icontains=q) | Q(phone__icontains=normalized_q or q)
    ).prefetch_related('measurements').order_by('-created_at')[:10]

    results = []
    for c in customers:
        # Get measurement categories for this customer (loads from prefetched relations)
        measurements_qs = c.measurements.all()
        measurement_data = {}
        measurement_list = []
        garment_list = []
        for m in measurements_qs:
            measurement_data[m.garment_category] = {
                'id': m.id,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_sample_product
            }
            measurement_list.append({
                'id': m.id,
                'category': m.garment_category,
                'values': m.values,
                'notes': m.notes,
                'is_sample_product': m.is_sample_product
            })
            garment_list.append(m.garment_category)

        results.append({
            'id': c.id,
            'full_name': c.full_name,
            'phone': c.phone,
            'city': c.city or '',
            'garments': garment_list,
            'measurements': measurement_data,
            'measurement_list': measurement_list,
        })

    return JsonResponse({'results': results})

from django.core.paginator import Paginator

@login_required
def customer_list(request):
    customers = Customer.objects.annotate(num_orders=Count('orders')).order_by('-created_at')
    
    # Simple search
    q = request.GET.get('q')
    if q:
        normalized_q = normalize_phone(q)
        customers = customers.filter(
            Q(full_name__icontains=q)
            | Q(phone__icontains=normalized_q or q)
            | Q(city__icontains=q)
        )
    
    paginator = Paginator(customers, 10)  # Show 10 customers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
        
    context = {
        'customers': page_obj,
        'q': q,
    }
    return render(request, 'customers/customer_list.html', context)

@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    orders = customer.orders.all().order_by('-created_at')
    measurements = customer.measurements.all().order_by('-updated_at')
    
    # Calculate lifetime value
    lifetime_value = sum(order.final_amount for order in orders if order.status != 'cancelled')
    
    context = {
        'customer': customer,
        'orders': orders,
        'measurements': measurements,
        'lifetime_value': lifetime_value,
    }
    return render(request, 'customers/customer_detail.html', context)
