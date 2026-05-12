from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.measurement_profile, name='measurement_profile'),
    path('api/custom-category/add/', views.add_custom_category, name='add_custom_category'),
    path('api/custom-parameter/add/', views.add_custom_parameter, name='add_custom_parameter'),
]
