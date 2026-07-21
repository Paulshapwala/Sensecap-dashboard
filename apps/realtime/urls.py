# apps/realtime/urls.py
from django.urls import path
from . import views

app_name = 'realtime'

urlpatterns = [
    path('stream/', views.stream, name='stream'),
]