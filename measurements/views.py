from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from measurements.models import Measurement, CustomGarmentCategory, CustomGarmentParameter, get_all_garment_categories, get_all_garment_parameters
from customers.models import Customer
from customers.utils import normalize_phone
import urllib.parse
from django.http import JsonResponse
import json

@login_required
def measurement_profile(request):
    if request.method == 'POST':
        # 1. Get or Create Customer
        customer_phone = request.POST.get('customer_phone')
        if not customer_phone or not customer_phone.strip():
            country_code = (request.POST.get('customer_country_code') or '').strip()
            phone_local = (request.POST.get('customer_phone_local') or '').strip()
            if phone_local:
                if country_code and not country_code.startswith('+'):
                    country_code = '+' + country_code
                customer_phone = country_code + phone_local
            else:
                customer_phone = ''

        customer_phone = normalize_phone(customer_phone)
        customer_name = (request.POST.get('customer_name') or '').strip()
        customer_city = (request.POST.get('customer_city') or '').strip()
        if not customer_phone or not customer_name:
            messages.error(request, 'Customer name and phone are required.')
            return redirect('measurement_profile')
        
        customer_id = request.POST.get('customer_id')
        created = False
        if customer_id:
            customer = get_object_or_404(Customer, id=customer_id)
            customer.phone = customer_phone
            customer.full_name = customer_name
            if customer_city is not None:
                customer.city = customer_city
            customer.save()
        else:
            # Look up customer by BOTH phone and name to reuse
            customer = Customer.objects.filter(phone=customer_phone, full_name=customer_name).first()
            if not customer:
                customer = Customer.objects.create(
                    phone=customer_phone,
                    full_name=customer_name,
                    city=customer_city
                )
                created = True
            else:
                if customer_city:
                    customer.city = customer_city
                    customer.save(update_fields=['city'])

        # 2. Extract selected garments to bill
        selected_to_bill = request.POST.getlist('bill_garment') # list of block IDs like "1", "2"
        garments_to_bill = []

        # 3. Process all garment blocks submitted
        block_ids = request.POST.getlist('garment_block_id')
        for block_id in block_ids:
            garment_type = request.POST.get(f'garment_type_{block_id}')
            if not garment_type:
                continue
                
            all_params = get_all_garment_parameters()
            parameters = all_params.get(garment_type, [])
            measure_values = {}
            import re
            for param in parameters:
                param_slug = re.sub(r'[^a-z0-9]', '_', param.lower())
                val = request.POST.get(f'measure_{block_id}_{param_slug}')
                if val:
                    measure_values[param] = val
                    
            # Save or Update Measurement
            m_id = request.POST.get(f'measurement_id_{block_id}')
            is_sample = request.POST.get(f'is_sample_{block_id}') == 'on'
            
            defaults = {
                'values': measure_values if not is_sample else {},
                'notes': (request.POST.get(f'notes_{block_id}') or '').strip(),
                'is_sample_product': is_sample,
                'garment_category': garment_type,
            }
            
            measurement = None
            if measure_values or is_sample:
                if m_id:
                    measurement = Measurement.objects.filter(id=m_id, customer=customer).first()
                    if measurement:
                        for k, v in defaults.items():
                            setattr(measurement, k, v)
                        measurement.save()
                
                if not measurement:
                    measurement = Measurement.objects.create(
                        customer=customer,
                        **defaults
                    )
                
            # If this block was selected for billing, add its ID
            if block_id in selected_to_bill and measurement:
                garments_to_bill.append(str(measurement.id))

        # 4. Redirect to Billing or stay on profile
        if 'save_garment' in request.POST:
            messages.success(request, 'Measurements saved successfully.')
            url = reverse('measurement_profile') + f"?customer_id={customer.id}"
            return redirect(url)

        # Redirect to Billing
        # We pass customer_id and selected measurement IDs in the query string
        measurements_qs = ",".join(garments_to_bill)
        url = reverse('order_create') + f"?customer_id={customer.id}&measurements={urllib.parse.quote(measurements_qs)}"
        return redirect(url)

    # GET request - render the page
    initial_phone = normalize_phone(request.GET.get('phone'))
    customer_id = request.GET.get('customer_id')
    initial_customer = None

    if customer_id:
        try:
            initial_customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            pass
    elif initial_phone:
        customers = Customer.objects.filter(phone=initial_phone)
        if customers.count() == 1:
            initial_customer = customers.first()

    initial_customer_data = None
    if initial_customer:
        measurements = Measurement.objects.filter(customer=initial_customer)
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
        initial_customer_data = {
            'id': initial_customer.id,
            'full_name': initial_customer.full_name,
            'phone': initial_customer.phone,
            'city': initial_customer.city or '',
            'measurements': measurement_data,
            'measurement_list': measurement_list
        }

    context = {
        'garment_categories': get_all_garment_categories(),
        'garment_parameters': get_all_garment_parameters(),
        'initial_phone': initial_phone,
        'initial_customer': initial_customer_data,
    }
    return render(request, 'measurements/measurement_profile.html', context)

@login_required
def add_custom_category(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            if name:
                cat, created = CustomGarmentCategory.objects.get_or_create(name=name)
                slug = name.lower().replace(' ', '_')
                return JsonResponse({'success': True, 'slug': slug, 'name': name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def add_custom_parameter(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            category_name = data.get('category_name', '').strip()
            name = data.get('name', '').strip()
            if category_name and name:
                param, created = CustomGarmentParameter.objects.get_or_create(category_name=category_name, name=name)
                return JsonResponse({'success': True, 'category_name': category_name, 'name': name})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})
