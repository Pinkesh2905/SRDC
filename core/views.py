from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate
from datetime import timedelta, datetime
from django.urls import reverse
from django.utils import timezone
from customers.models import Customer
from customers.utils import normalize_phone
from orders.models import Order, OrderItem, OrderStatus
import json


def format_inr(amount):
    """Format amount in Indian shorthand (₹1.0L, ₹13K, ₹500)"""
    amount = float(amount)
    if amount >= 100000:
        return f"₹{amount / 100000:.1f}L"
    elif amount >= 1000:
        val = amount / 1000
        return f"₹{int(val)}K" if val == int(val) else f"₹{val:.1f}K"
    else:
        return f"₹{int(amount)}"


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_first_setup'] = not User.objects.filter(is_staff=True).exists()
        return ctx

    def dispatch(self, request, *args, **kwargs):
        # Already logged in → go straight to dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


@login_required
def dashboard(request):
    today = timezone.localdate()

    time_filter = request.GET.get('filter', 'month')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if time_filter == 'today':
        start_date, end_date = today, today
        period_name = "Today"
    elif time_filter == 'week':
        start_date = today - timedelta(days=6)
        end_date = today
        period_name = "Last 7 days"
    elif time_filter == 'all':
        start_date = today - timedelta(days=36500) # 100 years
        end_date = today
        period_name = "All Time"
    elif time_filter == 'custom' and start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            period_name = f"{start_date.strftime('%d %b')} – {end_date.strftime('%d %b')}"
        except ValueError:
            start_date = today - timedelta(days=29)
            end_date, period_name, time_filter = today, "Last 30 days", 'month'
    else:
        time_filter = 'month'
        start_date = today - timedelta(days=29)
        end_date = today
        period_name = "Last 30 days"

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # ─── Period queryset ───
    period_qs = Order.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    )
    period_items = OrderItem.objects.filter(
        order__created_at__date__gte=start_date, order__created_at__date__lte=end_date
    )

    # ─── SCORECARD ROW 1 ───
    total_orders = period_qs.count()
    total_revenue = float(period_qs.aggregate(t=Sum('final_amount'))['t'] or 0)
    avg_order_value = total_revenue / total_orders if total_orders else 0

    top_product = period_items.values('description').annotate(
        qty=Sum('quantity')
    ).order_by('-qty').first()

    # ─── SCORECARD ROW 2 ───
    period_cids = list(period_qs.values_list('customer_id', flat=True).distinct())
    repeat_customers = Order.objects.filter(
        customer_id__in=period_cids,
        created_at__date__lt=start_date
    ).values('customer_id').distinct().count()
    new_customers = len(period_cids) - repeat_customers

    top_rev_product = period_items.values('description').annotate(
        rev=Sum('total_amount')
    ).order_by('-rev').first()

    adv = period_qs.aggregate(total=Sum('advance_paid'), avg=Avg('advance_paid'))
    total_advance = float(adv['total'] or 0)
    avg_advance = float(adv['avg'] or 0)

    cash_adv_qs = period_qs.filter(payment_method='cash', advance_paid__gt=0)
    cash_adv = float(cash_adv_qs.aggregate(t=Sum('advance_paid'))['t'] or 0)
    cash_orders_list = [
        {'id': o['order_number'], 'name': o['customer__full_name'], 'amount': float(o['advance_paid'])}
        for o in cash_adv_qs.values('order_number', 'customer__full_name', 'advance_paid').order_by('-created_at')
    ]

    online_adv_qs = period_qs.exclude(payment_method='cash').filter(advance_paid__gt=0)
    online_adv = float(online_adv_qs.aggregate(t=Sum('advance_paid'))['t'] or 0)
    online_orders_list = [
        {'id': o['order_number'], 'name': o['customer__full_name'], 'amount': float(o['advance_paid'])}
        for o in online_adv_qs.values('order_number', 'customer__full_name', 'advance_paid').order_by('-created_at')
    ]

    pending_qs = period_qs.annotate(
        bal=F('final_amount') - F('advance_paid')
    ).filter(bal__gt=0)
    
    pend_agg = pending_qs.aggregate(total=Sum('bal'), avg=Avg('bal'))
    total_pending = float(pend_agg['total'] or 0)
    avg_pending = float(pend_agg['avg'] or 0)
    
    pending_orders_list = [
        {'id': o['order_number'], 'name': o['customer__full_name'], 'amount': float(o['bal'])}
        for o in pending_qs.values('order_number', 'customer__full_name', 'bal').order_by('-created_at')
    ]

    # ─── REVENUE TREND ───
    daily_qs = period_qs.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(rev=Sum('final_amount')).order_by('date')
    daily_map = {r['date']: float(r['rev'] or 0) for r in daily_qs}

    trend_labels, trend_data = [], []
    for i in range((end_date - start_date).days + 1):
        d = start_date + timedelta(days=i)
        trend_labels.append(d.strftime('%d %b %y'))
        trend_data.append(daily_map.get(d, 0))

    # ─── PRODUCT PERFORMANCE ───
    prod_perf = list(period_items.values('description').annotate(
        qty=Sum('quantity')
    ).order_by('-qty')[:8])

    # ─── TOP CUSTOMERS ───
    top_customers = [
        {'name': tc['customer__full_name'], 'amount': format_inr(tc['spent'])}
        for tc in period_qs.values('customer__full_name').annotate(
            spent=Sum('final_amount')
        ).order_by('-spent')[:5]
    ]

    # ─── PRODUCT MOVEMENT ───
    all_prods = list(period_items.values('description').annotate(
        qty=Sum('quantity')
    ).order_by('-qty'))
    fast_moving = all_prods[:3]
    slow_moving = list(reversed(all_prods[-3:])) if len(all_prods) > 3 else []

    context = {
        'time_filter': time_filter,
        'period_name': period_name,
        'start_date_str': start_date_str or '',
        'end_date_str': end_date_str or '',
        # Row 1
        'total_orders': total_orders,
        'total_revenue_fmt': format_inr(total_revenue),
        'avg_order_value_fmt': format_inr(avg_order_value),
        'top_product_name': top_product['description'] if top_product else '—',
        'top_product_units': top_product['qty'] if top_product else 0,
        # Row 2
        'new_customers': new_customers,
        'repeat_customers': repeat_customers,
        'top_rev_product_name': top_rev_product['description'] if top_rev_product else '—',
        'top_rev_product_amt': format_inr(float(top_rev_product['rev'])) if top_rev_product else '₹0',
        'total_advance_fmt': format_inr(total_advance),
        'cash_adv_fmt': format_inr(cash_adv),
        'online_adv_fmt': format_inr(online_adv),
        'cash_orders_json': json.dumps(cash_orders_list),
        'online_orders_json': json.dumps(online_orders_list),
        'pending_orders_json': json.dumps(pending_orders_list),
        'avg_advance_fmt': format_inr(avg_advance),
        'total_pending_fmt': format_inr(total_pending),
        'avg_pending_fmt': format_inr(avg_pending),
        # Charts JSON
        'trend_labels_json': json.dumps(trend_labels),
        'trend_data_json': json.dumps(trend_data),
        'prod_labels_json': json.dumps([p['description'] for p in prod_perf]),
        'prod_qtys_json': json.dumps([p['qty'] for p in prod_perf]),
        'new_cust_count': new_customers,
        'repeat_cust_count': repeat_customers,
        # Lists
        'top_customers': top_customers,
        'fast_moving': fast_moving,
        'slow_moving': slow_moving,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def global_search(request):
    q = (request.GET.get('q') or '').strip()
    if not q:
        return redirect('dashboard')

    phone = normalize_phone(q)
    if phone:
        customer = Customer.objects.filter(phone__icontains=phone).order_by('-updated_at').first()
        if customer:
            return redirect('customer_detail', customer_id=customer.id)

    order = Order.objects.filter(order_number__icontains=q).order_by('-created_at').first()
    if order:
        return redirect('order_detail', order_id=order.id)

    customer = Customer.objects.filter(full_name__icontains=q).order_by('-updated_at').first()
    if customer:
        return redirect('customer_detail', customer_id=customer.id)

    return redirect(f"{reverse('order_list')}?q={q}")


def signup(request):
    from django.contrib.auth.models import User
    from django.contrib.auth import login, authenticate

    # If already logged in, go to dashboard (prevents back-button returning to signup)
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Only allow if no staff/superuser exists yet, OR if called by a superuser to add more staff
    existing_users = User.objects.filter(is_staff=True).exists()
    if existing_users and not (request.user.is_authenticated and request.user.is_superuser):
        return redirect('login')

    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = request.POST
        full_name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role', 'staff').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not full_name:
            errors['full_name'] = 'Full name is required.'
        if not username:
            errors['username'] = 'Username is required.'
        elif User.objects.filter(username=username).exists():
            errors['username'] = 'This username is already taken.'
        if len(password1) < 6:
            errors['password1'] = 'Password must be at least 6 characters.'
        if password1 != password2:
            errors['password2'] = 'Passwords do not match.'

        if not errors:
            first_name = full_name.split()[0] if full_name else ''
            last_name = ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else ''
            user = User.objects.create_user(
                username=username,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,
                is_superuser=(role == 'owner'),
            )
            # Store phone in profile if available (use email field as fallback)
            if phone:
                user.email = phone
                user.save(update_fields=['email'])

            if not existing_users:
                # Auto-login on first setup
                user = authenticate(request, username=username, password=password1)
                login(request, user)
                return redirect('dashboard')
            else:
                from django.contrib import messages
                messages.success(request, f"Staff member '{full_name}' created successfully.")
                return redirect('dashboard')

    context = {
        'errors': errors,
        'form_data': form_data,
        'is_first_setup': not existing_users,
    }
    return render(request, 'registration/signup.html', context)
