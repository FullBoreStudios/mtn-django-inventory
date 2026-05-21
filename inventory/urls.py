from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('labels/<int:pk>/', views.label_print, name='label_print'),
    path('labels/', views.label_print_bulk, name='label_print_bulk'),
]
