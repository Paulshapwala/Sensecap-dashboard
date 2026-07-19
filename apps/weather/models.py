from django.db import models


class WeatherReading(models.Model):
    """
    A single sensor reading from the SenseCAP S2120 station, relayed via TTN.
    Spec 4.1.

    Primary key: composite of (device_id, received_at) — no surrogate
    auto-increment id. This table is later converted to a TimescaleDB
    hypertable (partitioned on received_at, 7-day chunks) via a raw-SQL
    migration.

    Null policy: no field may be null except raw_payload.
    """

    device_id = models.CharField(max_length=255)
    received_at = models.DateTimeField()

    temperature = models.FloatField(help_text="°C")
    humidity = models.FloatField(help_text="%")
    pressure = models.FloatField(help_text="hPa")
    wind_speed = models.FloatField(help_text="m/s")
    wind_direction = models.FloatField(help_text="degrees, 0-360")
    rainfall = models.FloatField(help_text="mm")
    light_intensity = models.FloatField(help_text="lux")
    battery = models.FloatField(help_text="%", null=True, blank=True)
    rssi = models.IntegerField(help_text="dBm")
    snr = models.FloatField(help_text="dB")

    raw_payload = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["device_id", "received_at"], name="weather_reading_pk"
            )
        ]
        indexes = [
            models.Index(fields=["-received_at"], name="weather_received_at_desc"),
        ]
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.device_id} @ {self.received_at.isoformat()}"