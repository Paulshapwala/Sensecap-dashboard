# apps/dashboard/views.py
from django.shortcuts import render
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from apps.weather.services import (
    get_latest_reading,
    get_readings,
    get_aggregates,
    get_device_status,
)

# PAGE VIEWS (render templates)

@login_required
def live(request):
    """GET / — Live dashboard page"""
    return render(request, 'dashboard/sse_live_dashboard.html')


@login_required
def history(request):
    """GET /history/ — Historical data page"""
    return render(request, 'dashboard/history.html')

# DATA ENDPOINTS (return JSON)

@login_required
@require_http_methods(["GET"])
def data_history(request):
    """GET /data/history/?start=2026-07-22T12:00:00+00:00&end=2026-07-22T13:00:00+00:00"""
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    
    if not start_str or not end_str:
        return JsonResponse({'error': 'start and end required'}, status=400)
    
    try:
        print(f"Parsing start: {start_str}")
        print(f"Parsing end: {end_str}")
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
        print(f"Parsed successfully: {start} to {end}")
    except (ValueError, TypeError) as e:
        print(f"Error parsing: {e}")
        return JsonResponse({'error': f'Invalid date format: {str(e)}'}, status=400)
    
    readings = get_readings(start, end)
    
    data = [
        {
            'time': r.received_at.isoformat(),
            'device_id': r.device_id,
            'temperature': r.temperature,
            'humidity': r.humidity,
            'pressure': r.pressure,
            'wind_speed': r.wind_speed,
            'wind_direction': r.wind_direction,
            'rainfall': r.rainfall,
            'light_intensity': r.light_intensity,
            'rssi': r.rssi,
            'snr': r.snr,
        }
        for r in readings
    ]
    
    return JsonResponse({'readings': data})

@login_required
@require_http_methods(["GET"])
def data_aggregates(request):
    """
    GET /data/aggregates/?start=2024-01-15&end=2024-01-22&period=hourly|daily
    Returns aggregated data (min, max, avg) for a period
    """
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    period = request.GET.get('period', 'hourly')  # hourly or daily
    
    if not start_str or not end_str:
        return JsonResponse({'error': 'start and end required'}, status=400)
    
    try:
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get aggregates from weather app
    aggregates = get_aggregates(start, end, period)
    
    # aggregates is already a dict/list, just return it
    return JsonResponse({'aggregates': aggregates})


@login_required
@require_http_methods(["GET"])
def data_device(request):
    """
    GET /data/device/
    Returns current device status (battery, signal strength, etc.)
    """
    status = get_device_status()
    return JsonResponse(status)
