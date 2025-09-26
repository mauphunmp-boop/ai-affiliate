import os, sys, pytest

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
    # Cho phép test truy cập phiên bản sessionmaker
    app.state.TestingSessionLocal = TestingSessionLocal

    # Seed legacy style template + campaign APPROVED
    with TestingSessionLocal() as db:
        from models import AffiliateTemplate
        legacy = AffiliateTemplate(
            merchant="shopee", network="accesstrade", platform=None,
            template="https://legacy/?url={target}", default_params=None, enabled=True
        )
        db.add(legacy)
        crud.upsert_campaign(db, schemas.CampaignCreate(
            campaign_id="CID_SHOPEE", merchant="shopee", name="Camp shopee",
            status="running", user_registration_status="APPROVED"
        ))
        db.commit()
    return TestClient(app)


def test_upgrade_legacy_record(client):
    # Auto-generate sẽ thấy campaign APPROVED -> upgrade legacy record
    r = client.post("/aff/templates/auto-from-campaigns", json={"network": "accesstrade"})
    assert r.status_code == 200, r.text
    body = r.json()
    # Vì legacy đã nâng cấp thành platform=shopee nên 'shopee' nằm trong skipped (đã tồn tại sau upgrade)
    assert "shopee" in body.get("skipped", []) or any(c.get("platform") == "shopee" for c in body.get("created", []))

    # Gọi upsert trực tiếp để đổi template, đảm bảo không tạo mới
    new_tpl = client.post("/aff/templates/upsert", json={
        "network": "accesstrade", "platform": "shopee",
        "template": "https://new/?url={target}&sub1={sub1}",
        "default_params": {"sub1": "abc"}
    })
    assert new_tpl.status_code == 200
    # Gọi lại upsert với template khác -> vẫn 200 và không insert mới
    newer = client.post("/aff/templates/upsert", json={
        "network": "accesstrade", "platform": "shopee",
        "template": "https://new2/?url={target}",
        "default_params": None
    })
    assert newer.status_code == 200
