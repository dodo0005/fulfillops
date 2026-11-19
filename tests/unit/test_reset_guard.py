import pytest

from common.config import load_settings
from common.reset_test_data import NotATestEnvironment, assert_test_environment


def settings(monkeypatch, app_env, db_name):
    monkeypatch.setenv("DATABASE_URL", f"postgresql://u:pw@db:5432/{db_name}")
    monkeypatch.setenv("APP_ENV", app_env)
    return load_settings()


def test_test_environment_is_allowed(monkeypatch):
    assert_test_environment(settings(monkeypatch, "test", "fulfillops_test"))


@pytest.mark.parametrize(
    ("app_env", "db_name"),
    [("lab", "fulfillops_test"), ("production", "fulfillops_test"), ("test", "fulfillops")],
)
def test_other_environments_are_refused(monkeypatch, app_env, db_name):
    with pytest.raises(NotATestEnvironment):
        assert_test_environment(settings(monkeypatch, app_env, db_name))
