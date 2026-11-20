import pytest

from common.config import load_settings
from worker.processor import POISON_CUSTOMER_ID, compute_backoff, is_poison


def no_jitter() -> float:
    return 0.0


def test_backoff_doubles():
    delays = [compute_backoff(a, 1, 30, no_jitter) for a in range(1, 6)]
    assert delays == [1, 2, 4, 8, 16]


def test_backoff_is_capped():
    assert compute_backoff(20, 1, 30, no_jitter) == 30


@pytest.mark.parametrize("attempt", range(0, 12))
def test_backoff_jitter_is_bounded_and_positive(attempt):
    delay = compute_backoff(attempt, 1, 30, lambda: 1.0)
    assert 0 < delay <= 33


@pytest.fixture
def settings(monkeypatch):
    def make(poison_mode: str):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:pw@db/fulfillops_test")
        monkeypatch.setenv("POISON_TEST_MODE", poison_mode)
        return load_settings()

    return make


def test_poison_only_when_mode_enabled(settings):
    assert is_poison(POISON_CUSTOMER_ID, settings("true")) is True
    assert is_poison(POISON_CUSTOMER_ID, settings("false")) is False
    assert is_poison("CUST-042", settings("true")) is False
