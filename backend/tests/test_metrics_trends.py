import time, os, sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text as _text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from main import app, get_db  # type: ignore
import models  # type: ignore
from database import Base


@pytest.fixture(scope="module", autouse=True)
def _setup_db():
    os.environ.setdefault("AT_MOCK", "1")
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.TestingSessionLocal = TestingSessionLocal
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client():
    return TestClient(app)


def _insert_metric(name: str, value: float, session_id: str = "s1"):
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    db = TestingSessionLocal()
    try:
        m = models.WebVitalMetric(
            name=name, value=value, rating="good", session_id=session_id
        )
        db.add(m)
        db.commit()
    finally:
        db.close()


def test_trends_basic(client):
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        db.execute(_text("DELETE FROM web_vitals"))
        db.commit()
    for i in range(5):
        _insert_metric("LCP", 1000 + i * 100)
        time.sleep(0.002)
    for i in range(5):
        _insert_metric("CLS", 0.05 + i * 0.01)
        time.sleep(0.002)
    res = client.get(
        "/metrics/web-vitals/trends?window_minutes=10&buckets=4&names=LCP,CLS"
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "series" in data and "LCP" in data["series"] and "CLS" in data["series"]
    assert len(data["series"]["LCP"]) == 4
    point = data["series"]["LCP"][0]
    for k in ("t", "count", "avg", "p50", "p75", "p95"):
        assert k in point


def test_summary_endpoint(client):
    res = client.get("/metrics/web-vitals/summary?window_minutes=120")
    assert res.status_code == 200
    js = res.json()
    assert "metrics" in js
