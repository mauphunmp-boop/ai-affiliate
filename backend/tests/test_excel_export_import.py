import io
import os
import sys
import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed in this test environment")
from fastapi.testclient import TestClient

# Force SQLite and AT mock
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from main import app, get_db
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from database import Base
import crud, schemas, models
import pandas as pd


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
    return TestClient(app)


def _seed_minimal_data(db):
    # Seed campaign APPROVED
    crud.upsert_campaign(db, schemas.CampaignCreate(
        campaign_id="CAMP_OK",
        merchant="tikivn",
        name="Tiki",
        status="running",
        user_registration_status="APPROVED",
    ))
    # Seed promotions offer and manual offer
    crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(
        source="accesstrade", source_id="p1", merchant="tikivn", title="SP DF",
        url="https://tiki.vn/1", affiliate_url=None, image_url=None, price=100000, currency="VND",
        campaign_id="CAMP_OK", source_type="datafeeds", extra=None
    ))
    crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(
        source="accesstrade", source_id="p2", merchant="tikivn", title="SP TOP",
        url="https://tiki.vn/2", affiliate_url=None, image_url=None, price=200000, currency="VND",
        campaign_id="CAMP_OK", source_type="top_products", extra=None
    ))
    crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(
        source="accesstrade", source_id="p3", merchant="tikivn", title="SP PROMO",
        url="https://tiki.vn/3", affiliate_url=None, image_url=None, price=300000, currency="VND",
        campaign_id="CAMP_OK", source_type="promotions", extra=None
    ))
    crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(
        source="excel", source_id="p4", merchant="tikivn", title="SP EXCEL",
        url="https://tiki.vn/4", affiliate_url=None, image_url=None, price=400000, currency="VND",
        campaign_id="CAMP_OK", source_type="excel", extra=None
    ))
    crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(
        source="manual", source_id="p5", merchant="tikivn", title="SP MANUAL",
        url="https://tiki.vn/5", affiliate_url=None, image_url=None, price=500000, currency="VND",
        campaign_id="CAMP_OK", source_type="manual", extra=None
    ))
    # Seed commission & promotion rows
    crud.upsert_commission_policy(db, schemas.CommissionPolicyCreate(
        campaign_id="CAMP_OK", reward_type="CPS", sales_ratio=10.0, sales_price=None, target_month="2025-09"
    ))
    crud.upsert_promotion(db, schemas.PromotionCreate(
        campaign_id="CAMP_OK", name="Promo 10%", content="Giảm 10%", start_time="2025-09-01",
        end_time="2025-10-01", coupon="SALE10", link="https://tiki.vn/promo"
    ))


def test_export_excel_structure_and_sources(client):
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        _seed_minimal_data(db)

    r = client.get("/offers/export-excel")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Load workbook into pandas
    buf = io.BytesIO(r.content)
    xls = pd.ExcelFile(buf)
    sheets = set(xls.sheet_names)
    assert {"Products", "Campaigns", "Commissions", "Promotions"}.issubset(sheets)

    df_products = xls.parse("Products")
    # First row is header (Vietnamese), real data starts from row 2
    cols = list(df_products.columns)
    # Must contain source_type and not contain extra_raw
    assert "source_type" in cols
    assert "extra_raw" not in cols

    # Ensure products include extended sources
    # Skip the Vietnamese header row (row index 1 in Excel, zero-based in pandas skiprows)
    dfp = xls.parse("Products", skiprows=[1])
    assert (dfp["source_type"].isin(["datafeeds", "top_products", "promotions", "manual", "excel"]).any())

    # Enforce exact column order based on trans_products keys in backend
    expected_products_cols = [
        "id","source","source_id","source_type","merchant","title","url","affiliate_url","image_url",
        "price","currency","campaign_id","product_id","affiliate_link_available","domain","sku","discount",
        "discount_amount","discount_rate","status_discount","updated_at","desc","cate","shop_name","update_time_raw"
    ]
    assert list(dfp.columns) == expected_products_cols

    # Other sheets
    dfc = xls.parse("Campaigns", skiprows=[1])
    expected_campaigns_cols = [
        "campaign_id","merchant","campaign_name","approval_type","user_status","status","start_time","end_time",
        "category","conversion_policy","cookie_duration","cookie_policy","description_url","scope","sub_category","type","campaign_url"
    ]
    assert list(dfc.columns) == expected_campaigns_cols

    dfcm = xls.parse("Commissions", skiprows=[1])
    expected_comm_cols = ["campaign_id","reward_type","sales_ratio","sales_price","target_month"]
    assert list(dfcm.columns) == expected_comm_cols

    dfpr = xls.parse("Promotions", skiprows=[1])
    expected_prom_cols = ["campaign_id","merchant","name","content","start_time","end_time","coupon","link"]
    assert list(dfpr.columns) == expected_prom_cols


