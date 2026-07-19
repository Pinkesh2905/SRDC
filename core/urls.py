from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('search/', views.global_search, name='global_search'),
    path('payments/', views.payments_view, name='payments'),
    path('signup/', views.signup, name='signup'),
]
