import os
import time
import base64
import json
import hmac
import hashlib
from fastapi.testclient import TestClient

# Import app and helpers
from backend import main as backend_main
from backend.main import app, AFF_SECRET


def make_token(url: str, ts: int | None = None) -> str:
    payload = {"u": url, "ts": ts or int(time.time())}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(AFF_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def test_redirect_valid_token(monkeypatch):
    monkeypatch.setattr(backend_main, "AFF_TOKEN_TTL_SEC", 5, raising=False)
    with TestClient(app) as c:
        token = make_token("http://testserver/health")
        r = c.get(f"/r/{token}", follow_redirects=False)
        assert r.status_code == 302


def test_redirect_expired_token(monkeypatch):
    monkeypatch.setattr(backend_main, "AFF_TOKEN_TTL_SEC", 1, raising=False)
    with TestClient(app) as c:
        token = make_token("http://testserver/health", ts=int(time.time()) - 10)
        r = c.get(f"/r/{token}", follow_redirects=False)
        assert r.status_code == 400
        assert "expired" in r.json()["detail"]


def test_require_token_in_db(monkeypatch):
    # Turn on DB requirement; token is not in DB -> 404
    monkeypatch.setattr(backend_main, "AFF_TOKEN_TTL_SEC", 60, raising=False)
    monkeypatch.setattr(backend_main, "AFF_REQUIRE_TOKEN_IN_DB", True, raising=False)
    with TestClient(app) as c:
        token = make_token("http://testserver/health")
        r = c.get(f"/r/{token}", follow_redirects=False)
        assert r.status_code == 404