def test_import_excel_required_and_success(client, tmp_path):
    # Build a minimal valid Products sheet with required fields
    trans = {
        "id": "Mã ID", "source": "Nguồn", "source_id": "Mã nguồn (*)", "source_type": "Loại nguồn",
        "merchant": "Nhà bán (*)", "title": "Tên sản phẩm (*)", "url": "Link gốc", "affiliate_url": "Link tiếp thị",
        "image_url": "Ảnh sản phẩm", "price": "Giá", "currency": "Tiền tệ",
        "campaign_id": "Chiến dịch", "product_id": "Mã sản phẩm nguồn", "affiliate_link_available": "Có affiliate?",
        "domain": "Tên miền", "sku": "SKU", "discount": "Giá KM", "discount_amount": "Mức giảm",
        "discount_rate": "Tỷ lệ giảm (%)", "status_discount": "Có khuyến mãi?",
        "updated_at": "Ngày cập nhật", "desc": "Mô tả chi tiết",
        "cate": "Danh mục", "shop_name": "Tên cửa hàng", "update_time_raw": "Thời gian cập nhật từ nguồn",
    }

    cols = list(trans.keys())
    header_vi = [trans[c] for c in cols]

    # Case 1: Missing required (no merchant)
    df = pd.DataFrame(columns=cols)
    df.loc[0, cols] = header_vi
    df.loc[1, "source"] = "excel"
    df.loc[1, "source_type"] = "excel"
    # merchant intentionally missing
    df.loc[1, "title"] = "Sản phẩm A"
    df.loc[1, "url"] = "https://tiki.vn/a"

    p1 = tmp_path / "case1.xlsx"
    with pd.ExcelWriter(p1, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Products", index=False)

    with open(p1, "rb") as f:
        r = client.post("/offers/import-excel", files={"file": ("case1.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200
    body = r.json()
    assert body.get("skipped_required", 0) >= 1

    # Case 2: Valid row (no source_id, should be auto-generated)
    df2 = pd.DataFrame(columns=cols)
    df2.loc[0, cols] = header_vi
    df2.loc[1, "source"] = "excel"
    df2.loc[1, "source_type"] = "excel"
    df2.loc[1, "merchant"] = "tikivn"
    df2.loc[1, "title"] = "Sản phẩm B"
    df2.loc[1, "url"] = "https://tiki.vn/b"
    df2.loc[1, "currency"] = "VND"
    df2.loc[1, "price"] = 123000

    p2 = tmp_path / "case2.xlsx"
    with pd.ExcelWriter(p2, engine="xlsxwriter") as writer:
        df2.to_excel(writer, sheet_name="Products", index=False)

    with open(p2, "rb") as f:
        r2 = client.post("/offers/import-excel", files={"file": ("case2.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get("imported", 0) >= 1


def test_import_auto_convert_affiliate_url(client, tmp_path):
    # Seed a deeplink template for tikivn
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        crud.upsert_affiliate_template(db, schemas.AffiliateTemplateCreate(
            merchant="tikivn", network="accesstrade", template="https://aff.example.com?url={target}", default_params=None, enabled=True
        ))

    trans = {
        "id": "Mã ID", "source": "Nguồn", "source_id": "Mã nguồn", "source_type": "Loại nguồn",
        "merchant": "Nhà bán (*)", "title": "Tên sản phẩm (*)", "url": "Link gốc", "affiliate_url": "Link tiếp thị",
        "image_url": "Ảnh sản phẩm", "price": "Giá (*)", "currency": "Tiền tệ",
        "campaign_id": "Chiến dịch", "product_id": "Mã sản phẩm nguồn", "affiliate_link_available": "Có affiliate?",
        "domain": "Tên miền", "sku": "SKU", "discount": "Giá KM", "discount_amount": "Mức giảm",
        "discount_rate": "Tỷ lệ giảm (%)", "status_discount": "Có khuyến mãi?",
        "updated_at": "Ngày cập nhật", "desc": "Mô tả chi tiết",
        "cate": "Danh mục", "shop_name": "Tên cửa hàng", "update_time_raw": "Thời gian cập nhật từ nguồn",
    }
    cols = list(trans.keys())
    header_vi = [trans[c] for c in cols]

    df = pd.DataFrame(columns=cols)
    df.loc[0, cols] = header_vi
    df.loc[1, "source"] = "excel"
    df.loc[1, "source_type"] = "excel"
    df.loc[1, "merchant"] = "tikivn"
    df.loc[1, "title"] = "Sản phẩm C"
    df.loc[1, "url"] = "https://tiki.vn/c"
    df.loc[1, "price"] = 456000
    # intentionally leave affiliate_url empty so it should be auto-converted

    p = tmp_path / "auto_aff.xlsx"
    with pd.ExcelWriter(p, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Products", index=False)

    with open(p, "rb") as f:
        r = client.post("/offers/import-excel", files={"file": ("auto_aff.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200

    # verify inserted record has affiliate_url and affiliate_link_available=True
    resp = client.get("/offers")
    assert resp.status_code == 200
    items = resp.json()
    assert any(it.get("merchant") == "tikivn" and it.get("title") == "Sản phẩm C" and it.get("affiliate_url") for it in items)
    assert any(it.get("merchant") == "tikivn" and it.get("title") == "Sản phẩm C" and it.get("affiliate_link_available") is True for it in items)


def test_export_campaigns_includes_case_variants_and_is_stable(client):
    # Seed variants of user_registration_status with different case/whitespace
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        crud.upsert_campaign(db, schemas.CampaignCreate(
            campaign_id="CAMP_A",
            merchant="shopa",
            name="Shop A",
            status="running",
            user_registration_status="approved"  # lower-case
        ))
        crud.upsert_campaign(db, schemas.CampaignCreate(
            campaign_id="CAMP_B",
            merchant="shopb",
            name="Shop B",
            status="running",
            user_registration_status="  APPROVED  "  # padded whitespace
        ))
        crud.upsert_campaign(db, schemas.CampaignCreate(
            campaign_id="CAMP_C",
            merchant="shopc",
            name="Shop C",
            status="paused",
            user_registration_status="SUCCESSFUL"  # treated as APPROVED
        ))

    # Run export twice and ensure Campaigns sheet consistently includes all 3
    def _get_campaign_ids_from_export():
        r = client.get("/offers/export-excel")
        assert r.status_code == 200
        import io, pandas as pd
        xls = pd.ExcelFile(io.BytesIO(r.content))
        dfc = xls.parse("Campaigns", skiprows=[1])
        return sorted(list(dfc["campaign_id"].astype(str)))

    ids1 = _get_campaign_ids_from_export()
    ids2 = _get_campaign_ids_from_export()
    # Should contain the seeded campaign IDs
    assert set(["CAMP_A", "CAMP_B", "CAMP_C"]).issubset(set(ids1))
    # Deterministic across runs
    assert ids1 == ids2


def test_import_multiple_sheets_and_autogen_ids(client, tmp_path):
    # Chuẩn bị header 2 hàng cho từng sheet theo mapping trong backend
    # Products
    trans_products = {
        "id": "Mã ID", "source": "Nguồn", "source_id": "Mã nguồn (*)", "source_type": "Loại nguồn",
        "merchant": "Nhà bán (*)",
        "title": "Tên sản phẩm (*)", "url": "Link gốc", "affiliate_url": "Link tiếp thị",
        "image_url": "Ảnh sản phẩm", "price": "Giá", "currency": "Tiền tệ",
        "campaign_id": "Chiến dịch", "product_id": "Mã sản phẩm nguồn", "affiliate_link_available": "Có affiliate?",
        "domain": "Tên miền", "sku": "SKU", "discount": "Giá KM", "discount_amount": "Mức giảm",
        "discount_rate": "Tỷ lệ giảm (%)", "status_discount": "Có khuyến mãi?",
        "updated_at": "Ngày cập nhật", "desc": "Mô tả chi tiết",
        "cate": "Danh mục", "shop_name": "Tên cửa hàng", "update_time_raw": "Thời gian cập nhật từ nguồn",
    }
    p_cols = list(trans_products.keys())
    p_head = [trans_products[c] for c in p_cols]
    df_p = pd.DataFrame(columns=p_cols)
    df_p.loc[0, p_cols] = p_head
    df_p.loc[1, "source"] = "excel"
    df_p.loc[1, "source_type"] = "excel"
    df_p.loc[1, "merchant"] = "tikivn"
    df_p.loc[1, "title"] = "Product Z excel"
    df_p.loc[1, "url"] = "https://tiki.vn/z"
    df_p.loc[1, "price"] = 99000
    # Không cung cấp source_id -> phải auto-gen 'exp' + 11 số = 14 ký tự

    # Campaigns
    trans_campaigns = {
        "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "campaign_name": "Tên chiến dịch",
        "approval_type": "Approval", "user_status": "Trạng thái của tôi", "status": "Tình trạng",
        "start_time": "Bắt đầu", "end_time": "Kết thúc",
        "category": "Danh mục chính", "conversion_policy": "Chính sách chuyển đổi",
        "cookie_duration": "Hiệu lực cookie (giây)", "cookie_policy": "Chính sách cookie",
        "description_url": "Mô tả (Web)", "scope": "Phạm vi", "sub_category": "Danh mục phụ",
        "type": "Loại", "campaign_url": "URL chiến dịch",
    }
    c_cols = list(trans_campaigns.keys())
    c_head = [trans_campaigns[c] for c in c_cols]
    df_c = pd.DataFrame(columns=c_cols)
    df_c.loc[0, c_cols] = c_head
    df_c.loc[1, "campaign_id"] = "CAMP_XL"
    df_c.loc[1, "merchant"] = "tikivn"
    df_c.loc[1, "campaign_name"] = "Tiki XL"
    df_c.loc[1, "user_status"] = "APPROVED"
    df_c.loc[1, "status"] = "running"

    # Commissions
    trans_comm = {
        "campaign_id": "Mã chiến dịch", "reward_type": "Kiểu thưởng", "sales_ratio": "Tỷ lệ (%)",
        "sales_price": "Hoa hồng cố định", "target_month": "Tháng áp dụng",
    }
    m_cols = list(trans_comm.keys())
    m_head = [trans_comm[c] for c in m_cols]
    df_m = pd.DataFrame(columns=m_cols)
    df_m.loc[0, m_cols] = m_head
    df_m.loc[1, "campaign_id"] = "CAMP_CMC"
    df_m.loc[1, "reward_type"] = "CPS"
    df_m.loc[1, "sales_ratio"] = 12.5
    df_m.loc[1, "target_month"] = "2025-09"

    # Promotions
    trans_prom = {
        "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "name": "Tên khuyến mãi", "content": "Nội dung",
        "start_time": "Bắt đầu KM", "end_time": "Kết thúc KM", "coupon": "Mã giảm", "link": "Link khuyến mãi",
    }
    pr_cols = list(trans_prom.keys())
    pr_head = [trans_prom[c] for c in pr_cols]
    df_pr = pd.DataFrame(columns=pr_cols)
    df_pr.loc[0, pr_cols] = pr_head
    df_pr.loc[1, "campaign_id"] = "CAMP_PRM"
    df_pr.loc[1, "merchant"] = "tikivn"
    df_pr.loc[1, "name"] = "Back to school"
    df_pr.loc[1, "content"] = "Giảm 15% đồ học tập"
    df_pr.loc[1, "start_time"] = "2025-09-01T00:00:00"
    df_pr.loc[1, "end_time"] = "2025-10-01T00:00:00"
    df_pr.loc[1, "coupon"] = "BTS15"
    df_pr.loc[1, "link"] = "https://tiki.vn/promo-bts"

    p = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(p, engine="xlsxwriter") as writer:
        df_p.to_excel(writer, sheet_name="Products", index=False)
        df_c.to_excel(writer, sheet_name="Campaigns", index=False)
        df_m.to_excel(writer, sheet_name="Commissions", index=False)
        df_pr.to_excel(writer, sheet_name="Promotions", index=False)

    with open(p, "rb") as f:
        r = client.post("/offers/import-excel", files={"file": ("multi.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200
    body = r.json()
    assert body.get("imported", 0) >= 1
    assert body.get("campaigns", 0) >= 1
    assert body.get("commissions", 0) >= 1
    assert body.get("promotions", 0) >= 1

    # Kiểm tra dữ liệu đã vào DB
    TestingSessionLocal = getattr(app.state, "TestingSessionLocal")
    with TestingSessionLocal() as db:
        # Products: có sản phẩm excel với title "Product Z excel" và source_id 14 ký tự bắt đầu bằng 'exp'
        items = db.query(models.ProductOffer).filter(models.ProductOffer.source == "excel", models.ProductOffer.title == "Product Z excel").all()
        assert items, "Không thấy product vừa import"
        sid = items[0].source_id
        assert isinstance(sid, str) and len(sid) == 14 and sid.startswith("exp")

        # Campaigns
        camp = crud.get_campaign_by_cid(db, "CAMP_XL")
        assert camp is not None and (camp.user_registration_status or "").upper() in ("APPROVED", "SUCCESSFUL")

        # Commissions
        cm = db.query(models.CommissionPolicy).filter(
            models.CommissionPolicy.campaign_id == "CAMP_CMC",
            models.CommissionPolicy.reward_type == "CPS",
            models.CommissionPolicy.target_month == "2025-09",
        ).first()
        assert cm is not None

        # Promotions
        pr = db.query(models.Promotion).filter(
            models.Promotion.campaign_id == "CAMP_PRM",
            models.Promotion.name == "Back to school",
        ).first()
        assert pr is not None
