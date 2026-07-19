import django.dispatch

# Fired immediately after every successful save_reading() call.
# Carries the WeatherReading instance as `instance`.
# Contract note (spec 4.1): only the `realtime` app listens to this signal.
reading_saved = django.dispatch.Signal()