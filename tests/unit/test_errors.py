from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import ApiError, install_error_handlers


def _client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/stock")
    def stock():
        raise ApiError(409, "OUT_OF_STOCK", "Not enough items available")

    @app.get("/boom")
    def boom():
        raise RuntimeError("password=secret SELECT * FROM orders")

    return TestClient(app, raise_server_exceptions=False)


def test_api_error_uses_contract_format():
    r = _client().get("/stock")
    assert r.status_code == 409
    assert r.json() == {"error": {"code": "OUT_OF_STOCK", "message": "Not enough items available"}}


def test_unknown_route_uses_contract_format():
    r = _client().get("/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_unexpected_error_leaks_nothing():
    r = _client().get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in r.text and "SELECT" not in r.text
