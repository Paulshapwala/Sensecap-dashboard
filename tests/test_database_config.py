"""
Database configuration tests - configuration only (no DB needed).
"""
import os
import pytest
from django.conf import settings


@pytest.mark.django_db(databases={})
class TestDatabaseConfiguration:
    """Test database configuration without connecting to the database."""

    def test_postgres_backend_is_configured(self):
        """Test that PostgreSQL backend is configured when DATABASE_URL is set."""
        db_config = settings.DATABASES["default"]
        
        if os.environ.get("DATABASE_URL"):
            assert db_config["ENGINE"] == "django.db.backends.postgresql"
        else:
            assert db_config["ENGINE"] == "django.db.backends.sqlite3"

    def test_database_configuration_has_required_fields(self):
        """Test that database config has ENGINE and NAME."""
        db_config = settings.DATABASES["default"]
        assert "ENGINE" in db_config
        assert "NAME" in db_config

    def test_postgres_has_host_and_user(self):
        """Test PostgreSQL has connection details."""
        db_config = settings.DATABASES["default"]
        
        if "postgresql" in db_config.get("ENGINE", ""):
            assert "HOST" in db_config
            assert "USER" in db_config
            assert db_config["HOST"]

    def test_sqlite_path_is_correct(self):
        """Test SQLite database path ends with db.sqlite3."""
        db_config = settings.DATABASES["default"]
        
        if "sqlite3" in db_config.get("ENGINE", ""):
            assert str(db_config["NAME"]).endswith("db.sqlite3")


@pytest.mark.django_db(databases={})
class TestEnvironmentVariable:
    """Test environment variables."""

    def test_database_url_is_postgresql(self):
        """Test DATABASE_URL is PostgreSQL format if set."""
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            assert database_url.startswith(("postgres://", "postgresql://"))

    def test_databases_configured(self):
        """Test DATABASES is configured."""
        assert settings.DATABASES is not None
        assert "default" in settings.DATABASES