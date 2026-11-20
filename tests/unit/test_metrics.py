from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from api.metrics import REGISTRY, BusinessCollector
from api.middleware import request_metrics


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_metrics)

    @app.get("/things/{thing_id}")
    def thing(thing_id: str):
        return {"id": thing_id}

    return app


def test_route_template_is_used_not_real_path():
    client = TestClient(_app())
    client.get("/things/abc-123")
    text = generate_latest(REGISTRY).decode()
    assert 'route="/things/{thing_id}"' in text
    assert "abc-123" not in text


def test_unknown_route_is_labelled_unmatched():
    TestClient(_app()).get("/nope/1")
    assert 'route="unmatched"' in generate_latest(REGISTRY).decode()


class _FakeConn:
    def __init__(self, row):
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, _sql):
        return self

    def fetchone(self):
        return self.row


class _FakePool:
    def __init__(self, row=None, fail=False):
        self.row, self.fail = row, fail

    def connection(self, timeout=None):
        if self.fail:
            raise ConnectionError("db down")
        return _FakeConn(self.row)


def test_business_collector_reads_totals():
    families = list(BusinessCollector(_FakePool(row=(10, 7, 1, 4))).collect())
    values = {f.name: f.samples[0].value for f in families}
    assert values == {
        "fulfillops_orders_created": 10,
        "fulfillops_orders_completed": 7,
        "fulfillops_orders_failed": 1,
        "fulfillops_worker_retries": 4,
    }


def test_business_collector_survives_db_outage():
    assert list(BusinessCollector(_FakePool(fail=True)).collect()) == []
