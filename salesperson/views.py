import json
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Avg, F
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render, get_object_or_404

from .models import Salesperson
from orders.models import Order, OrderItem


@login_required
def salesperson_dashboard(request):
    if request.method == 'POST':
        full_name = (request.POST.get('full_name') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        employee_code = (request.POST.get('employee_code') or '').strip() or None
        if not full_name:
            messages.error(request, 'Salesperson name is required.')
        else:
            Salesperson.objects.create(
                full_name=full_name,
                phone=phone,
                employee_code=employee_code,
            )
            messages.success(request, 'Salesperson added.')
        return redirect('salesperson_dashboard')

    salespeople = Salesperson.objects.annotate(
        total_orders=Count('orders'),
        total_amount=Sum('orders__final_amount'),
    )
    context = {
        'salespeople': salespeople,
        'active_count': Salesperson.objects.filter(is_active=True).count(),
        'total_count': Salesperson.objects.count(),
    }
    return render(request, 'salesperson/dashboard.html', context)

def format_inr(value):
    if not value: return '₹0'
    v = float(value)
    if v >= 100000: return f"₹{v/100000:.1f}L"
    if v >= 1000: return f"₹{v/1000:.1f}K"
    return f"₹{int(v)}"

@login_required
def salesperson_detail(request, pk):
    person = get_object_or_404(Salesperson, pk=pk)
    
    # Date Filtering
    period = request.GET.get('period', '30')
    now = timezone.now()
    if period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == '7':
        start_date = now - timedelta(days=7)
    elif period == 'all':
        start_date = None
    else: # default 30
        start_date = now - timedelta(days=30)
        period = '30'

    # Base Queries
    base_qs = Order.objects.filter(salesperson=person)
    all_store_qs = Order.objects.all()

    if start_date:
        period_qs = base_qs.filter(created_at__gte=start_date)
        all_store_period_qs = all_store_qs.filter(created_at__gte=start_date)
    else:
        period_qs = base_qs
        all_store_period_qs = all_store_qs

    # Basic Aggregates
    agg = period_qs.aggregate(
        rev=Sum('final_amount'),
        avg=Avg('final_amount')
    )
    total_rev = float(agg['rev'] or 0)
    avg_ord = float(agg['avg'] or 0)
    total_orders = period_qs.count()

    # Share in total revenue
    store_rev = float(all_store_period_qs.aggregate(total=Sum('final_amount'))['total'] or 0)
    share_pct = (total_rev / store_rev * 100) if store_rev > 0 else 0

    # Top Product
    period_items = OrderItem.objects.filter(order__in=period_qs)
    top_product = period_items.values('description').annotate(qty=Sum('quantity')).order_by('-qty').first()
    top_product_name = top_product['description'] if top_product else '—'
    top_product_qty = top_product['qty'] if top_product else 0

    # Pending Balances
    pend = period_qs.annotate(
        bal=F('final_amount') - F('advance_paid')
    ).filter(bal__gt=0).aggregate(total=Sum('bal'))
    total_pending = float(pend['total'] or 0)

    # Chart Data (Revenue Trend)
    chart_qs = period_qs.annotate(date=TruncDate('created_at')).values('date').annotate(daily=Sum('final_amount')).order_by('date')
    dates, revs = [], []
    for item in chart_qs:
        dates.append(item['date'].strftime('%b %d'))
        revs.append(float(item['daily'] or 0))

    # Top Customers for this salesperson
    top_customers = [
        {'name': tc['customer__full_name'], 'amount': format_inr(tc['spent'])}
        for tc in period_qs.values('customer__full_name').annotate(
            spent=Sum('final_amount')
        ).order_by('-spent')[:5]
    ]

    context = {
        'person': person,
        'period': period,
        'total_orders': total_orders,
        'total_rev_fmt': format_inr(total_rev),
        'avg_ord_fmt': format_inr(avg_ord),
        'share_pct': round(share_pct, 1),
        'top_product_name': top_product_name,
        'top_product_qty': top_product_qty,
        'total_pending_fmt': format_inr(total_pending),
        'chart_dates': json.dumps(dates),
        'chart_revs': json.dumps(revs),
        'top_customers': top_customers,
    }
    return render(request, 'salesperson/detail.html', context)
