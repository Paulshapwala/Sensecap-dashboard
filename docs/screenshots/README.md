# Screenshot context — 12 November 2026

All images in this directory are unretouched browser captures of a **local demonstration using synthetic data**. No real browsing history, production database, physical sensor feed or hosted deployment is represented.

- `sensecap-live-dashboard-sample-data.png`: populated dashboard using the existing SSE endpoint through Gunicorn/gevent. Redis, SQLite and seeded weather readings were local; no application source changes were needed. “Connected” refers to the local application stream, not a real sensor.
- `sensecap-history-sample-data.png`: successful date-filtered retrieval of synthetic readings for `DEMO-SYNTHETIC-DATA`. This shows the working table, not charts or the failing aggregate endpoint.

Django's development server rejected the stream response's Connection header; Gunicorn/gevent delivered the initial stored reading. The history page's bottom summary appears to map pressure to rainfall and count to wind speed; it is not verified as correct. Device-status and aggregate endpoint failures remain unresolved. No real TTN/MQTT connection was attempted.
