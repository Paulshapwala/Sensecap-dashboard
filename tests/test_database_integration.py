"""
Integration tests - actually connects to Supabase / PostgreSQL.
Run with: pytest tests/test_database_integration.py -v
"""
import os
from django.conf import settings
from django.db import connection
from django.test import TestCase


class TestDatabaseIntegration(TestCase):
    """Integration tests that require an actual database connection."""

    def test_can_connect_and_execute_query(self):
        """Test that we can connect and run a simple query."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 AS test")
            result = cursor.fetchone()
            self.assertIsNotNone(result)
            self.assertEqual(result[0], 1)

    def test_database_engine_is_postgresql_when_url_present(self):
        """Verify PostgreSQL is used when DATABASE_URL is set."""
        if os.environ.get("DATABASE_URL"):
            engine = settings.DATABASES["default"]["ENGINE"]
            self.assertIn("postgresql", engine)

    def test_conn_max_age_is_configured(self):
        """Verify connection pooling (CONN_MAX_AGE) is enabled."""
        if os.environ.get("DATABASE_URL"):
            conn_max_age = settings.DATABASES["default"].get("CONN_MAX_AGE")
            self.assertEqual(conn_max_age, 600)

    def test_connect_timeout_is_configured(self):
        """Verify connect_timeout is present in OPTIONS."""
        if os.environ.get("DATABASE_URL"):
            options = settings.DATABASES["default"].get("OPTIONS", {})
            self.assertEqual(options.get("connect_timeout"), 10)

    def test_conn_health_checks_enabled(self):
        """Verify connection health checks are enabled (Django 4.1+)."""
        if os.environ.get("DATABASE_URL"):
            # dj_database_url puts this key when conn_health_checks=True
            self.assertTrue(
                settings.DATABASES["default"].get("CONN_HEALTH_CHECKS", False)
            )

    def test_supabase_host_and_name_are_present(self):
        """Basic sanity check that HOST and NAME were parsed from DATABASE_URL."""
        if os.environ.get("DATABASE_URL"):
            db = settings.DATABASES["default"]
            self.assertTrue(db.get("HOST"), "HOST should be set")
            self.assertTrue(db.get("NAME"), "NAME (database) should be set")
            self.assertTrue(db.get("USER"), "USER should be set")

    def test_sqlite_fallback_when_no_url(self):
        """When DATABASE_URL is missing we should fall back to SQLite."""
        if not os.environ.get("DATABASE_URL"):
            engine = settings.DATABASES["default"]["ENGINE"]
            self.assertIn("sqlite3", engine)