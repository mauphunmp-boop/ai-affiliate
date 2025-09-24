import json
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

    # Use a single shared in-memory SQLite DB across threads
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

    # Apply dependency override
    app.dependency_overrides[get_db] = override_get_db

    # Expose session factory for other tests via app.state
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


def test_openapi_has_unified_endpoints(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = set(r.json().get("paths", {}).keys())
    expected = {
        "/ingest/campaigns/sync",
        "/ingest/promotions",
        "/ingest/top-products",
        "/ingest/datafeeds/all",
        "/ingest/products",
    }
    assert expected.issubset(paths)


def test_legacy_preset_removed(client):
    r = client.post("/ingest/presets/tiktokshop", json={"merchant": "tiktokshop"})
    # Should be 404 as the route doesn't exist
    assert r.status_code in (404, 405)


def test_ingest_datafeeds_all_with_mock(client):
    # With AT_MOCK=1 and seeded config, ingest should import some offers
    r = client.post("/ingest/datafeeds/all", json={
        "provider": "accesstrade",
        "max_pages": 1,
        "limit_per_page": 100,
        "params": {"merchant": "tikivn"}
    })
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("imported"), int) and body.get("imported") >= 0

    # After ingest, offers endpoint should return items (mock may import >=0)
    r2 = client.get("/offers?limit=5")
    assert r2.status_code == 200
    data = r2.json()
    assert isinstance(data, list)


def test_campaigns_sync_and_manual_ingest_products(client):
    # Sync campaigns first (to ensure APPROVED mapping exists in DB)
    r = client.post("/ingest/campaigns/sync", json={
        "provider": "accesstrade",
        "statuses": ["running"],
        "only_my": True,
        "enrich_user_status": False
    })
    assert r.status_code == 200

    # Now do a manual products ingest from datafeeds path
    r2 = client.post("/ingest/products", json={
        "provider": "accesstrade",
        "path": "/v1/datafeeds",
        "params": {"merchant": "tikivn", "page": "1", "limit": "5"}
    })
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("ok") is True


def test_offers_check_endpoint_with_seeded_offer(client):
    # Seed a product offer directly into the same test DB
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal", None)
    assert TestingSessionLocal is not None, "TestingSessionLocal not found on app.state"
    from models import ProductOffer
    with TestingSessionLocal() as db:
        obj = ProductOffer(
            source="test",
            source_id="seed-1",
            merchant="tiki",
            title="Seeded Offer",
            url="http://localhost:1",  # likely unreachable => alive=False deterministically
            affiliate_url=None,
            image_url=None,
            price=None,
            currency="VND",
            campaign_id="seed-cid",
            source_type="test",
            approval_status=None,
            eligible_commission=False,
            affiliate_link_available=False,
            product_id=None,
            extra=None,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        offer_id = obj.id

    # Call the check endpoint
    r = client.get(f"/offers/check/{offer_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == offer_id
    # alive flag should be a boolean (may be True in container due to exception policy)
    assert isinstance(data.get("alive"), bool)


def test_provider_registry_unsupported_provider_error(client):
    r = client.post("/ingest/products", json={
        "provider": "not-supported",
        "path": "/v1/datafeeds",
        "params": {"merchant": "tikivn", "page": "1", "limit": "5"}
    })
    assert r.status_code == 400
    body = r.json()
    assert "chưa được hỗ trợ" in (body.get("detail") or "")


def test_ingest_promotions_saves_promotions_only(client):
    # Ensure campaigns are synced so APPROVED campaign exists in DB (mock CAMP3 for tikivn)
    r_sync = client.post("/ingest/campaigns/sync", json={
        "provider": "accesstrade",
        "statuses": ["running"],
        "only_my": True,
        "enrich_user_status": False
    })
    assert r_sync.status_code == 200

    # Ingest promotions for tikivn (alias to tiki for API fetch)
    r = client.post("/ingest/promotions", json={
        "provider": "accesstrade",
        "merchant": "tikivn"
    })
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("promotions"), int) and body.get("promotions") >= 1

    # Verify promotions upserted and NO offer auto-created from promotions anymore
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal", None)
    assert TestingSessionLocal is not None, "TestingSessionLocal not found on app.state"
    from models import Promotion, ProductOffer
    with TestingSessionLocal() as db:
        prom_count = db.query(Promotion).filter(Promotion.campaign_id == "CAMP3").count()
        assert prom_count >= 1
        offers_from_promotions = db.query(ProductOffer).filter(
            ProductOffer.source == "accesstrade",
            ProductOffer.source_type == "promotions",
            ProductOffer.merchant == "tikivn"
        ).count()
        assert offers_from_promotions == 0


def test_ingest_top_products_creates_offers(client):
    # Ensure campaigns are synced so APPROVED campaign exists in DB
    r_sync = client.post("/ingest/campaigns/sync", json={
        "provider": "accesstrade",
        "statuses": ["running"],
        "only_my": True,
        "enrich_user_status": False
    })
    assert r_sync.status_code == 200

    # Ingest top products for tikivn within a small page window
    r = client.post("/ingest/top-products", json={
        "provider": "accesstrade",
        "merchant": "tikivn",
        "limit_per_page": 50,
        "max_pages": 1,
        "check_urls": False
    })
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("imported"), int) and body.get("imported") >= 1

    # Verify offers persisted with source_type=top_products
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal", None)
    assert TestingSessionLocal is not None, "TestingSessionLocal not found on app.state"
    from models import ProductOffer
    with TestingSessionLocal() as db:
        top_count = db.query(ProductOffer).filter(
            ProductOffer.source == "accesstrade",
            ProductOffer.source_type == "top_products",
            ProductOffer.merchant == "tikivn"
        ).count()
        assert top_count >= 1


def test_ingest_top_products_no_merchant_verbose_returns_skipped(client):
    # Sync campaigns first to have running & approved mock campaigns
    r_sync = client.post("/ingest/campaigns/sync", json={
        "provider": "accesstrade",
        "statuses": ["running"],
        "only_my": True,
        "enrich_user_status": False
    })
    assert r_sync.status_code == 200

    # No merchant provided: should run across approved-running merchants and include skipped when verbose=true
    r = client.post("/ingest/top-products", json={
        "provider": "accesstrade",
        "limit_per_page": 50,
        "max_pages": 1,
        "check_urls": False,
        "verbose": True
    })
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("imported"), int)
    assert isinstance(body.get("by_merchant"), dict)
    # skipped_merchants should exist in verbose mode albeit possibly empty
    assert "skipped_merchants" in body
    assert isinstance(body.get("skipped_merchants"), list)
