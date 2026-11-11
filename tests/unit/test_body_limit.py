from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.errors import install_error_handlers
from api.middleware import limit_body_size

LIMIT = 16384


def _client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/echo")
    async def echo(request: Request):
        raw = await limit_body_size(request, LIMIT)
        return {"size": len(raw)}

    return TestClient(app)


def test_body_at_limit_is_accepted():
    r = _client().post("/echo", content=b"x" * LIMIT)
    assert r.status_code == 200 and r.json() == {"size": LIMIT}


def test_body_over_limit_is_refused():
    r = _client().post("/echo", content=b"x" * (LIMIT + 1))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_chunked_body_over_limit_is_refused():
    def chunks():
        for _ in range(20):
            yield b"x" * 1024

    r = _client().post("/echo", content=chunks())  # no Content-Length header
    assert r.status_code == 413
