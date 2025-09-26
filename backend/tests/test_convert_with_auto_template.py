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

    # Seed 1 campaign APPROVED (shopee)
    with TestingSessionLocal() as db:
        crud.upsert_campaign(db, schemas.CampaignCreate(
            campaign_id="CID_AUTO", merchant="shopee", name="Camp Shopee",
            status="running", user_registration_status="APPROVED"
        ))
    return TestClient(app)


def test_auto_template_then_convert(client):
    # Auto generate
    r = client.post("/aff/templates/auto-from-campaigns", json={"network": "accesstrade"})
    assert r.status_code == 200, r.text
    body = r.json()
    # Ít nhất 1 template được tạo hoặc skip nếu test chạy lại
    assert "shopee" in [c.get("platform") for c in body.get("created", [])] or "shopee" in body.get("skipped", [])

    # Convert một link cụ thể
    r_conv = client.post("/aff/convert", json={
        "url": "https://shopee.vn/product/999",
        "platform": "shopee",
        "params": {"sub1": "custom123"}
    })
    assert r_conv.status_code == 200, r_conv.text
    data = r_conv.json()
    assert data["affiliate_url"].startswith("https://")
    assert data["short_url"].startswith("/r/")
    # sub1 custom phải xuất hiện (trong deeplink hoặc query appended)
    assert "custom123" in data["affiliate_url"]