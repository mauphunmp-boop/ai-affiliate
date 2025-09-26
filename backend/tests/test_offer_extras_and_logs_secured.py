import os, sys, json
import pytest

# Ensure in-memory DB
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AT_MOCK", "1")
# Set admin key to test protection
os.environ.setdefault("ADMIN_API_KEY", "secret-key")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
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
    app.state.TestingSessionLocal = TestingSessionLocal

    # Seed api config
    with TestingSessionLocal() as db:
        crud.upsert_api_config_by_name(db, schemas.APIConfigCreate(
            name="accesstrade", base_url="mock://accesstrade", api_key="dummy", model="-",
        ))

    return TestClient(app)


def seed_offer_with_campaign(db):
    # Seed campaign
    camp = crud.upsert_campaign(db, schemas.CampaignCreate(
        campaign_id="CAMPX", merchant="tikivn", name="Tiki Camp", status="running", approval="auto"
    ))
    # Seed promotion & policy
    from models import Promotion, CommissionPolicy
    p = Promotion(campaign_id="CAMPX", name="Promo 1", content="Sale 50%")
    cp = CommissionPolicy(campaign_id="CAMPX", reward_type="CPS", sales_ratio=12.5)
    db.add_all([p, cp])
    db.commit()
    # Seed offer linking campaign
    crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(
        source="manual", source_id="ox1", merchant="tikivn", title="Offer X",
        url="https://tiki.vn/x", affiliate_url=None, image_url=None, price=100000, currency="VND",
        campaign_id="CAMPX", source_type="manual", extra=json.dumps({"desc":"Mô tả X"})
    ))


def test_offer_extras_endpoint(client):
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        seed_offer_with_campaign(db)
        # Lấy id offer vừa tạo
        from models import ProductOffer
        oid = db.query(ProductOffer.id).first()[0]

    r = client.get(f"/offers/{oid}/extras")
    assert r.status_code == 200
    body = r.json()
    assert body["offer"]["id"] == oid
    assert body["campaign"]["campaign_id"] == "CAMPX"
    assert body["counts"]["promotions"] >= 1
    assert body["counts"]["commission_policies"] >= 1


def test_logs_endpoints_protected(client, tmp_path, monkeypatch):
    # Prepare fake log dir
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    f = log_dir / "sample.jsonl"
    f.write_text("{\"event\":1}\n{\"event\":2}\n", encoding="utf-8")
    monkeypatch.setenv("API_LOG_DIR", str(log_dir))

    # Missing key -> 401
    r1 = client.get("/system/logs")
    assert r1.status_code == 401
    # Wrong key
    r2 = client.get("/system/logs", headers={"X-Admin-Key":"wrong"})
    assert r2.status_code == 401
    # Correct key
    r3 = client.get("/system/logs", headers={"X-Admin-Key":"secret-key"})
    assert r3.status_code == 200 and r3.json().get("ok") is True

    # Tail
    r4 = client.get("/system/logs/sample.jsonl", headers={"X-Admin-Key":"secret-key"})
    assert r4.status_code == 200
    assert r4.json().get("count") == 2

    # Tail limit param
    r5 = client.get("/system/logs/sample.jsonl", params={"n":1}, headers={"X-Admin-Key":"secret-key"})
    assert r5.status_code == 200
    assert r5.json().get("count") == 1
