import pytest

from common.config import load_settings

DB_URL = "postgresql://fulfillops:secret-pw@db:5432/fulfillops_test"


def test_defaults_and_database_name(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.delenv("QUEUE_BACKEND", raising=False)
    s = load_settings()
    assert s.queue_backend == "postgres"
    assert s.api_port == 8080
    assert s.max_body_bytes == 16384
    assert s.worker_max_attempts == 5
    assert s.database_name == "fulfillops_test"


def test_password_never_in_repr(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    assert "secret-pw" not in repr(load_settings())


def test_missing_database_url_fails(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()


def test_invalid_queue_backend_fails(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("QUEUE_BACKEND", "kafka")
    with pytest.raises(RuntimeError):
        load_settings()


def test_poison_mode_parsing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("POISON_TEST_MODE", "true")
    assert load_settings().poison_test_mode is True
