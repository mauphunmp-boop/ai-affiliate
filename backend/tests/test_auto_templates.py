import os, sys, pytest

# Bắt buộc dùng SQLite in-memory cho test
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("AT_MOCK", "1")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from main import app, get_db
from database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import crud, schemas, models

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

    # Seed 2 campaigns APPROVED + running (merchant shopee, lazada)
    with TestingSessionLocal() as db:
        for m in ["shopee", "lazada"]:
            crud.upsert_campaign(db, schemas.CampaignCreate(
                campaign_id=f"CID_{m}",
                merchant=m,
                name=f"Camp {m}",
                status="running",
                user_registration_status="APPROVED",
            ))
    return TestClient(app)


def test_auto_generate_templates_creates_missing(client):
    # Lần 1: chưa có template nào -> tạo cả 2
    r1 = client.post("/aff/templates/auto-from-campaigns", json={"network": "accesstrade"})
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    created_platforms = sorted([c["platform"] for c in body1["created"]])
    assert created_platforms == ["lazada", "shopee"], body1
    assert sorted(body1["skipped"]) == []

    # Lần 2: đã có -> skipped cả 2
    r2 = client.post("/aff/templates/auto-from-campaigns", json={"network": "accesstrade"})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["created"] == []
    assert sorted(body2["skipped"]) == ["lazada", "shopee"], body2

    # Kiểm tra logic upsert: nếu gọi upsert với shopee thay đổi template -> cập nhật, không tạo mới
    r_up = client.post("/aff/templates/upsert", json={
        "network": "accesstrade",
        "platform": "shopee",
        "template": "https://go.aff/?url={target}&sub1={sub1}",
        "default_params": {"sub1": "fixed"}
    })
    assert r_up.status_code == 200
    # Gọi auto nữa -> shopee vẫn skipped
    r3 = client.post("/aff/templates/auto-from-campaigns", json={"network": "accesstrade"})
    assert r3.status_code == 200
    assert any(s == "shopee" for s in r3.json()["skipped"])  # vẫn skip
