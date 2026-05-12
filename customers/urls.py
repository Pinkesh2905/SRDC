from django.urls import path
from . import views

urlpatterns = [
    path('', views.customer_list, name='customer_list'),
    path('<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('api/by-phone/<str:phone>/', views.api_get_customer_by_phone, name='api_get_customer_by_phone'),
    path('api/search/', views.api_search_customers, name='api_search_customers'),
]
