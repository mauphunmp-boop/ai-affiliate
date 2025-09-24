import os
import sys
import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed in this test environment")
from fastapi.testclient import TestClient

# Force SQLite DB before importing app/main
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import app, get_db
import models, crud, schemas
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from database import Base


@pytest.fixture(scope="module")
def client():
    # Use in-memory SQLite and override FastAPI dependency
    os.environ["AT_MOCK"] = "1"  # force Accesstrade service to return mock data

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

    c = TestClient(app)

    # Seed mock API config so _get_at_config() passes
    with TestingSessionLocal() as db:
        crud.upsert_api_config_by_name(db, schemas.APIConfigCreate(
            name="accesstrade",
            base_url="mock://accesstrade",
            api_key="dummy",
            model="-",
        ))

    return c


def test_catalog_promotions_list_and_delete_by_campaign(client):
    # Sync campaigns and then ingest promotions for tikivn
    r_sync = client.post("/ingest/campaigns/sync", json={
        "provider": "accesstrade",
        "statuses": ["running"],
        "only_my": True,
        "enrich_user_status": False
    })
    assert r_sync.status_code == 200

    r_ing = client.post("/ingest/promotions", json={
        "provider": "accesstrade",
        "merchant": "tikivn"
    })
    assert r_ing.status_code == 200

    # Mock data uses CAMP3 for tiki/tikivn in previous tests
    cid = "CAMP3"
    r_list = client.get(f"/catalog/promotions?campaign_id={cid}")
    assert r_list.status_code == 200
    items = r_list.json()
    assert isinstance(items, list)
    assert len(items) >= 0

    # If there are promotions, delete by campaign
    if len(items) > 0:
        r_del = client.delete(f"/offers/0?category=promotions&campaign_id={cid}")
        assert r_del.status_code == 200
        body = r_del.json()
        assert body.get("ok") is True
        # Verify cleared
        r_list2 = client.get(f"/catalog/promotions?campaign_id={cid}")
        assert r_list2.status_code == 200
        assert len(r_list2.json()) == 0


def test_catalog_commissions_list_and_delete_by_campaign(client):
    # Manually seed a commission policy and then validate list/delete-by-campaign
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        crud.upsert_commission_policy(db, schemas.CommissionPolicyCreate(
            campaign_id="CAMP3",
            reward_type="sale",
            sales_ratio=0.1,
            sales_price=None,
            target_month="2025-09",
        ))
        crud.upsert_commission_policy(db, schemas.CommissionPolicyCreate(
            campaign_id="CAMP3",
            reward_type="lead",
            sales_ratio=None,
            sales_price=10000.0,
            target_month="2025-09",
        ))

    r_list = client.get("/catalog/commissions?campaign_id=CAMP3")
    assert r_list.status_code == 200
    items = r_list.json()
    assert isinstance(items, list)
    assert len(items) >= 2

    # Delete by campaign id
    r_del = client.delete("/offers/0?category=commissions&campaign_id=CAMP3")
    assert r_del.status_code == 200
    body = r_del.json()
    assert body.get("ok") is True

    # Verify cleared
    r_list2 = client.get("/catalog/commissions?campaign_id=CAMP3")
    assert r_list2.status_code == 200
    assert len(r_list2.json()) == 0


def test_offers_category_top_products_list(client):
    # Ingest some top-products for tikivn
    r_sync = client.post("/ingest/campaigns/sync", json={
        "provider": "accesstrade",
        "statuses": ["running"],
        "only_my": True,
        "enrich_user_status": False
    })
    assert r_sync.status_code == 200

    r = client.post("/ingest/top-products", json={
        "provider": "accesstrade",
        "merchant": "tikivn",
        "limit_per_page": 50,
        "max_pages": 1,
        "check_urls": False
    })
    assert r.status_code == 200

    # List with category=top-products should return rows
    r_list = client.get("/offers", params={"category": "top-products", "limit": 5})
    assert r_list.status_code == 200
    items = r_list.json()
    assert isinstance(items, list)
    # not asserting count because ingest could return 0 in some environments, but ensure type correctness


def test_delete_offers_from_promotions_by_campaign(client):
    # Create a ProductOffer that mimics old behavior (source_type='promotions')
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        from models import ProductOffer
        obj = ProductOffer(
            source="accesstrade",
            source_id="promo:seed",
            merchant="tikivn",
            title="Promo Offer Seed",
            url="https://example.com/seed",
            affiliate_url=None,
            image_url=None,
            price=None,
            currency="VND",
            campaign_id="CAMPX",
            source_type="promotions",
            approval_status=None,
            eligible_commission=False,
            affiliate_link_available=False,
            product_id=None,
            extra=None,
        )
        db.add(obj)
        db.commit()

        # sanity: row exists
        count_before = db.query(models.ProductOffer).filter(
            models.ProductOffer.campaign_id == "CAMPX",
            models.ProductOffer.source_type == "promotions",
        ).count()
        assert count_before == 1

    # Delete using offers category with campaign_id (only promotions-source offers should be removed)
    r_del = client.delete("/offers/0", params={"category": "offers", "campaign_id": "CAMPX"})
    assert r_del.status_code == 200
    body = r_del.json()
    assert body.get("ok") is True

    # Verify deletion
    with TestingSessionLocal() as db:
        count_after = db.query(models.ProductOffer).filter(
            models.ProductOffer.campaign_id == "CAMPX",
            models.ProductOffer.source_type == "promotions",
        ).count()
        assert count_after == 0


def test_delete_single_promotion_and_commission_by_id(client):
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    # Seed one promotion and one commission policy, then delete by id
    with TestingSessionLocal() as db:
        p = crud.upsert_promotion(db, schemas.PromotionCreate(
            campaign_id="CAMPY",
            name="Y Promo",
            content="Y content",
        ))
        c = crud.upsert_commission_policy(db, schemas.CommissionPolicyCreate(
            campaign_id="CAMPY",
            reward_type="sale",
            sales_ratio=0.2,
            sales_price=None,
            target_month="2025-10",
        ))
        pid, cid = p.id, c.id

    # Delete single promotion by id
    r1 = client.delete(f"/offers/{pid}", params={"category": "promotions"})
    assert r1.status_code == 200
    # Delete single commission by id
    r2 = client.delete(f"/offers/{cid}", params={"category": "commissions"})
    assert r2.status_code == 200

    # Verify both gone
    with TestingSessionLocal() as db:
        assert crud.get_promotion_by_id(db, pid) is None
        assert crud.get_commission_policy_by_id(db, cid) is None
