import base64

from fastapi.testclient import TestClient

from backend.src.main import app


def test_web_basic_auth_protects_frontend_but_not_health(monkeypatch) -> None:
    monkeypatch.setenv("APP_BASIC_AUTH_USER", "demo")
    monkeypatch.setenv("APP_BASIC_AUTH_PASSWORD", "secret")
    client = TestClient(app)

    health = client.get("/api/health")
    denied = client.get("/")
    token = base64.b64encode(b"demo:secret").decode("ascii")
    allowed = client.get("/", headers={"Authorization": f"Basic {token}"})

    assert health.status_code == 200
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == 'Basic realm="SpeakWise"'
    assert allowed.status_code == 200
    assert "text/html" in allowed.headers["content-type"]
