from django.urls import path

from . import views


urlpatterns = [
    path('', views.salesperson_dashboard, name='salesperson_dashboard'),
    path('<int:pk>/', views.salesperson_detail, name='salesperson_detail'),
]
