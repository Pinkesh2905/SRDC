from django.urls import path
from . import views

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('new/', views.order_create, name='order_create'),
    path('delivery-schedule/', views.delivery_schedule, name='delivery_schedule'),
    path('print-list/', views.order_list_print, name='order_list_print'),
    path('<int:order_id>/', views.order_detail, name='order_detail'),
    path('<int:order_id>/edit-info/', views.order_edit_info, name='order_edit_info'),
    path('<int:order_id>/item/<int:item_id>/edit/', views.order_item_edit, name='order_item_edit'),
    path('<int:order_id>/print/', views.order_print, name='order_print'),
    path('<int:order_id>/delete/', views.order_delete, name='order_delete'),
    path('api/<int:order_id>/update-shortcut/', views.api_update_order_shortcut, name='api_update_order_shortcut'),
]
