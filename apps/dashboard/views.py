# apps/dashboard/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone 
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
    """
    GET /data/history/?start=2026-07-22T12:00:00&end=2026-07-22T13:00:00
    Accepts times in user's local timezone, converts to UTC for query,
    returns times in user's local timezone for display.
    """
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    
    if not start_str or not end_str:
        return JsonResponse({'error': 'start and end required'}, status=400)
    
    try:
        # Parse incoming times as naive (no timezone info)
        start_naive = datetime.fromisoformat(start_str)
        end_naive = datetime.fromisoformat(end_str)
        
        # Localize to user's timezone (EAT), then convert to UTC for database query
        tz = timezone.get_current_timezone()
        start_tz = timezone.make_aware(start_naive, tz)
        end_tz = timezone.make_aware(end_naive, tz)
        
        # Convert to UTC for database query
        start_utc = start_tz.astimezone(dt_timezone.utc)
        end_utc = end_tz.astimezone(dt_timezone.utc)
        
        print(f"User selected (EAT): {start_tz} to {end_tz}")
        print(f"Query DB (UTC): {start_utc} to {end_utc}")
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': f'Invalid date format: {str(e)}'}, status=400)
    
    # Query database with UTC times
    readings = get_readings(start_utc, end_utc)
    
    # Convert results back to user's timezone for display
    tz = timezone.get_current_timezone()
    data = [
        {
            'time': readings_obj.received_at.astimezone(tz).isoformat(),
            'device_id': readings_obj.device_id,
            'temperature': readings_obj.temperature,
            'humidity': readings_obj.humidity,
            'pressure': readings_obj.pressure,
            'wind_speed': readings_obj.wind_speed,
            'wind_direction': readings_obj.wind_direction,
            'rainfall': readings_obj.rainfall,
            'light_intensity': readings_obj.light_intensity,
            'rssi': readings_obj.rssi,
            'snr': readings_obj.snr,
        }
        for readings_obj in readings
    ]
    
    return JsonResponse({'readings': data})

@login_required
@require_http_methods(["GET"])
def data_aggregates(request):
    """
    GET /data/aggregates/?start=2026-07-22&end=2026-07-23&period=hourly|daily
    Accepts times in user's local timezone, converts to UTC for query,
    returns times in user's local timezone for display.
    """
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    period = request.GET.get('period', 'hourly')
    
    if not start_str or not end_str:
        return JsonResponse({'error': 'start and end required'}, status=400)
    
    try:
        start_naive = datetime.fromisoformat(start_str)
        end_naive = datetime.fromisoformat(end_str)
        
        tz = timezone.get_current_timezone()
        start_tz = timezone.make_aware(start_naive, tz)
        end_tz = timezone.make_aware(end_naive, tz)
        
        start_utc = start_tz.astimezone(timezone.utc)
        end_utc = end_tz.astimezone(timezone.utc)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get aggregates from weather app
    aggregates = get_aggregates(start_utc, end_utc, period)
    
    # Convert period_start times back to user's timezone
    tz = timezone.get_current_timezone()
    for agg in aggregates:
        if 'period_start' in agg:
            period_dt = datetime.fromisoformat(agg['period_start'])
            period_aware = timezone.make_aware(period_dt, timezone.utc)
            agg['period_start'] = period_aware.astimezone(tz).isoformat()
    
    return JsonResponse({'aggregates': aggregates})


@login_required
@require_http_methods(["GET"])
def data_device(request):
    """
    GET /data/device/
    Returns current device status, with last_seen converted to user's timezone.
    """
    status = get_device_status()
    
    # Convert last_seen to user's timezone
    if 'last_seen' in status:
        tz = timezone.get_current_timezone()
        last_seen_dt = datetime.fromisoformat(status['last_seen'])
        last_seen_aware = timezone.make_aware(last_seen_dt, timezone.utc)
        status['last_seen'] = last_seen_aware.astimezone(tz).isoformat()
    
    return JsonResponse(status)