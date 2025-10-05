import os
import sys
import io
import pytest

fastapi = pytest.importorskip(
    "fastapi", reason="FastAPI not installed in this test environment"
)
from fastapi.testclient import TestClient

# Force SQLite DB before importing app/main
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from main import app, get_db
import crud, schemas, models
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from database import Base


@pytest.fixture(scope="module")
def client():
    # Use in-memory SQLite and override FastAPI dependency
    os.environ["AT_MOCK"] = "1"

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

    # Seed mock API config so Accesstrade helper passes when needed
    with TestingSessionLocal() as db:
        crud.upsert_api_config_by_name(
            db,
            schemas.APIConfigCreate(
                name="accesstrade",
                base_url="mock://accesstrade",
                api_key="dummy",
                model="-",
            ),
        )

    return c


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_links_crud(client):
    # Create
    payload = {
        "name": "Link Shopee",
        "url": "https://shopee.vn/product/1",
        "affiliate_url": "https://go.example/?url=https%3A%2F%2Fshopee.vn%2Fproduct%2F1",
    }
    r_create = client.post("/links", json=payload)
    assert r_create.status_code == 200
    link_id = r_create.json()["id"]

    # List
    r_list = client.get("/links")
    assert r_list.status_code == 200 and isinstance(r_list.json(), list)

    # Detail
    r_get = client.get(f"/links/{link_id}")
    assert r_get.status_code == 200
    assert r_get.json()["name"] == payload["name"]

    # Update
    upd = dict(payload)
    upd["name"] = "Link Shopee A"
    r_upd = client.put(f"/links/{link_id}", json=upd)
    assert r_upd.status_code == 200
    assert r_upd.json()["name"] == "Link Shopee A"

    # Delete
    r_del = client.delete(f"/links/{link_id}")
    assert r_del.status_code == 200
    r_get2 = client.get(f"/links/{link_id}")
    assert r_get2.status_code == 404


def test_api_configs_crud(client):
    # Upsert
    r_upsert = client.post(
        "/api-configs/upsert",
        json={
            "name": "testprov",
            "base_url": "https://api.example.com",
            "api_key": "KEY",
            "model": "m1",
        },
    )
    assert r_upsert.status_code == 200
    cfg = r_upsert.json()
    cfg_id = cfg["id"]

    # List
    r_list = client.get("/api-configs")
    assert r_list.status_code == 200 and any(
        c["name"] == "testprov" for c in r_list.json()
    )

    # Update by id
    r_put = client.put(
        f"/api-configs/{cfg_id}",
        json={
            "name": "testprov",
            "base_url": "https://api2.example.com",
            "api_key": "NEW",
            "model": "m2",
        },
    )
    assert r_put.status_code == 200
    assert r_put.json()["base_url"].startswith("https://api2")

    # Delete
    r_del = client.delete(f"/api-configs/{cfg_id}")
    assert r_del.status_code == 200 and r_del.json().get("ok") is True


def test_affiliate_templates_and_convert_redirect(client):
    # Upsert a template for shopee
    r_tpl = client.post(
        "/aff/templates/upsert",
        json={
            "platform": "shopee",
            "network": "accesstrade",
            "template": "https://go.aff/?url={target}&sub1={sub1}",
            "default_params": {"sub1": "abc"},
        },
    )
    assert r_tpl.status_code == 200

    # Convert a valid shopee url
    r_conv = client.post(
        "/aff/convert",
        json={
            "platform": "shopee",
            "url": "https://shopee.vn/product/123",
            "params": {"sub1": "xyz"},
        },
    )
    assert r_conv.status_code == 200
    data = r_conv.json()
    assert data["affiliate_url"].startswith("https://go.aff/?url=")
    assert data["short_url"].startswith("/r/")

    # Redirect should 302 to affiliate_url
    short = data["short_url"]
    r_redir = client.get(short, follow_redirects=False)
    assert r_redir.status_code in (302, 307)
    assert r_redir.headers.get("location") == data["affiliate_url"]

    # Invalid domain (not whitelisted)
    r_bad = client.post(
        "/aff/convert", json={"platform": "shopee", "url": "https://evil.com/haha"}
    )
    assert r_bad.status_code == 400


def test_campaigns_summary_and_list_and_approved_merchants(client):
    # Sync campaigns to seed DB
    r_sync = client.post(
        "/ingest/campaigns/sync",
        json={
            "provider": "accesstrade",
            "statuses": ["running"],
            "only_my": True,
            "enrich_user_status": False,
        },
    )
    assert r_sync.status_code == 200

    r_sum = client.get("/campaigns/summary")
    assert r_sum.status_code == 200
    body = r_sum.json()
    assert set(["total", "by_status", "by_user_status"]).issubset(body.keys())

    r_list = client.get("/campaigns", params={"user_status": "APPROVED"})
    assert r_list.status_code == 200
    assert isinstance(r_list.json(), list)

    r_mer = client.get("/campaigns/approved-merchants")
    assert r_mer.status_code == 200 and isinstance(r_mer.json(), list)


