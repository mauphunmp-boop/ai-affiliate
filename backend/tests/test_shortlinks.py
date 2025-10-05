import os, sys, time
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

# Force in-memory DB
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from main import app, get_db
from database import Base
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
import crud, schemas


@pytest.fixture(scope="module")
def client():
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
    c = TestClient(app)

    # Seed one affiliate template
    with TestingSessionLocal() as db:
        crud.upsert_affiliate_template(
            db,
            schemas.AffiliateTemplateCreate(
                network="accesstrade",
                platform="tikivn",
                template="https://go.aff/?url={target}&sub1={sub1}",
                default_params={"sub1": "base"},
                enabled=True,
            ),
        )
    return c


def test_shortlink_generation_and_redirect_and_stats_filters(client):
    # Generate 3 shortlinks with different params
    toks = []
    for i in range(3):
        r = client.post(
            "/aff/convert",
            json={
                "platform": "tikivn",
                "url": f"https://tiki.vn/p{i}",
                "params": {"sub1": f"u{i}"},
            },
        )
        assert r.status_code == 200
        body = r.json()
        toks.append(body["short_url"].split("/r/")[-1])
        assert body["affiliate_url"].startswith("https://go.aff/?url=")

    # Click first token 2 times, second 1 time, third 0
    t1, t2, t3 = toks
    for _ in range(2):
        rr = client.get(f"/r/{t1}", follow_redirects=False)
        assert rr.status_code in (302, 307)
    rr = client.get(f"/r/{t2}", follow_redirects=False)
    assert rr.status_code in (302, 307)

    # List all
    r_all = client.get("/aff/shortlinks")
    assert r_all.status_code == 200
    arr = r_all.json()
    assert len(arr) >= 3

    # Filter min_clicks=2 should include only t1 (or any with >=2)
    r_min2 = client.get("/aff/shortlinks", params={"min_clicks": 2})
    assert r_min2.status_code == 200
    hits = {sl["token"] for sl in r_min2.json()}
    assert t1 in hits and t2 not in hits

    # Search by partial token
    part = t2[:4]
    r_q = client.get("/aff/shortlinks", params={"q": part})
    assert r_q.status_code == 200
    tokens_found = {sl["token"] for sl in r_q.json()}
    assert t2 in tokens_found

    # Order by clicks_desc: first element should have click_count >= others
    r_ord = client.get("/aff/shortlinks", params={"order": "clicks_desc"})
    assert r_ord.status_code == 200
    data = r_ord.json()
    if len(data) >= 2:
        assert data[0]["click_count"] >= data[1]["click_count"]

    # Detail of first token
    r_detail = client.get(f"/aff/shortlinks/{t1}")
    assert r_detail.status_code == 200
    assert r_detail.json()["token"] == t1

    # Delete third token
    r_del = client.delete(f"/aff/shortlinks/{t3}")
    assert r_del.status_code == 200 and r_del.json().get("ok") is True
    r_detail_missing = client.get(f"/aff/shortlinks/{t3}")
    assert r_detail_missing.status_code == 404
