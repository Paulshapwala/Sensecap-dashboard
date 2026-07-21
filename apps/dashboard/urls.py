# apps/dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Pages
    path('', views.live, name='live'),                          # GET /
    path('history/', views.history, name='history'),            # GET /history/
    path('login/', views.login_view, name='login'),             # GET /login/
    path('logout/', views.logout_view, name='logout'),          # GET /logout/
    
    # Data endpoints (JSON APIs)
    path('data/history/', views.data_history, name='data_history'),      # GET /data/history/?start=&end=
    path('data/aggregates/', views.data_aggregates, name='data_aggregates'),  # GET /data/aggregates/?start=&end=&period=
    path('data/device/', views.data_device, name='data_device'),          # GET /data/device/
]