def test_ingest_policy_and_settings_and_rotate(client):
    # Policy toggles
    r_pol = client.post("/ingest/policy", params={"only_with_commission": True})
    assert r_pol.status_code == 200 and r_pol.json().get("ok") is True

    r_chk = client.post("/ingest/policy/check-urls", params={"enable": True})
    assert r_chk.status_code == 200 and r_chk.json().get("ok") is True

    # Linkcheck config
    r_cfg = client.post(
        "/settings/linkcheck/config", json={"linkcheck_mod": 2, "linkcheck_limit": 5}
    )
    assert r_cfg.status_code == 200 and r_cfg.json().get("ok") is True

    # Rotate run (no data is fine)
    r_rot = client.post("/scheduler/linkcheck/rotate")
    assert r_rot.status_code == 200
    out = r_rot.json()
    assert set(["cursor_used", "next_cursor", "mod", "scanned"]).issubset(out.keys())


def test_ai_endpoints_with_and_without_products(client):
    # ai/test should return suggestion even when no products
    r_test = client.post("/ai/test")
    assert r_test.status_code == 200
    assert isinstance(r_test.json().get("suggestion"), str)

    # ai/suggest should 404 when no products
    r_sug = client.post("/ai/suggest", params={"query": "giới thiệu"})
    assert r_sug.status_code == 404

    # Seed one product so ai/suggest works and returns 'chưa cấu hình' message
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        crud.upsert_offer_by_source(
            db,
            schemas.ProductOfferCreate(
                source="manual",
                source_id="seed-ai",
                merchant="tiki",
                title="SP AI",
                url="https://tiki.vn/a",
                affiliate_url=None,
                image_url=None,
                price=100000,
                currency="VND",
                campaign_id=None,
                source_type="manual",
                extra=None,
            ),
        )

    r_sug2 = client.post(
        "/ai/suggest", params={"query": "giới thiệu", "provider": "groq"}
    )
    assert r_sug2.status_code == 200
    assert "Chưa cấu hình API" in r_sug2.json().get("suggestion", "")


def test_export_template_and_campaign_description(client):
    r_tpl = client.get("/offers/export-template")
    assert r_tpl.status_code == 200
    assert r_tpl.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Description page (no logs -> fallback HTML)
    r_desc = client.get("/campaigns/CAMP3/description")
    assert r_desc.status_code == 200
    assert "<!doctype html>" in r_desc.text.lower()


def test_ingest_commissions_unified(client):
    # Ensure we have synced campaigns
    client.post(
        "/ingest/campaigns/sync",
        json={
            "provider": "accesstrade",
            "statuses": ["running"],
            "only_my": True,
            "enrich_user_status": False,
        },
    )
    r = client.post(
        "/ingest/commissions", json={"provider": "accesstrade", "merchant": "tikivn"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("policies_imported"), int)


def test_delete_all_offers_endpoint(client):
    # Seed various offers
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        crud.upsert_offer_by_source(
            db,
            schemas.ProductOfferCreate(
                source="accesstrade",
                source_id="d1",
                merchant="tikivn",
                title="DF 1",
                url="https://tiki.vn/1",
                affiliate_url=None,
                image_url=None,
                price=1,
                currency="VND",
                campaign_id="CID",
                source_type="datafeeds",
                extra=None,
            ),
        )
        crud.upsert_offer_by_source(
            db,
            schemas.ProductOfferCreate(
                source="accesstrade",
                source_id="tp1",
                merchant="tikivn",
                title="TP 1",
                url="https://tiki.vn/2",
                affiliate_url=None,
                image_url=None,
                price=2,
                currency="VND",
                campaign_id="CID",
                source_type="top_products",
                extra=None,
            ),
        )
        crud.upsert_offer_by_source(
            db,
            schemas.ProductOfferCreate(
                source="manual",
                source_id="m1",
                merchant="tikivn",
                title="Manual 1",
                url="https://tiki.vn/3",
                affiliate_url=None,
                image_url=None,
                price=3,
                currency="VND",
                campaign_id="CID",
                source_type="manual",
                extra=None,
            ),
        )

    # Delete all in offers category (should keep top_products)
    r_del = client.delete("/offers", params={"category": "offers"})
    assert r_del.status_code == 200
    assert r_del.json().get("ok") is True
