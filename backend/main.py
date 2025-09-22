# backend/main.py
import logging
import traceback
import os, hmac, hashlib, base64, json, time, asyncio
from urllib.parse import urlparse, quote_plus
from typing import Optional, Dict, List, Any

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from providers import ProviderRegistry, ProviderOps
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
import io
from fastapi.exceptions import RequestValidationError

from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_

from ai_service import suggest_products_with_config
import models, schemas, crud
from database import Base, engine, SessionLocal
from pydantic import BaseModel, HttpUrl
from accesstrade_service import (
    fetch_products, map_at_product_to_offer, _check_url_alive, fetch_promotions,
    fetch_campaign_detail, fetch_commission_policies  # NEW
)

# FastAPI application instance
app = FastAPI()

# CORS (open by default; tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logger
logger = logging.getLogger("affiliate_api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# --- DB init: create tables on import (no Alembic here) ---
Base.metadata.create_all(bind=engine)

# DB session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Error handlers ----------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "Validation error on %s %s: %s | body=%s",
        request.method, request.url.path, exc, getattr(exc, "body", None)
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": getattr(exc, "body", None)}
    )

@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    return JSONResponse(status_code=500, content={"error": str(exc), "traceback": tb})

# ---------------- System ----------------
## NOTE: (removed) stray decorator left behind during refactor
@app.get(
    "/health",
    tags=["System 🛠️"],
    summary="Kiểm tra sức khỏe hệ thống",
    description="Thực hiện truy vấn SQL đơn giản để kiểm tra kết nối DB và tình trạng dịch vụ."
)
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        logger.exception("Health check failed")
        return {"ok": False, "error": str(e)}

# =====================================================================
#                       AFFILIATE — SAFE SHORTLINK
# =====================================================================

# Secret ký HMAC cho shortlink /r/{token}
AFF_SECRET = os.getenv("AFF_SECRET", "change-me")  # nhớ đặt trong docker-compose/.env khi chạy thật

# Whitelist domain theo merchant để chống open-redirect
ALLOWED_DOMAINS = {
    "shopee": ["shopee.vn", "shopee.sg", "shopee.co.id", "shopee.co.th", "shopee.com.my", "shopee.ph"],
    "lazada": ["lazada.vn", "lazada.co.id", "lazada.co.th", "lazada.com.my", "lazada.sg", "lazada.com.ph"],
    "tiki":   ["tiki.vn"],
}

def _is_allowed_domain(merchant: str, url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
        return any(netloc.endswith(dom) for dom in ALLOWED_DOMAINS.get(merchant, []))
    except Exception:
        return False

def _apply_template(template: str, target_url: str, params: Optional[Dict[str, str]]) -> str:
    # Encode link gốc vào placeholder {target}; các {param} khác thay trực tiếp
    aff = template.replace("{target}", quote_plus(target_url))
    if params:
        for k, v in params.items():
            aff = aff.replace("{" + k + "}", str(v))
    return aff

def _make_token(affiliate_url: str, ts: Optional[int] = None) -> str:
    payload = {"u": affiliate_url, "ts": ts or int(time.time())}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(AFF_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"

def _parse_token(token: str) -> str:
    try:
        b64, sig = token.split(".", 1)
        expect = hmac.new(AFF_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            raise ValueError("invalid signature")
        pad = "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(b64 + pad).decode())
        return payload["u"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid token: {e}")

# ---------------- CRUD: Links ----------------
@app.get(
    "/links",
    tags=["Links 🔗"],
    summary="Danh sách link",
    description="Lấy danh sách link tiếp thị từ DB. Hỗ trợ phân trang qua `skip`, `limit`.",
    response_model=list[schemas.AffiliateLinkOut]
)
def read_links(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_links(db, skip=skip, limit=limit)

@app.get(
    "/links/{link_id}",
    tags=["Links 🔗"],
    summary="Chi tiết link",
    description="Lấy chi tiết một link tiếp thị theo **ID**.",
    response_model=schemas.AffiliateLinkOut
)
def read_link(link_id: int, db: Session = Depends(get_db)):
    db_link = crud.get_link(db, link_id)
    if db_link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return db_link

@app.post(
    "/links",
    tags=["Links 🔗"],
    summary="Thêm link mới",
    description="Tạo mới một link tiếp thị và lưu vào DB.",
    response_model=schemas.AffiliateLinkOut
)
def create_link(link: schemas.AffiliateLinkCreate, db: Session = Depends(get_db)):
    logger.debug("Create link payload: %s", link.model_dump() if hasattr(link, "model_dump") else link.dict())
    return crud.create_link(db, link)

@app.put(
    "/links/{link_id}",
    tags=["Links 🔗"],
    summary="Cập nhật link",
    description="Cập nhật thông tin một link tiếp thị theo **ID**.",
    response_model=schemas.AffiliateLinkOut
)
def update_link(link_id: int, link: schemas.AffiliateLinkUpdate, db: Session = Depends(get_db)):
    db_link = crud.update_link(db, link_id, link)
    if db_link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return db_link

@app.delete(
    "/links/{link_id}",
    tags=["Links 🔗"],
    summary="Xoá link",
    description="Xoá link tiếp thị theo **ID**."
)
def delete_link(link_id: int, db: Session = Depends(get_db)):
    db_link = crud.delete_link(db, link_id)
    if db_link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True, "message": "Link deleted"}

# ---------------- CRUD: API Configs ----------------

@app.get(
    "/api-configs",
    tags=["API Configs ⚙️"],
    summary="Danh sách cấu hình API",
    description="Liệt kê toàn bộ cấu hình nhà cung cấp AI/API.",
    response_model=list[schemas.APIConfigOut]
)
def read_api_configs(db: Session = Depends(get_db)):
    return crud.list_api_configs(db)

@app.post(
    "/api-configs/upsert",
    tags=["API Configs ⚙️"],
    summary="Upsert cấu hình API",
    description="**Tạo mới hoặc cập nhật** cấu hình dựa trên `name`. Thuận tiện để cập nhật nhanh.",
    response_model=schemas.APIConfigOut
)
def upsert_api_config(config: schemas.APIConfigCreate, db: Session = Depends(get_db)):
    """Tạo mới hoặc cập nhật API config theo name."""
    return crud.upsert_api_config_by_name(db, config)

@app.put(
    "/api-configs/{config_id}",
    tags=["API Configs ⚙️"],
    summary="Cập nhật cấu hình API",
    description="Cập nhật thông tin cấu hình theo **ID**.",
    response_model=schemas.APIConfigOut
)
def update_api_config(config_id: int, config: schemas.APIConfigCreate, db: Session = Depends(get_db)):
    db_config = db.query(models.APIConfig).filter(models.APIConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="API config not found")
    db_config.name = config.name
    db_config.base_url = config.base_url
    db_config.api_key = config.api_key
    db_config.model = config.model
    db.commit()
    db.refresh(db_config)
    return db_config

@app.delete(
    "/api-configs/{config_id}",
    tags=["API Configs ⚙️"],
    summary="Xoá cấu hình API",
    description="Xoá cấu hình nhà cung cấp theo **ID**."
)
def delete_api_config_route(config_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_api_config(db, config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API config not found")
    return {"ok": True, "deleted_id": config_id, "name": deleted.name}

# ---------------- AI: Suggest/Test ----------------
@app.post(
    "/ai/suggest",
    tags=["AI 🤖"],
    summary="AI gợi ý theo sản phẩm trong DB",
    description="Trả lời/gợi ý bằng AI dựa trên danh sách sản phẩm đã ingest."
)
async def ai_suggest(
    query: str,
    provider: str = "groq",
    db: Session = Depends(get_db)
):
    # Giữ nguyên logic gốc
    products = []
    for o in crud.list_offers(db, limit=50):
        desc = None
        if o.extra:
            try:
                desc = json.loads(o.extra).get("desc")
            except:
                pass
        products.append({
            "name": o.title,
            "url": o.url,
            "affiliate_url": o.affiliate_url or o.url,
            "desc": desc
        })
    if not products:
        raise HTTPException(status_code=404, detail="Chưa có sản phẩm nào trong DB")
    response = await suggest_products_with_config(query, products, db, provider)
    return {"suggestion": response}

@app.post(
    "/ai/test",
    tags=["AI 🤖"],
    summary="Test AI nhanh",
    description="Gọi AI với câu hỏi mẫu & 10 sản phẩm gần nhất trong DB để kiểm tra nhanh chất lượng trả lời."
)
async def ai_test(
    query: str = "Giới thiệu sản phẩm tốt nhất trên Shopee",
    provider: str = "groq",
    db: Session = Depends(get_db)
):
    # Giữ nguyên logic gốc
    products = []
    for o in crud.list_offers(db, limit=50):
        desc = None
        if o.extra:
            try:
                desc = json.loads(o.extra).get("desc")
            except:
                pass
        products.append({
            "name": o.title,
            "url": o.url,
            "affiliate_url": o.affiliate_url or o.url,
            "desc": desc
        })
    if not products:
        return {"suggestion": "⚠️ Chưa có sản phẩm nào trong DB để gợi ý."}
    response = await suggest_products_with_config(query, products, db, provider)
    return {"suggestion": response}

# =====================================================================
#                  NEW: Templates + Convert + Redirect
# =====================================================================

# Upsert template deeplink (mỗi merchant/network một mẫu)

@app.get(
    "/aff/templates",
    tags=["Affiliate 🎯"],
    summary="Danh sách mẫu deeplink",
    description="Hiển thị đầy đủ các mẫu deeplink hiện có trong DB.",
    response_model=list[schemas.AffiliateTemplateOut]
)
def list_templates(db: Session = Depends(get_db)):
    return crud.list_affiliate_templates(db)

@app.post(
    "/aff/templates/upsert",
    tags=["Affiliate 🎯"],
    summary="Upsert mẫu deeplink",
    description="Thêm/cập nhật mẫu deeplink cho từng **merchant** và **network**.",
    response_model=schemas.AffiliateTemplateOut
)
def upsert_template(data: schemas.AffiliateTemplateCreate, db: Session = Depends(get_db)):
    tpl = crud.upsert_affiliate_template(db, data)
    return tpl

@app.put(
    "/aff/templates/{template_id}",
    tags=["Affiliate 🎯"],
    summary="Cập nhật mẫu deeplink",
    description="Sửa mẫu deeplink theo ID.",
    response_model=schemas.AffiliateTemplateOut
)
def update_template(template_id: int, data: schemas.AffiliateTemplateCreate, db: Session = Depends(get_db)):
    tpl = crud.update_affiliate_template(db, template_id, data)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl

@app.delete(
    "/aff/templates/{template_id}",
    tags=["Affiliate 🎯"],
    summary="Xoá mẫu deeplink",
    description="Xoá mẫu deeplink theo ID."
)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tpl = crud.delete_affiliate_template_by_id(db, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True, "deleted_id": template_id}

# Yêu cầu convert
class ConvertReq(BaseModel):
    merchant: str
    url: HttpUrl
    network: str = "accesstrade"
    params: Optional[Dict[str, str]] = None  # ví dụ {"sub1": "my_subid"}

class ConvertRes(BaseModel):
    affiliate_url: str
    short_url: str

# Convert link gốc -> deeplink + shortlink /r/{token}
@app.post(
    "/aff/convert",
    tags=["Affiliate 🎯"],
    summary="Chuyển link gốc → deeplink + shortlink",
    description=(
        "Nhận link gốc + merchant → trả về **affiliate_url** (deeplink) và **short_url** dạng `/r/{token}`.\n"
        "Hỗ trợ merge `default_params` từ template + `params` người dùng truyền."
    ),
    response_model=ConvertRes
)
def aff_convert(req: ConvertReq, db: Session = Depends(get_db)):
    if not _is_allowed_domain(req.merchant, str(req.url)):
        raise HTTPException(status_code=400, detail=f"URL không thuộc domain hợp lệ của {req.merchant}")

    tpl = crud.get_affiliate_template(db, req.merchant, req.network)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Chưa cấu hình template cho merchant={req.merchant}, network={req.network}")

    merged: Dict[str, str] = {}
    if tpl.default_params:
        merged.update(tpl.default_params)
    if req.params:
        merged.update(req.params)

    affiliate_url = _apply_template(tpl.template, str(req.url), merged)
    token = _make_token(affiliate_url)
    short_url = f"/r/{token}"
    return ConvertRes(affiliate_url=affiliate_url, short_url=short_url)

# Redirect từ shortlink -> deeplink thật
@app.get(
    "/r/{token}",
    tags=["Affiliate 🎯"],
    summary="Redirect shortlink",
    description="Giải mã token và chuyển hướng 302 tới **affiliate_url** thực tế."
)
def redirect_short_link(token: str):
    affiliate_url = _parse_token(token)
    return RedirectResponse(url=affiliate_url, status_code=302)

# =====================================================================
#                  NEW (Bước 3): Ingest/List từ Accesstrade
# =====================================================================

class IngestReq(BaseModel):
    provider: str = "accesstrade"                 # ví dụ: "accesstrade", "adpia", ...
    path: str = "/v1/publishers/product_search"   # tuỳ provider
    params: Dict[str, str] | None = None

class IngestAllDatafeedsReq(BaseModel):
    """
    Ingest toàn bộ datafeeds trong một lần (tự phân trang nội bộ).
    - params: bộ lọc chuyển thẳng đến provider (Accesstrade) và một số filter nội bộ:
        - merchant: lọc theo merchant/campaign slug của AT (vd: "tiki", "tiktokshop").
        - domain: lọc theo domain sản phẩm (vd: "tiki.vn").
        - campaign_id | camp_id: cố định đúng campaign_id cần ingest (ưu tiên nếu có).
        - update_from/update_to, price_from/to, discount_*: chuyển tiếp xuống API AT nếu hỗ trợ.
    - limit_per_page: kích thước trang khi gọi ra Accesstrade (mặc định 100)
    - max_pages: chặn vòng lặp vô hạn nếu API trả bất thường (mặc định 2000 trang)
    - throttle_ms: nghỉ giữa các lần gọi để tôn trọng rate-limit (mặc định 0ms)
    - check_urls: nếu True mới kiểm tra link sống (mặc định False).
    """
    params: Dict[str, str] | None = None
    limit_per_page: int = 100
    max_pages: int = 2000
    throttle_ms: int = 0
    check_urls: bool = False
    verbose: bool = False
    
class CampaignsSyncReq(BaseModel):
    """
    Đồng bộ campaigns từ Accesstrade (tối ưu tốc độ).
    - statuses: danh sách trạng thái cần quét, mặc định ["running","paused"].
    - only_my: True -> chỉ giữ approval in {"successful","pending"} (nhanh hơn, ít ghi DB).
    - enrich_user_status: lấy user_status thật từ campaign detail (chậm). Mặc định False để nhanh.
    - limit_per_page, page_concurrency, window_pages, throttle_ms: tinh chỉnh tốc độ vs độ ổn định.
    - merchant: nếu truyền sẽ lọc theo merchant sau khi fetch.
    """
    statuses: List[str] | None = None
    only_my: bool = True
    enrich_user_status: bool = True
    limit_per_page: int = 50
    page_concurrency: int = 6
    window_pages: int = 10
    throttle_ms: int = 300
    merchant: str | None = None

class IngestV2PromotionsReq(BaseModel):
    """
    Ingest khuyến mãi (offers_informations) theo merchant đã duyệt.
    - merchant: nếu truyền, chỉ ingest đúng merchant này; nếu bỏ trống sẽ chạy cho tất cả merchant active.
    - create_offers: nếu True, sẽ map mỗi promotion thành 1 offer tối thiểu (title/url/affiliate_url/image).
    - check_urls: nếu True mới kiểm tra link sống (mặc định False).
    """
    merchant: str | None = None
    create_offers: bool = True
    check_urls: bool = False
    verbose: bool = False

class IngestV2TopProductsReq(BaseModel):
    """
    Ingest top_products (bán chạy) theo merchant & khoảng ngày.
    - date_from/date_to: 'YYYY-MM-DD' (tùy Accesstrade hỗ trợ); nếu bỏ trống có thể lấy mặc định phía API.
    - limit_per_page: kích thước trang (<=100)
    - max_pages: số trang tối đa sẽ quét
    - throttle_ms: nghỉ giữa các lần gọi
    - check_urls: nếu True mới kiểm tra link sống (mặc định False).
    """
    merchant: str
    date_from: str | None = None
    date_to: str | None = None
    check_urls: bool = False
    verbose: bool = False
    limit_per_page: int = 100
    max_pages: int = 200
    throttle_ms: int = 0
# ================================
# Unified provider-agnostic ingest (front-door)
class UnifiedCampaignsSyncReq(CampaignsSyncReq):
    provider: str = "accesstrade"

class UnifiedPromotionsReq(IngestV2PromotionsReq):
    provider: str = "accesstrade"

class UnifiedTopProductsReq(IngestV2TopProductsReq):
    provider: str = "accesstrade"

class UnifiedDatafeedsAllReq(IngestAllDatafeedsReq):
    provider: str = "accesstrade"

## Removed duplicated earlier unified endpoints (replaced by a single consolidated set below)

# ---------------- Provider registry wiring ----------------
_registry = ProviderRegistry()

# Build Accesstrade ops from existing handlers
async def _accesstrade_campaigns_sync(req: "CampaignsSyncReq", db: Session):
    return await ingest_v2_campaigns_sync(req, db)

async def _accesstrade_promotions(req: "IngestV2PromotionsReq", db: Session):
    return await ingest_v2_promotions(req, db)

async def _accesstrade_top_products(req: "IngestV2TopProductsReq", db: Session):
    return await ingest_v2_top_products(req, db)

async def _accesstrade_datafeeds_all(req: "IngestAllDatafeedsReq", db: Session):
    return await ingest_accesstrade_datafeeds_all(req, db)

# products op will be provided by a helper implemented below
async def _accesstrade_products(req: "IngestReq", db: Session):
    return await _ingest_products_accesstrade_impl(req, db)

_registry.register("accesstrade", ProviderOps(
    campaigns_sync=_accesstrade_campaigns_sync,
    promotions=_accesstrade_promotions,
    top_products=_accesstrade_top_products,
    datafeeds_all=_accesstrade_datafeeds_all,
    products=_accesstrade_products,
))

from sqlalchemy import func

@app.get("/campaigns/summary", tags=["Campaigns 📢"])
def campaigns_summary(db: Session = Depends(get_db)):
    total = db.query(func.count(models.Campaign.campaign_id)).scalar() or 0

    by_status = {
        (k or "NULL"): v
        for (k, v) in db.query(models.Campaign.status, func.count())
                        .group_by(models.Campaign.status).all()
    }
    by_user_status = {
        (k or "NULL"): v
        for (k, v) in db.query(models.Campaign.user_registration_status, func.count())
                        .group_by(models.Campaign.user_registration_status).all()
    }

    running_approved_count = (
            db.query(func.count(models.Campaign.campaign_id))
            .filter(models.Campaign.status == "running")
            .filter(models.Campaign.user_registration_status.in_(["APPROVED", "SUCCESSFUL"]))
            .scalar() or 0
    )
    approved_merchants = sorted({
            m for (m,) in db.query(models.Campaign.merchant)
                            .filter(models.Campaign.status == "running")
                            .filter(models.Campaign.user_registration_status.in_(["APPROVED", "SUCCESSFUL"]))
                            .distinct().all()
            if m
    })

    return {
        "total": total,
        "by_status": by_status,
        "by_user_status": by_user_status,
        "running_approved_count": running_approved_count,
        "approved_merchants": approved_merchants
    }

@app.post("/maintenance/normalize-campaigns", tags=["Campaigns 📢"], summary="Chuẩn hoá dữ liệu campaign (v1 → v2)")
def normalize_campaigns(db: Session = Depends(get_db)):
    """
    Di chuyển các giá trị 'successful/pending/unregistered' từ cột approval
    sang user_registration_status, rồi set approval = NULL.
    """
    rows = db.query(models.Campaign).all()
    moved = 0
    for r in rows:
        val = (r.approval or "").strip().lower() if r.approval else ""
        if val in ("successful", "pending", "unregistered"):
            r.user_registration_status = "APPROVED" if val == "successful" else val.upper()
            r.approval = None
            db.add(r)
            moved += 1
    db.commit()
    return {"ok": True, "moved": moved}

@app.get("/campaigns", response_model=list[schemas.CampaignOut], tags=["Campaigns 📢"])
def list_campaigns_api(
    status: str | None = None,
    approval: str | None = None,
    user_status: str | None = None,
    merchant: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Campaign)
    if status:
        q = q.filter(models.Campaign.status == status)
    # filter chính xác theo tài liệu: approval = unregistered/pending/successful
    if approval:
        q = q.filter(models.Campaign.approval == approval)
    # hỗ trợ user_status: ưu tiên cột user_registration_status; nếu NULL mới fallback về approval map
    if user_status:
        us = user_status.strip().upper()
        fallback = {
            "APPROVED": "successful",
            "PENDING": "pending",
            "NOT_REGISTERED": "unregistered",
        }.get(us)
        if fallback:
            q = q.filter(
                or_(
                    models.Campaign.user_registration_status == us,
                    and_(models.Campaign.user_registration_status == None,
                         models.Campaign.approval == fallback)
                )
            )
        else:
            q = q.filter(models.Campaign.user_registration_status == us)
    if merchant:
        q = q.filter(models.Campaign.merchant == merchant)
    return q.order_by(models.Campaign.updated_at.desc()).all()

@app.get("/campaigns/approved-merchants", response_model=list[str], tags=["Campaigns 📢"])
def list_approved_merchants_api(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Campaign.merchant)
        .filter(models.Campaign.status == "running")
        .filter(or_(
            models.Campaign.user_registration_status == "APPROVED",
            models.Campaign.user_registration_status == "SUCCESSFUL",
        ))
        .distinct()
        .all()
    )
    merchants = sorted({m for (m,) in rows if m})
    return merchants

@app.get("/offers", response_model=list[schemas.ProductOfferOut], tags=["Offers 🛒"])
def list_offers_api(
    merchant: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    🛒 Lấy danh sách sản phẩm trong DB có phân trang  
    - `merchant`: lọc theo tên merchant (vd: `shopee`, `lazada`, `tiki`)  
    - `skip`: số bản ghi bỏ qua (offset)  
    - `limit`: số bản ghi tối đa trả về  
    """
    rows = crud.list_offers(db, merchant=merchant, skip=skip, limit=limit)

    out: list[dict] = []
    for o in rows:
        item = {
            "id": o.id,
            "title": o.title,
            "url": o.url,
            "affiliate_url": o.affiliate_url,
            "image_url": o.image_url,
            "merchant": o.merchant,
            "campaign_id": o.campaign_id,
            "price": o.price,
            "currency": o.currency,
            # Model không có 'status'; giữ key cho tương thích, map sang approval_status
            "status": getattr(o, "status", None) or o.approval_status,
            "approval_status": o.approval_status,
            "eligible_commission": o.eligible_commission,
            "source_type": o.source_type,
            "affiliate_link_available": o.affiliate_link_available,
            "product_id": o.product_id,
            "extra": o.extra,
            "updated_at": o.updated_at,
            "desc": None, "cate": None, "shop_name": None, "update_time_raw": None,
        }

        try:
            ex = json.loads(o.extra) if o.extra else {}
            item["desc"] = ex.get("desc")
            item["cate"] = ex.get("cate")
            item["shop_name"] = ex.get("shop_name")
            item["update_time_raw"] = ex.get("update_time_raw") or ex.get("update_time")
        except Exception:
            pass
        out.append(item)

    return out

@app.post(
    "/ingest/policy",
    tags=["Offers 🛒"],
    summary="Cấu hình policy ingest",
    description="Bật/tắt chế độ chỉ ingest sản phẩm có commission policy."
)
def set_ingest_policy(only_with_commission: bool = False, db: Session = Depends(get_db)):
    model_str = f"only_with_commission={'true' if only_with_commission else 'false'}"
    cfg = crud.upsert_api_config_by_name(db, schemas.APIConfigCreate(
        name="ingest_policy",
        base_url="-",
        api_key="-",
        model=model_str,
    ))
    return {"ok": True, "ingest_policy": model_str, "config_id": cfg.id}

@app.post(
    "/ingest/policy/check-urls",
    tags=["Offers 🛒"],
    summary="Bật/tắt kiểm tra link khi IMPORT EXCEL",
    description="Chỉ ảnh hưởng import Excel. API ingest (V1/V2) luôn mặc định KHÔNG check link."
)
def set_ingest_policy_check_urls(enable: bool = False, db: Session = Depends(get_db)):
    # dùng store flags trong api_configs.name='ingest_policy'
    crud.set_policy_flag(db, "check_urls", enable)
    flags = crud.get_policy_flags(db)
    return {"ok": True, "flags": flags}

@app.post(
    "/ingest/products",
    tags=["Offers 🛒"],
    summary="Ingest sản phẩm từ nhiều provider",
    description=(
        "Nhập sản phẩm vào DB từ nhiều provider (ví dụ: Accesstrade). "
        "Hiện hỗ trợ `provider=accesstrade`. Các provider khác có thể bổ sung sau."
    )
)
async def ingest_products(
    req: IngestReq,
    db: Session = Depends(get_db),
):
    provider = (req.provider or "accesstrade").lower()
    ops = _registry.get(provider)
    if not ops:
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' hiện chưa được hỗ trợ")
    return await ops.products(req, db)

# Internal helper: Accesstrade implementation for products ingest
async def _ingest_products_accesstrade_impl(req: IngestReq, db: Session):
    from accesstrade_service import (
        fetch_active_campaigns, fetch_campaign_detail, fetch_products,
        fetch_promotions, fetch_commission_policies, map_at_product_to_offer, _check_url_alive,
    )
    active_campaigns = await fetch_active_campaigns(db)
    logger.info("Fetched %d active campaigns", len(active_campaigns))
    merchant_campaign_map = {v: k for k, v in active_campaigns.items()}

    items = await fetch_products(db, req.path, req.params or {})
    if not items:
        return {"ok": True, "imported": 0}

    imported = 0
    def _vlog(reason: str, extra: dict | None = None):
        try:
            from accesstrade_service import _log_jsonl as _rawlog
            payload = {"endpoint": "manual_ingest", "reason": reason}
            if extra:
                payload.update(extra)
            _rawlog("ingest_skips.jsonl", payload)
        except Exception:
            pass

    for it in items:
        policies = []  # ensure defined for each iteration
        camp_id = str(it.get("campaign_id") or it.get("campaign_id_str") or "").strip()
        merchant = str(it.get("merchant") or it.get("campaign") or "").lower().strip()
        _alias = {"lazadacps": "lazada", "tikivn": "tiki"}
        merchant_norm = _alias.get(merchant, merchant.split(".")[0] if "." in merchant else merchant)

        def _resolve_campaign_id_by_suffix(m_name: str) -> tuple[str | None, str]:
            if m_name in merchant_campaign_map:
                return merchant_campaign_map[m_name], "exact"
            for m_key, cid in merchant_campaign_map.items():
                if m_key.endswith(m_name) or f"_{m_name}" in m_key:
                    return cid, f"suffix({m_key})"
            for m_key, cid in merchant_campaign_map.items():
                if m_name in m_key:
                    return cid, f"contains({m_key})"
            return None, ""

        if not camp_id:
            camp_id, how = _resolve_campaign_id_by_suffix(merchant_norm)
            if camp_id:
                logger.debug("Fallback campaign_id=%s via %s cho merchant=%s (norm=%s) [manual ingest]",
                             camp_id, how, merchant, merchant_norm)
            else:
                _vlog("no_campaign_match", {"merchant": merchant, "merchant_norm": merchant_norm})

        if not camp_id or camp_id not in active_campaigns:
            logger.info("Skip product vì campaign_id=%s không active [manual ingest] (merchant=%s)", camp_id, merchant_norm)
            _vlog("campaign_not_active", {"campaign_id": camp_id, "merchant": merchant_norm})
            continue

        try:
            _row = crud.get_campaign_by_cid(db, camp_id)
            if not _row or (_row.user_registration_status or "").upper() != "APPROVED":
                logger.info("Skip product vì campaign_id=%s chưa APPROVED [manual ingest]", camp_id)
                _vlog("campaign_not_approved", {"campaign_id": camp_id})
                continue
        except Exception:
            continue

        promotions_data = await fetch_promotions(db, merchant_norm) if merchant_norm else []
        if promotions_data:
            for prom in promotions_data:
                try:
                    crud.upsert_promotion(db, schemas.PromotionCreate(
                        campaign_id=camp_id,
                        name=prom.get("name"),
                        content=prom.get("content") or prom.get("description"),
                        start_time=prom.get("start_time"),
                        end_time=prom.get("end_time"),
                        coupon=prom.get("coupon"),
                        link=prom.get("link"),
                    ))
                except Exception as e:
                    logger.debug("Skip promotion upsert: %s", e)

        try:
            camp = await fetch_campaign_detail(db, camp_id)
            if camp:
                status_val = camp.get("status")
                approval_val = camp.get("approval")
                _user_raw = (
                    camp.get("user_registration_status")
                    or camp.get("publisher_status")
                    or camp.get("user_status")
                )
                def _map_status(v):
                    s = str(v).strip() if v is not None else None
                    if s == "1": return "running"
                    if s == "0": return "paused"
                    return s
                crud.upsert_campaign(db, schemas.CampaignCreate(
                    campaign_id=str(camp.get("campaign_id") or camp_id),
                    merchant=str(camp.get("merchant") or merchant_norm or "").lower() or None,
                    name=camp.get("name"),
                    status=_map_status(status_val),
                    approval=(str(approval_val) if approval_val is not None else None),
                    start_time=camp.get("start_time"),
                    end_time=camp.get("end_time"),
                    user_registration_status=(_user_raw if _user_raw not in (None, "", []) else None),
                ))
        except Exception as e:
            logger.debug("Skip campaign upsert: %s", e)

        try:
            policies = await fetch_commission_policies(db, camp_id)
            for rec in (policies or []):
                crud.upsert_commission_policy(db, schemas.CommissionPolicyCreate(
                    campaign_id=camp_id,
                    reward_type=rec.get("reward_type") or rec.get("type"),
                    sales_ratio=rec.get("sales_ratio") or rec.get("ratio"),
                    sales_price=rec.get("sales_price"),
                    target_month=rec.get("target_month"),
                ))
        except Exception as e:
            logger.debug("Skip commission upsert: %s", e)

        data = map_at_product_to_offer(it, commission=policies, promotion=promotions_data)
        if not data.get("url") or not data.get("source_id"):
            continue

        data["campaign_id"] = camp_id
        data["source_type"] = "manual"
        _camp_row = crud.get_campaign_by_cid(db, camp_id)
        if _camp_row:
            us = (_camp_row.user_registration_status or "").upper()
            data["approval_status"] = (
                "successful" if us == "APPROVED" else
                "pending" if us == "PENDING" else
                "unregistered" if us == "NOT_REGISTERED" else None
            )
            data["eligible_commission"] = (
                (_camp_row.status == "running") and (us in ("APPROVED", "SUCCESSFUL"))
            )

        if not await _check_url_alive(str(data.get("url") or "")):
            logger.info("Skip dead product [manual ingest]: title='%s'", data.get("title"))
            _vlog("dead_url", {"url": data.get("url")})
            continue

        crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(**data))
        imported += 1

    return {"ok": True, "imported": imported}

async def ingest_accesstrade_datafeeds_all(
    req: IngestAllDatafeedsReq,
    db: Session = Depends(get_db),
):

    # Dùng luôn session `db` từ Depends; không mở/đóng session mới tại đây
    from accesstrade_service import fetch_campaigns_full_all, fetch_campaign_detail
    items = await fetch_campaigns_full_all(
        db,
        status="running",
        limit_per_page=req.limit_per_page or 100,
        max_pages=req.max_pages or 200,
        throttle_ms=req.throttle_ms or 0
    )
    imported = 0
    for camp in (items or []):
        try:
            camp_id = str(camp.get("campaign_id") or camp.get("id") or "").strip()
            merchant = str(camp.get("merchant") or camp.get("name") or "").lower().strip()
            status_val = camp.get("status")
            approval_val = camp.get("approval")

            # map status "1/0" -> "running/paused" nếu API trả dạng số
            def _map_status(v):
                s = str(v).strip() if v is not None else None
                if s == "1": return "running"
                if s == "0": return "paused"
                return s

            # Tách approval (kiểu duyệt campaign) ↔ user_status (trạng thái đăng ký của riêng mình)
            def _split_approval_or_user(v):
                if v is None:
                    return (None, None)
                s = str(v).strip().lower()
                if s in ("successful", "pending", "unregistered"):
                    # Đây thực chất là trạng thái đăng ký của bạn
                    user = "APPROVED" if s == "successful" else s.upper()
                    return (None, user)
                return (str(v), None)

            approval_for_campaign, user_status = _split_approval_or_user(approval_val)

            # NEW: nếu API không cung cấp user_status, dùng giá trị cũ trong DB để tránh mất record
            existing = crud.get_campaign_by_cid(db, camp_id)
            eff_user = user_status or (existing.user_registration_status if existing else None)

            # Lọc: chỉ giữ APPROVED/PENDING
            if eff_user not in ("APPROVED", "PENDING"):
                continue
            # Không enrich ở job định kỳ để nhanh (có thể bật ở API /ingest/v2/campaigns/sync)

            payload = schemas.CampaignCreate(
                campaign_id=camp_id,
                merchant=merchant or None,
                name=camp.get("name"),
                status=_map_status(status_val),
                approval=approval_for_campaign,                 # KHÔNG còn ghi 'successful/pending/unregistered' ở đây
                start_time=camp.get("start_time"),
                end_time=camp.get("end_time"),
                user_registration_status=user_status,           # NOT_REGISTERED/PENDING/APPROVED hoặc None
            )

            crud.upsert_campaign(db, payload)
            imported += 1
        except Exception as e:
            logger.debug("Skip campaign upsert: %s", e)

    logger.info("Scheduled campaigns sync done: %s", imported)

    from accesstrade_service import (
        fetch_products, fetch_active_campaigns, fetch_promotions,
        fetch_commission_policies, fetch_campaign_detail,
        map_at_product_to_offer, _check_url_alive
    )

    # 0) Lấy danh sách campaign đang chạy để lọc
    active_campaigns = await fetch_active_campaigns(db)  # dict {campaign_id: merchant}
    if not active_campaigns:
        # Fallback: lấy từ DB nếu API không trả (ổn định cho smoke test)
        active_campaigns = {
            c.campaign_id: c.merchant
            for c in db.query(models.Campaign)
                        .filter(models.Campaign.status == "running")
                        .filter(models.Campaign.user_registration_status.in_(["APPROVED","SUCCESSFUL"]))
                        .all()
            if c.campaign_id and c.merchant
        }
    merchant_campaign_map = {v: k for k, v in active_campaigns.items()}  # {merchant: campaign_id}

    # Map merchant -> approved campaign_id (running + user APPROVED/SUCCESSFUL) for fallback rebinding
    approved_cid_by_merchant: dict[str, str] = {}
    try:
        for cid, m in active_campaigns.items():
            _row = crud.get_campaign_by_cid(db, cid)
            if _row and (_row.user_registration_status or "").upper() in ("APPROVED", "SUCCESSFUL"):
                approved_cid_by_merchant[(m or "").lower()] = cid
    except Exception:
        pass

    # chính sách ingest (API bỏ qua policy; policy chỉ áp dụng cho import Excel)
    only_with_commission = False

    # 2) Cache promotions theo merchant để tránh gọi trùng
    promotion_cache: dict[str, list[dict]] = {}

    # NEW: Cache commission theo campaign_id để tránh spam API (fix NameError)
    cache_commissions: dict[str, list[dict]] = {}

    # 3) Tham số gọi API datafeeds + bộ lọc phía server
    base_params = dict(req.params or {})
    base_params.pop("page", None)   # client không cần truyền
    base_params.pop("limit", None)  # client không cần truyền

    # Chuẩn hoá alias filters
    filter_merchant = (base_params.get("merchant") or base_params.get("campaign") or base_params.get("merchant_slug"))
    if isinstance(filter_merchant, str):
        filter_merchant = filter_merchant.strip().lower()
    filter_cid = (base_params.get("campaign_id") or base_params.get("camp_id"))
    if isinstance(filter_cid, str):
        filter_cid = filter_cid.strip()

    imported = 0
    total_pages = 0

    # Xây danh sách merchants cần chạy: ưu tiên từ active_campaigns (đang chạy) ∩ DB (APPROVED)
    approved_merchants: set[str] = set()
    try:
        for cid, m in active_campaigns.items():
            _row = crud.get_campaign_by_cid(db, cid)
            if _row and (_row.user_registration_status or "").upper() in ("APPROVED", "SUCCESSFUL"):
                approved_merchants.add((m or "").lower())
    except Exception:
        pass
    if not approved_merchants:
        # Fallback: lấy từ DB
        approved_merchants = {
            (c.merchant or "").lower()
            for c in db.query(models.Campaign)
                        .filter(models.Campaign.status == "running")
                        .filter(models.Campaign.user_registration_status.in_(["APPROVED","SUCCESSFUL"]))
                        .all()
            if c.merchant
        }

    # Áp dụng filter merchant/campaign_id nếu có
    forced_cid_by_merchant: dict[str, str] = {}
    if filter_cid:
        # Nếu campaign_id có trong active list, giới hạn merchant tương ứng
        cid = str(filter_cid)
        m = active_campaigns.get(cid)
        if m:
            m_norm = (m or "").lower()
            approved_merchants = {m_norm} if m_norm in approved_merchants else set()
            forced_cid_by_merchant[m_norm] = cid
        else:
            # Không tìm thấy campaign_id đang chạy → không ingest gì
            approved_merchants = set()

    if filter_merchant:
        m_norm = filter_merchant
        # alias nội bộ
        _alias = {"lazadacps": "lazada", "tikivn": "tiki"}
        m_norm = _alias.get(m_norm, m_norm)
        if approved_merchants:
            approved_merchants = {m for m in approved_merchants if (m == m_norm or m.endswith(m_norm) or (m_norm in m))}
        else:
            # nếu trước đó rỗng (ví dụ đã lọc theo campaign_id không khớp) thì giữ rỗng
            pass

    # verbose helper
    def _vlog(reason: str, extra: dict | None = None):
        try:
            from accesstrade_service import _log_jsonl as _rawlog
            payload = {"endpoint": "datafeeds_all", "reason": reason}
            if extra:
                payload.update(extra)
            _rawlog("ingest_skips.jsonl", payload)
        except Exception:
            pass

    # Lặp từng merchant đã APPROVED và gọi /v1/datafeeds với bộ lọc merchant
    for m in sorted(approved_merchants):
        _alias = {"lazadacps": "lazada", "tikivn": "tiki"}
        merchant_fetch = _alias.get(m, m)

        # Xác định campaign_id tương ứng merchant đang fetch (ưu tiên exact, sau đó suffix/contains)
        cid_for_fetch = None
        # Ưu tiên forced campaign id nếu đã xác định
        if m in forced_cid_by_merchant:
            cid_for_fetch = forced_cid_by_merchant[m]
        for cid, mm in active_campaigns.items():
            if (mm or "").lower() == merchant_fetch or (mm or "").lower() == m:
                cid_for_fetch = cid
                break
        if not cid_for_fetch:
            for cid, mm in active_campaigns.items():
                mm_l = (mm or "").lower()
                if mm_l.endswith(merchant_fetch) or f"_{merchant_fetch}" in mm_l or (merchant_fetch in mm_l):
                    cid_for_fetch = cid
                    break
        if not cid_for_fetch and merchant_fetch != m:
            for cid, mm in active_campaigns.items():
                mm_l = (mm or "").lower()
                if mm_l.endswith(m) or f"_{m}" in mm_l or (m in mm_l):
                    cid_for_fetch = cid
                    break

        page = 1
        while page <= max(1, req.max_pages):
            params = dict(base_params)
            params["page"] = str(page)
            params["limit"] = str(req.limit_per_page)
            params["merchant"] = merchant_fetch

            items = await fetch_products(db, "/v1/datafeeds", params)
            if not items:
                # Không có dữ liệu cho merchant/page này → dừng merchant
                break

            # Xử lý từng item
            for it in items:
                # Gắn merchant theo vòng lặp ngoài và force-bind campaign_id theo merchant đang fetch
                merchant_norm = m
                camp_id = cid_for_fetch

                # Bỏ qua nếu campaign không active
                if not camp_id or camp_id not in active_campaigns:
                    if req.verbose:
                        _vlog("campaign_not_active", {"campaign_id": camp_id, "merchant": merchant_norm, "page": page})
                    continue

                # YÊU CẦU: user APPROVED
                try:
                    _row = crud.get_campaign_by_cid(db, camp_id)
                    us = (_row.user_registration_status or "").upper() if _row else ""
                    if (not _row) or (us not in ("APPROVED", "SUCCESSFUL")):
                        # Fallback: nếu merchant có campaign khác đã APPROVED, dùng campaign đó
                        alt_cid = approved_cid_by_merchant.get(merchant_norm)
                        if alt_cid:
                            if req.verbose:
                                _vlog("rebind_campaign_id", {"from": camp_id, "to": alt_cid, "merchant": merchant_norm, "page": page})
                            camp_id = alt_cid
                        else:
                            if req.verbose:
                                _vlog("campaign_not_approved", {"campaign_id": camp_id, "merchant": merchant_norm, "page": page})
                            continue
                except Exception:
                    continue

                # Lấy commission theo camp_id (cache)
                policies = cache_commissions.get(camp_id)
                if policies is None:
                    try:
                        policies = await fetch_commission_policies(db, camp_id)
                        cache_commissions[camp_id] = policies or []
                        for p in (policies or []):
                            crud.upsert_commission_policy(db, schemas.CommissionPolicyCreate(
                                campaign_id=str(camp_id),
                                reward_type=p.get("reward_type") or p.get("type"),
                                sales_ratio=p.get("sales_ratio") or p.get("ratio"),
                                sales_price=p.get("sales_price"),
                                target_month=p.get("target_month"),
                            ))
                    except Exception:
                        policies = []
                        logger.debug("Skip commission upsert")

                if only_with_commission:
                    eligible_by_status = False
                    try:
                        _camp_row = crud.get_campaign_by_cid(db, camp_id)
                        if _camp_row:
                            _us = (_camp_row.user_registration_status or "").upper()
                            eligible_by_status = (_camp_row.status == "running") and (_us == "APPROVED")
                    except Exception:
                        eligible_by_status = False

                    has_commission = bool(policies) or eligible_by_status
                    if not has_commission:
                        if req.verbose:
                            _vlog("no_commission", {"campaign_id": camp_id, "merchant": merchant_norm, "page": page})
                        continue

                # Promotions: lấy theo merchant, có cache + upsert DB
                if merchant_norm not in promotion_cache:
                    promotion_cache[merchant_norm] = await fetch_promotions(db, merchant_norm) or []
                pr_list = promotion_cache.get(merchant_norm, [])
                if pr_list:
                    for prom in pr_list:
                        try:
                            crud.upsert_promotion(db, schemas.PromotionCreate(
                                campaign_id=camp_id,
                                name=prom.get("name"),
                                content=prom.get("content") or prom.get("description"),
                                start_time=prom.get("start_time"),
                                end_time=prom.get("end_time"),
                                coupon=prom.get("coupon"),
                                link=prom.get("link"),
                            ))
                        except Exception as e:
                            logger.debug("Skip promotion upsert: %s", e)

                # Campaign detail: đồng nhất upsert
                try:
                    camp = await fetch_campaign_detail(db, camp_id)
                    if camp:
                        status_val = camp.get("status")
                        approval_val = camp.get("approval")

                        def _map_status(v):
                            s = str(v).strip() if v is not None else None
                            if s == "1": return "running"
                            if s == "0": return "paused"
                            return s

                        _user_raw = (
                            camp.get("user_registration_status")
                            or camp.get("publisher_status")
                            or camp.get("user_status")
                        )
                        crud.upsert_campaign(db, schemas.CampaignCreate(
                            campaign_id=str(camp.get("campaign_id") or camp_id),
                            merchant=str(camp.get("merchant") or merchant_norm or "").lower() or None,
                            name=camp.get("name"),
                            status=_map_status(status_val),
                            approval=(str(approval_val) if approval_val is not None else None),
                            start_time=camp.get("start_time"),
                            end_time=camp.get("end_time"),
                            user_registration_status=(_user_raw if _user_raw not in (None, "", []) else None),
                        ))
                except Exception as e:
                    logger.debug("Skip campaign upsert: %s", e)

                # Chuẩn hoá record → ProductOfferCreate
                data = map_at_product_to_offer(it, commission=policies, promotion=pr_list)
                if not data or not data.get("url"):
                    continue
                data["campaign_id"] = camp_id

                # NEW: gắn loại nguồn + trạng thái phê duyệt & eligibility
                data["source_type"] = "datafeeds"
                _camp_row = crud.get_campaign_by_cid(db, camp_id)
                if _camp_row:
                    us = (_camp_row.user_registration_status or "").upper()
                    data["approval_status"] = (
                        "successful" if us == "APPROVED" else
                        "pending" if us == "PENDING" else
                        "unregistered" if us == "NOT_REGISTERED" else None
                    )
                    data["eligible_commission"] = (
                        (_camp_row.status == "running") and (us in ("APPROVED", "SUCCESSFUL"))
                    )

                # Link gốc: chỉ kiểm tra khi bật cờ (để tránh bỏ sót do chặn bot/timeout trong môi trường container)
                if req.check_urls:
                    if not await _check_url_alive(data["url"]):
                        if req.verbose:
                            _vlog("dead_url", {"url": data.get("url"), "merchant": merchant_norm, "page": page})
                        continue

                crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(**data))
                imported += 1

            # Sau khi xử lý xong 1 trang cho merchant hiện tại
            total_pages += 1
            # Dừng nếu trang hiện tại ít hơn limit → coi như trang cuối
            if len(items) < (req.limit_per_page or 100):
                break

            # Trang tiếp theo
            page += 1
            sleep_ms = getattr(req, "throttle_ms", 0) or 0
            if sleep_ms:
                await asyncio.sleep(sleep_ms / 1000.0)

    return {"ok": True, "imported": imported, "pages": total_pages}

async def ingest_v2_campaigns_sync(
    req: CampaignsSyncReq,
    db: Session = Depends(get_db),
):
    from accesstrade_service import fetch_campaigns_full_all, fetch_campaign_detail

    # --- gom dữ liệu theo nhiều trạng thái (running/paused/...) nếu được truyền ---
    statuses = (req.statuses or ["running"])  # mặc định chỉ 'running' để nhanh; bạn có thể gửi ["running","paused"]
    unique = {}
    for st in statuses:
        try:
            items = await fetch_campaigns_full_all(
                db,
                status=st,
                limit_per_page=req.limit_per_page or 50,
                max_pages=1000,
                throttle_ms=req.throttle_ms or 0,
                page_concurrency=req.page_concurrency or 6,
                window_pages=req.window_pages or 10,
            )
            for it in (items or []):
                cid = str(it.get("campaign_id") or it.get("id") or "").strip()
                if cid:
                    unique[cid] = it
        except Exception as e:
            logger.error("ingest_v2_campaigns_sync: fetch failed (%s): %s", st, e)

    imported = 0

    def _map_status(v):
        s = str(v).strip() if v is not None else None
        if s == "1": return "running"
        if s == "0": return "paused"
        return s

    def _split_approval_or_user(v):
        """
        Nếu AT trả 'approval' ∈ {successful,pending,unregistered} thì đây thực chất là user_status.
        Trả về tuple: (approval_for_campaign, user_status_for_me)
        """
        if v is None:
            return (None, None)
        s = str(v).strip().lower()
        if s in ("successful", "pending", "unregistered"):
            # map về NOT_REGISTERED/PENDING/APPROVED
            user = "APPROVED" if s == "successful" else s.upper()
            return (None, user)
        # còn lại để nguyên cho kiểu duyệt (auto/manual/…)
        return (str(v), None)

    for camp in unique.values():
        try:
            camp_id = str(camp.get("campaign_id") or camp.get("id") or "").strip()
            merchant = str(camp.get("merchant") or camp.get("name") or "").lower().strip()
            if req.merchant and merchant != req.merchant.strip().lower():
                continue

            status_val = _map_status(camp.get("status"))
            approval_val, user_status = _split_approval_or_user(camp.get("approval"))

            # enrich user_status từ detail nếu bật cờ (chính xác hơn)
            if req.enrich_user_status or (req.only_my and not user_status):
                try:
                    det = await fetch_campaign_detail(db, camp_id)
                    if det:
                        _user_raw = (
                            det.get("user_registration_status")
                            or det.get("publisher_status")
                            or det.get("user_status")
                        )
                        # Fallback: đôi khi detail chỉ trả 'approval' = successful/pending/unregistered
                        if not _user_raw:
                            appr_det = det.get("approval")
                            if isinstance(appr_det, str) and appr_det.lower() in ("successful","pending","unregistered"):
                                _user_raw = "APPROVED" if appr_det.lower() == "successful" else appr_det.upper()
                        if _user_raw not in (None, "", []):
                            user_status = str(_user_raw).strip().upper()
                except Exception:
                    pass

            # Lọc only_my: chỉ giữ APPROVED/PENDING.
            # Nếu đã bật enrich_user_status nhưng vẫn KHÔNG lấy được user_status (API không trả),
            # cho phép import để lưu lại trước (tránh imported=0 ở lần đầu).
            if req.only_my:
                existing = crud.get_campaign_by_cid(db, camp_id)
                eff_user = user_status or (existing.user_registration_status if existing else None)
                if eff_user not in ("APPROVED", "PENDING"):
                    if req.enrich_user_status and eff_user is None:
                        logger.debug("only_my=true: allow %s (%s) dù user_status chưa rõ (first-run).", camp_id, merchant)
                    else:
                        logger.debug("only_my=true: skip %s (%s) vì user_status=%s", camp_id, merchant, eff_user)
                        continue

            payload = schemas.CampaignCreate(
                campaign_id=camp_id,
                merchant=merchant or None,
                name=camp.get("name"),
                status=status_val,
                approval=approval_val,                  # KHÔNG còn ghi 'successful' ở đây nữa
                start_time=camp.get("start_time"),
                end_time=camp.get("end_time"),
                user_registration_status=user_status,   # NOT_REGISTERED / PENDING / APPROVED / None
            )
            crud.upsert_campaign(db, payload)
            imported += 1
        except Exception as e:
            logger.debug("Skip campaign upsert: %s", e)

    return {"ok": True, "imported": imported}

# (Removed) Aliases for Accesstrade routes — use unified endpoints instead

async def ingest_v2_promotions(
    req: IngestV2PromotionsReq,
    db: Session = Depends(get_db),
):
    from accesstrade_service import fetch_promotions, fetch_active_campaigns, _check_url_alive
    imported_promos = 0
    imported_offers = 0

    # 0) Xác định merchant cần chạy: 1 merchant hoặc tất cả merchant đang active
    active = await fetch_active_campaigns(db)  # {campaign_id: merchant}
    merchants = set(active.values())
    if not merchants:
        # Fallback: từ DB
        merchants = {
            (c.merchant or "").lower()
            for c in db.query(models.Campaign)
                        .filter(models.Campaign.status == "running")
                        .filter(models.Campaign.user_registration_status.in_(["APPROVED","SUCCESSFUL"]))
                        .all()
            if c.merchant
        }
    if req.merchant:
        merchants = {req.merchant.strip().lower()}

    # 1) Vòng lặp từng merchant
    for m in sorted(merchants):
        _alias = {"lazadacps": "lazada", "tikivn": "tiki"}
        m_fetch = _alias.get(m, m)
        promos = await fetch_promotions(db, m_fetch) or []
        # upsert bảng promotions
        for p in promos:
            try:
                # map campaign_id từ merchant
                # ưu tiên exact, nếu không có thì bỏ trống
                campaign_id = None
                # Ưu tiên exact theo m hoặc m_fetch
                for cid, mm in active.items():
                    mm_l = (mm or "").lower()
                    if mm_l == m or mm_l == m_fetch:
                        campaign_id = cid
                        break
                # Nếu chưa khớp, thử suffix/contains (đỡ lệch alias)
                if not campaign_id:
                    for cid, mm in active.items():
                        mm_l = (mm or "").lower()
                        if mm_l.endswith(m) or f"_{m}" in mm_l or (m in mm_l):
                            campaign_id = cid
                            break
                if not campaign_id and m_fetch != m:
                    for cid, mm in active.items():
                        mm_l = (mm or "").lower()
                        if mm_l.endswith(m_fetch) or f"_{m_fetch}" in mm_l or (m_fetch in mm_l):
                            campaign_id = cid
                            break

                crud.upsert_promotion(db, schemas.PromotionCreate(
                    campaign_id=campaign_id or "",
                    name=p.get("name"),
                    content=p.get("content") or p.get("description"),
                    start_time=p.get("start_time"),
                    end_time=p.get("end_time"),
                    coupon=p.get("coupon"),
                    link=p.get("link"),
                ))
                imported_promos += 1

                if req.create_offers:
                    # map promotion -> offer tối thiểu
                    title = p.get("name") or "Khuyến mãi"
                    link = p.get("link") or p.get("url")
                    aff = p.get("aff_link")
                    img = p.get("image") or p.get("thumb") or p.get("banner")

                    # CHO PHÉP TẠO OFFER KHI CHỈ CÓ aff_link
                    if not link and not aff:
                        logger.debug("[PROMO] skip: no link/aff for %s (merchant=%s)", title, m)
                        continue

                    url_to_check = link or aff

                    # (policy) chỉ check khi bật cờ
                    alive = True if not req.check_urls else await _check_url_alive(str(url_to_check or ""))
                    if not alive:
                        logger.debug("[PROMO] skip: dead url %s", url_to_check)
                        continue

                    # source_id cố định theo link/aff_link để idempotent
                    sid_base = (link or aff or "").encode("utf-8")
                    sid = hashlib.md5(sid_base).hexdigest()
                    extra = {
                        "source_type": "promotions",
                        "raw": p,
                    }
                    # Chỉ tạo offer nếu campaign đã duyệt (SUCCESSFUL/APPROVED)
                    try:
                        _row = crud.get_campaign_by_cid(db, campaign_id) if campaign_id else None
                        _user = (_row.user_registration_status or "").upper() if _row else ""
                        if not _row or _user not in ("APPROVED", "SUCCESSFUL"):
                            continue
                    except Exception:
                        continue

                    payload = schemas.ProductOfferCreate(
                        source="accesstrade",
                        source_id=f"promo:{m}:{sid}",
                        merchant=m,
                        title=title,
                        url=link,
                        affiliate_url=aff,
                        image_url=img,
                        price=None,
                        currency="VND",
                        campaign_id=campaign_id,
                        source_type="promotions",
                        # eligible_commission = campaign đang chạy & user APPROVED/SUCCESSFUL (dùng _row đã truy vấn trước đó)
                        eligible_commission=bool(
                            _row
                            and _row.status == "running"
                            and (_row.user_registration_status or "").upper() in ("APPROVED", "SUCCESSFUL")
                        ),
                        affiliate_link_available=bool(aff),
                        extra=json.dumps(extra, ensure_ascii=False),
                    )
                    crud.upsert_offer_by_source(db, payload)
                    imported_offers += 1
            except Exception as e:
                logger.debug("Skip promotion/offer upsert: %s", e)

    return {"ok": True, "promotions": imported_promos, "offers_from_promotions": imported_offers}

"""Legacy provider-specific routes have been removed. Use unified endpoints."""

async def ingest_v2_top_products(
    req: IngestV2TopProductsReq,
    db: Session = Depends(get_db),
):
    from accesstrade_service import fetch_top_products, fetch_active_campaigns, _check_url_alive

    # 0) map merchant -> campaign_id để gắn campaign_id cho offer
    active = await fetch_active_campaigns(db)  # {campaign_id: merchant}
    if not active:
        active = {
            c.campaign_id: c.merchant
            for c in db.query(models.Campaign)
                        .filter(models.Campaign.status == "running")
                        .filter(models.Campaign.user_registration_status.in_(["APPROVED","SUCCESSFUL"]))
                        .all()
            if c.campaign_id and c.merchant
        }
    m_req = (req.merchant or "").lower()
    _alias = {"lazadacps": "lazada", "tikivn": "tiki"}
    m_fetch = _alias.get(m_req, m_req)

    campaign_id = None
    for cid, mm in active.items():
        mm_l = (mm or "").lower()
        if mm_l == m_req or mm_l == m_fetch:
            campaign_id = cid
            break
    if not campaign_id:
        for cid, mm in active.items():
            mm_l = (mm or "").lower()
            if mm_l.endswith(m_req) or f"_{m_req}" in mm_l or (m_req in mm_l):
                campaign_id = cid
                break
    if not campaign_id and m_fetch != m_req:
        for cid, mm in active.items():
            mm_l = (mm or "").lower()
            if mm_l.endswith(m_fetch) or f"_{m_fetch}" in mm_l or (m_fetch in mm_l):
                campaign_id = cid
                break

    # DEFAULT date range: 7 ngày gần nhất nếu không truyền
    if not req.date_from or not req.date_to:
        from datetime import datetime, timedelta, UTC
        _to = datetime.now(UTC).date()
        _from = _to - timedelta(days=7)
        date_from_use = req.date_from or _from.strftime("%Y-%m-%d")
        date_to_use = req.date_to or _to.strftime("%Y-%m-%d")
    else:
        date_from_use = req.date_from
        date_to_use = req.date_to

    page = 1
    imported = 0
    while page <= max(1, req.max_pages):
        items = await fetch_top_products(
            db,
            merchant=m_fetch,  # dùng alias để gọi API ổn định
            date_from=date_from_use,
            date_to=date_to_use,
            page=page,
            limit=req.limit_per_page
        )
        if not items:
            break

        for it in items:
            try:
                title = it.get("name") or "Sản phẩm"
                link = it.get("link") or it.get("url")
                aff = it.get("aff_link")
                img = it.get("image") or it.get("thumb")
                price = it.get("price")
                product_id = it.get("product_id") or it.get("id")

                if not link and not aff:
                    logger.debug("[TOP] skip: no link/aff for %s", title)
                    continue
                # Ưu tiên link gốc cho trường url (affiliate_url sẽ giữ aff)
                url_to_check = link or aff

                # (policy) chỉ check khi bật cờ
                alive = True if not req.check_urls else await _check_url_alive(str(url_to_check or ""))
                if not alive:
                    logger.debug("[TOP] skip: dead url %s", url_to_check)
                    continue

                # idempotent theo product_id nếu có, nếu không theo link
                base_key = str(product_id or url_to_check)
                sid = hashlib.md5(base_key.encode("utf-8")).hexdigest()

                extra = {
                    "source_type": "top_products",
                    "raw": it,
                }
                # Chỉ tạo offer nếu campaign APPROVED (API bỏ qua policy nhưng vẫn yêu cầu APPROVED)
                try:
                    _row = crud.get_campaign_by_cid(db, campaign_id) if campaign_id else None
                    _user = (_row.user_registration_status or "").upper() if _row else ""
                    if not _row or _user not in ("APPROVED", "SUCCESSFUL"):
                        continue
                except Exception:
                    continue

                payload = schemas.ProductOfferCreate(
                    source="accesstrade",
                    source_id=f"top:{req.merchant}:{sid}",
                    merchant=req.merchant,
                    title=title,
                    url=link or aff,
                    affiliate_url=aff,
                    image_url=img,
                    price=price,
                    currency="VND",
                    campaign_id=campaign_id,
                    source_type="top_products",
                    # eligible_commission = campaign đang chạy & user APPROVED/SUCCESSFUL
                    eligible_commission=bool(
                        _row
                        and _row.status == "running"
                        and (_row.user_registration_status or "").upper() in ("APPROVED", "SUCCESSFUL")
                    ),
                    affiliate_link_available=bool(aff),
                    product_id=str(product_id) if product_id is not None else None,
                    extra=json.dumps(extra, ensure_ascii=False),
                )

                crud.upsert_offer_by_source(db, payload)
                imported += 1
            except Exception as e:
                logger.debug("Skip top_product upsert: %s", e)

        page += 1
        sleep_ms = getattr(req, "throttle_ms", 0) or 0
        if sleep_ms:
            await asyncio.sleep(sleep_ms / 1000.0)

    return {"ok": True, "imported": imported, "merchant": req.merchant}

# =============================================
# Unified provider-agnostic ingest endpoints 🌐
# =============================================

class ProviderReq(BaseModel):
    provider: str = "accesstrade"

class CampaignsSyncUnifiedReq(ProviderReq, CampaignsSyncReq):
    pass

class PromotionsUnifiedReq(ProviderReq, IngestV2PromotionsReq):
    pass

class TopProductsUnifiedReq(ProviderReq, IngestV2TopProductsReq):
    pass

class DatafeedsAllUnifiedReq(ProviderReq, IngestAllDatafeedsReq):
    pass

@app.post(
    "/ingest/campaigns/sync",
    tags=["Ingest 🌐"],
    summary="Đồng bộ campaigns (provider-agnostic)",
    description="Hỗ trợ nhiều provider qua tham số `provider`. Hiện hỗ trợ: accesstrade."
)
async def ingest_campaigns_sync_unified(req: CampaignsSyncUnifiedReq, db: Session = Depends(get_db)):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = CampaignsSyncReq(**req.model_dump(exclude={"provider"}))
        return await ingest_v2_campaigns_sync(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

@app.post(
    "/ingest/promotions",
    tags=["Ingest 🌐"],
    summary="Ingest promotions (provider-agnostic)",
    description="Hỗ trợ nhiều provider qua tham số `provider`. Hiện hỗ trợ: accesstrade."
)
async def ingest_promotions_unified(req: PromotionsUnifiedReq, db: Session = Depends(get_db)):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = IngestV2PromotionsReq(**req.model_dump(exclude={"provider"}))
        return await ingest_v2_promotions(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

@app.post(
    "/ingest/top-products",
    tags=["Ingest 🌐"],
    summary="Ingest top products (provider-agnostic)",
    description="Hỗ trợ nhiều provider qua tham số `provider`. Hiện hỗ trợ: accesstrade."
)
async def ingest_top_products_unified(req: TopProductsUnifiedReq, db: Session = Depends(get_db)):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = IngestV2TopProductsReq(**req.model_dump(exclude={"provider"}))
        return await ingest_v2_top_products(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

@app.post(
    "/ingest/datafeeds/all",
    tags=["Ingest 🌐"],
    summary="Ingest datafeeds toàn bộ (provider-agnostic)",
    description="Hỗ trợ nhiều provider qua tham số `provider`. Hiện hỗ trợ: accesstrade."
)
async def ingest_datafeeds_all_unified(req: DatafeedsAllUnifiedReq, db: Session = Depends(get_db)):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = IngestAllDatafeedsReq(**req.model_dump(exclude={"provider"}))
        return await ingest_accesstrade_datafeeds_all(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

"""Legacy provider-specific routes have been removed. Use unified endpoints."""

"""Legacy provider-specific routes have been removed. Use unified endpoints."""

# ================================
# NEW: One-shot ingest ALL sources for APPROVED merchants
# ================================
## Removed deprecated endpoint: POST /ingest/v2/offers/all-approved (per requirements)

@app.put(
    "/offers/{offer_id}",
    tags=["Offers 🛒"],
    summary="Cập nhật thông tin sản phẩm",
    description="Sửa thông tin 1 sản phẩm trong DB theo ID.",
    response_model=schemas.ProductOfferOut
)
def update_offer_api(offer_id: int, data: schemas.ProductOfferUpdate, db: Session = Depends(get_db)):
    obj = crud.update_offer(db, offer_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Offer not found")
    return obj

@app.delete(
    "/offers/{offer_id}",
    tags=["Offers 🛒"],
    summary="Xoá 1 sản phẩm",
    description="Xoá một sản phẩm trong DB theo ID."
)
def delete_offer_api(offer_id: int, db: Session = Depends(get_db)):
    obj = crud.delete_offer(db, offer_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Offer not found")
    return {"ok": True, "deleted_id": offer_id}

# --- API cleanup: xóa sản phẩm có link chết ---
@app.delete(
    "/offers/cleanup/dead",
    tags=["Offers 🛒"],
    summary="Dọn link chết (cleanup)",
    description="Quét toàn bộ sản phẩm trong DB, kiểm tra link sống/chết và **xoá tất cả** link chết."
)
async def cleanup_dead_offers(db: Session = Depends(get_db)):
    offers = crud.list_offers(db, limit=1000)
    removed = 0
    alive_count = 0
    total = len(offers)
    for idx, o in enumerate(offers, start=1):
        if idx % 50 == 0 or idx == total:
            logger.info("Cleanup progress: %d/%d", idx, total)
        alive = await _check_url_alive(o.url)  # chỉ dùng link gốc để tránh click ảo
        if not alive:
            logger.info("Removing dead product via API: id=%s, title='%s'", o.id, o.title)
            db.delete(o)
            removed += 1
        else:
            alive_count += 1
    db.commit()
    logger.info("API cleanup done: %s dead / %s alive / %s scanned", removed, alive_count, total)
    return {"dead": removed, "alive": alive_count, "scanned": total}

@app.post(
    "/scheduler/linkcheck/rotate",
    tags=["Maintenance 🧹"],
    summary="Kiểm tra link sống theo lát cắt 10% và xoay vòng",
    description=(
        "Mỗi lần chạy sẽ kiểm tra ~10% sản phẩm theo điều kiện id % 10 = cursor. "
        "Sau khi chạy xong, cursor tự tăng (modulo 10). "
        "Tuỳ chọn xoá link chết."
    )
)
async def scheduler_linkcheck_rotate(
    delete_dead: bool = False,
    db: Session = Depends(get_db),
):
    from accesstrade_service import _check_url_alive
    flags = crud.get_policy_flags(db)
    cursor = int(flags.get("linkcheck_cursor", 0)) % 10

    from models import ProductOffer
    slice_q = db.query(ProductOffer).filter(text("id % 10 = :cur")).params(cur=cursor)
    offers = slice_q.all()

    total = len(offers)
    removed = 0
    alive_count = 0
    for idx, o in enumerate(offers, start=1):
        if idx % 50 == 0 or idx == total:
            logger.info("[ROTATE] progress: %d/%d (cursor=%d)", idx, total, cursor)
        alive = await _check_url_alive(o.url)
        if alive:
            alive_count += 1
        else:
            if delete_dead:
                db.delete(o)
                removed += 1
    db.commit()

    next_cursor = (cursor + 1) % 10
    crud.set_policy_flag(db, "linkcheck_cursor", next_cursor)

    return {
        "cursor_used": cursor,
        "next_cursor": next_cursor,
        "scanned": total,
        "alive": alive_count,
        "deleted": removed,
    }

# --- API test nhanh: check 1 sản phẩm trong DB ---
from datetime import datetime, UTC

@app.get(
    "/offers/check/{offer_id}",
    tags=["Offers 🛒"],
    summary="Kiểm tra 1 sản phẩm (alive/dead)",
    description="Kiểm tra nhanh trạng thái link của một sản phẩm trong DB theo ID."
)
async def check_offer_status(offer_id: int, db: Session = Depends(get_db)):
    offer = db.query(models.ProductOffer).filter(models.ProductOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    alive = await _check_url_alive(offer.url)  # chỉ check link gốc để tránh click ảo
    return {
        "id": offer.id,
        "title": offer.title,
        "url": offer.url,
        "affiliate_url": offer.affiliate_url,
        "alive": alive,
    "checked_at": datetime.now(UTC).isoformat()
    }

"""Legacy v2 routes have been removed. Use unified endpoints."""

@app.delete(
    "/offers",
    tags=["Offers 🛒"],
    summary="Xoá toàn bộ sản phẩm",
    description="**Cảnh báo:** Xoá tất cả sản phẩm trong DB."
)
def delete_all_offers_api(db: Session = Depends(get_db)):
    count = crud.delete_all_offers(db)
    return {"ok": True, "deleted": count}

# --- Import sản phẩm từ Excel ---
import pandas as pd
@app.post(
    "/offers/import-excel",
    tags=["Offers 🛒"],
    summary="Import sản phẩm từ Excel",
    description="Upload file Excel (.xlsx) chứa danh sách sản phẩm để import vào DB."
)
async def import_offers_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file .xlsx")

    try:
        # Read specifically the 'Products' sheet (if present). Fall back to first sheet.
        try:
            df = pd.read_excel(file.file, sheet_name="Products")
        except Exception:
            # fallback to first sheet
            file.file.seek(0)
            df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đọc file Excel: {e}")

    # BẮT BUỘC: File Excel phải có 2 hàng tiêu đề
    # - Hàng 1: tiêu đề kỹ thuật (tên cột gốc) → được pandas dùng làm df.columns
    # - Hàng 2: tiêu đề tiếng Việt (human-readable) → là dòng đầu tiên của df và sẽ bị bỏ qua khi import
    # Nếu không có hàng 2 này, trả lỗi 400 để đảm bảo thống nhất định dạng trong dự án
    # Map dịch dùng để kiểm tra (hàng 2). Đánh dấu (*) cho cột bắt buộc.
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
    if df.empty:
        raise HTTPException(status_code=400, detail="File Excel trống hoặc không đúng định dạng (thiếu dữ liệu)")
    # Kiểm tra dòng đầu tiên phải là tiêu đề tiếng Việt (chấp nhận có/không dấu (*))
    first = df.iloc[0]
    matches = 0
    total_keys = 0
    for k, v in trans_products.items():
        if k in df.columns:
            total_keys += 1
            try:
                def _norm_header(s: str) -> str:
                    s = str(s or "").strip()
                    # Bỏ "(*)" nếu có để tương thích ngược
                    return s.replace("(*)", "").replace("( * )", "").replace("(*) ", "").strip()
                if _norm_header(str(first[k])) == _norm_header(str(v)):
                    matches += 1
            except Exception:
                pass
    # Yêu cầu: phải khớp ít nhất 1/3 số cột hiện diện (tối thiểu 3 cột) để coi là header tiếng Việt hợp lệ
    threshold = max(3, total_keys // 3)
    if not (total_keys and matches >= threshold):
        raise HTTPException(
            status_code=400,
            detail=(
                "File Excel thiếu hàng tiêu đề tiếng Việt (hàng 2). "
                "Mọi file phải có 2 hàng tiêu đề: hàng 1 là tên cột kỹ thuật, hàng 2 là tên cột tiếng Việt."
            ),
        )
    # Bỏ qua hàng tiêu đề tiếng Việt để tiến hành import dữ liệu
    df = df.iloc[1:].reset_index(drop=True)
    # Chỉ import Excel mới áp dụng policy; mặc định False nếu chưa set
    flags = crud.get_policy_flags(db)
    only_with_commission = bool(flags.get("only_with_commission"))
    check_urls_excel = bool(flags.get("check_urls"))
    from accesstrade_service import _check_url_alive

    imported = 0
    skipped_required = 0
    required_errors: list[dict] = []
    
    def _opt_str(v):
        try:
            import pandas as _pd
            if v is None or (isinstance(v, float) and _pd.isna(v)) or (hasattr(_pd, "isna") and _pd.isna(v)):
                return None
        except Exception:
            if v is None:
                return None
        s = str(v)
        s = s.strip()
        return s if s != "" else None
    for _, row in df.iterrows():
        # Map columns expected in Products sheet coming from API datafeeds
        # Coerce and sanitize typical Excel NaN/empty values
        _price_val = row.get("price")
        try:
            if _price_val in (None, "") or (hasattr(pd, "isna") and pd.isna(_price_val)):
                _price_val = None
            else:
                _price_val = float(_price_val)
        except Exception:
            _price_val = None

        base = {
            "source": "excel",
            "source_type": "excel",
            "source_id": _opt_str(row.get("source_id") or row.get("product_id") or row.get("id") or "") or "",
            "merchant": (_opt_str(row.get("merchant") or row.get("campaign")) or "").lower(),
            "title": _opt_str(row.get("title") or row.get("name") or "") or "",
            "url": _opt_str(row.get("url") or row.get("landing_url") or "") or "",
            "affiliate_url": _opt_str(row.get("affiliate_url") or row.get("aff_link")),
            "image_url": _opt_str(row.get("image_url") or row.get("image") or row.get("thumbnail")),
            "price": _price_val,
            "currency": _opt_str(row.get("currency")) or "VND",
        }

        # REQUIRED validation: merchant, title, price, and at least one of url/affiliate_url
        missing = []
        if not base["merchant"]:
            missing.append("merchant")
        if not base["title"]:
            missing.append("title")
        if base.get("price") in (None,):
            missing.append("price")
        if not (base["url"] or base["affiliate_url"]):
            missing.append("url|affiliate_url")
        if missing:
            skipped_required += 1
            required_errors.append({"row": int(_)+2, "missing": missing})
            continue

        # Auto-generate source_id if missing: prefer URL, then affiliate_url, else hash of title+merchant
        if not base["source_id"]:
            import hashlib
            sid_src = base.get("url") or base.get("affiliate_url")
            if sid_src:
                base["source_id"] = hashlib.md5(str(sid_src).encode("utf-8")).hexdigest()
            else:
                seed = f"{base.get('title')}-{base.get('merchant')}"
                base["source_id"] = hashlib.md5(seed.encode("utf-8")).hexdigest()

        # Ghi campaign_id nếu có trong file Excel
        campaign_id = row.get("campaign_id")
        if pd.notna(campaign_id):
            base["campaign_id"] = str(campaign_id).strip()

        # Gom promotion (if Products sheet contains promotion fields)
        promotion = {
            "name": row.get("promotion_name") or row.get("name"),
            "content": row.get("promotion_content") or row.get("content") or row.get("description"),
            "start_time": row.get("promotion_start_time") or row.get("start_time"),
            "end_time": row.get("promotion_end_time") or row.get("end_time"),
            "coupon": row.get("promotion_coupon") or row.get("coupon"),
            "link": row.get("promotion_link") or row.get("link"),
        }
        promotion = {k: v for k, v in promotion.items() if pd.notna(v)}

        # Gom commission (nếu Products sheet có các cột này)
        commission = {
            "sales_ratio": row.get("sales_ratio") or row.get("commission_sales_ratio"),
            "sales_price": row.get("sales_price") or row.get("commission_sales_price"),
            "reward_type": row.get("reward_type") or row.get("commission_reward_type"),
            "target_month": row.get("target_month") or row.get("commission_target_month"),
        }
        commission = {k: v for k, v in commission.items() if pd.notna(v)}

        # Gộp vào extra (không còn xuất extra_raw trong Excel, nhưng DB vẫn giữ extra nếu có)
        extra = {}
        if promotion:
            extra["promotion"] = promotion
        if commission:
            extra["commission"] = commission
        base["extra"] = json.dumps(extra, ensure_ascii=False)
        
        if only_with_commission:
            # Xác định đủ điều kiện: có cột eligible_commission=True hoặc có ít nhất một trường commission hợp lệ
            eligible_flag = False
            try:
                eligible_flag = bool(str(row.get("eligible_commission") or "").strip().lower() in ("true","1","yes"))
            except Exception:
                eligible_flag = False

            has_comm = False
            try:
                _comm = commission if isinstance(commission, dict) else {}
                for _k in ("sales_ratio","sales_price","reward_type","target_month"):
                    v = _comm.get(_k)
                    if v not in (None, "", float("nan")):
                        has_comm = True
                        break
            except Exception:
                has_comm = False

            if not (eligible_flag or has_comm):
                continue

        # Auto-convert url -> affiliate_url if missing and a template is available
        if (not base.get("affiliate_url")) and base.get("url") and base.get("merchant"):
            try:
                tpl = crud.get_affiliate_template(db, base["merchant"], "accesstrade")
                if tpl:
                    merged_params: dict[str, str] = {}
                    if tpl.default_params:
                        merged_params.update(tpl.default_params)
                    # apply template: replace {target} and any params
                    aff = tpl.template.replace("{target}", quote_plus(base["url"]))
                    for k, v in merged_params.items():
                        aff = aff.replace("{"+k+"}", str(v))
                    base["affiliate_url"] = aff
            except Exception:
                pass

        # Set affiliate_link_available by presence of affiliate_url
        base["affiliate_link_available"] = bool(base.get("affiliate_url"))

        data = schemas.ProductOfferCreate(**base)

        if not data.url or not data.source_id:
            continue

        # Nếu bật check link cho Excel thì chỉ ghi khi url sống
        if check_urls_excel:
            try:
                if not await _check_url_alive(data.url or ""):
                    continue
            except Exception:
                continue

        crud.upsert_offer_by_source(db, data)
        imported += 1

    if required_errors:
        # Trả thông tin thống kê để người dùng biết lý do bỏ qua
        return {
            "ok": True,
            "imported": imported,
            "skipped_required": skipped_required,
            "errors": required_errors[:50]  # tránh trả quá dài
        }
    return {"ok": True, "imported": imported}

# --- Export sản phẩm từ DB ra file Excel ---
@app.get(
    "/offers/export-excel",
    tags=["Offers 🛒"],
    summary="Xuất Excel chuyên biệt (Products/Campaigns/Commissions/Promotions)",
    description=(
        "Xuất Excel gồm 4 sheet độc lập. Products chỉ gồm sản phẩm từ API (datafeeds/top_products) và có cột source_type; "
        "Campaigns chỉ các campaign đã APPROVED/SUCCESSFUL; Commissions/PROMotions độc lập, không phụ thuộc sản phẩm."
    )
)
def export_offers_excel(
    merchant: str | None = None,
    title: str | None = None,
    skip: int = 0,
    limit: int = 0,  # nếu =0 thì xuất toàn bộ
    db: Session = Depends(get_db)
):
    import os, json
    import pandas as pd
    from collections import defaultdict

    # 1) Products: chỉ lấy offers từ nguồn API (datafeeds/top_products)
    q_offers = db.query(models.ProductOffer).filter(
        models.ProductOffer.source_type.in_(["datafeeds", "top_products", "promotions", "manual", "excel"])  # mở rộng theo yêu cầu
    )
    if merchant:
        q_offers = q_offers.filter(models.ProductOffer.merchant == merchant.lower())
    if title:
        q_offers = q_offers.filter(models.ProductOffer.title.ilike(f"%{title.lower()}%"))
    if skip:
        q_offers = q_offers.offset(skip)
    if limit:
        q_offers = q_offers.limit(limit)
    offers = q_offers.all()

    # 2) Campaigns: độc lập, chỉ APPROVED/SUCCESSFUL
    campaigns_all = db.query(models.Campaign).filter(
        (models.Campaign.user_registration_status.in_(["APPROVED", "SUCCESSFUL"]))
    ).all()
    campaign_map = {c.campaign_id: c for c in campaigns_all}

    # 3) Commissions: độc lập, lấy từ bảng CommissionPolicy
    commissions_all = db.query(models.CommissionPolicy).all()

    # 4) Promotions: độc lập, lấy từ bảng Promotion (kèm merchant từ campaign nếu có)
    promotions_all = db.query(models.Promotion).all()

    # 5) Đọc JSONL logs để enrich Campaign fields (giống trước đây)
    LOG_DIR = os.getenv("API_LOG_DIR", "./logs")
    def _read_jsonl(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        yield json.loads(line)
                    except Exception:
                        pass
        except FileNotFoundError:
            return

    CAMP_LAST = {}
    for rec in _read_jsonl(os.path.join(LOG_DIR, "campaign_detail.jsonl")) or []:
        cid = str(rec.get("campaign_id") or "")
        if cid:
            CAMP_LAST[cid] = rec

    def _campaign_field_from_log(cid: str, field_name: str):
        rec = CAMP_LAST.get(str(cid) if cid is not None else "")
        if not rec:
            return "API_MISSING"
        if field_name == "end_time" and rec.get("has_end_time") is False:
            return "API_EMPTY"
        if field_name == "user_registration_status" and rec.get("has_user_status") is False:
            return "API_EMPTY"
        if rec.get("empty") is True:
            return "API_EMPTY"
        raw = rec.get("raw")
        if isinstance(raw, dict):
            data = None
            d = raw.get("data")
            if isinstance(d, dict):
                data = d
            elif isinstance(d, list) and d:
                data = d[0]
            if isinstance(data, dict):
                if field_name == "user_registration_status":
                    for k in ("user_registration_status", "publisher_status", "user_status"):
                        v = data.get(k, None)
                        if v not in (None, "", []):
                            return v
                    return "API_EMPTY"
                v = data.get(field_name, None)
                return v if v not in (None, "", []) else "API_EMPTY"
        return "API_MISSING"

    # ---------------------------
    # Build Products rows
    # ---------------------------
    df_products_rows = []
    for o in offers:
        extra = {}
        if o.extra:
            try:
                extra = json.loads(o.extra)
            except Exception:
                extra = {}
        df_products_rows.append({
            "id": o.id,
            "source": o.source,
            "source_id": o.source_id,
            "source_type": o.source_type,
            "merchant": o.merchant,
            "title": o.title,
            "url": o.url,
            "affiliate_url": o.affiliate_url,
            "image_url": o.image_url,
            "price": o.price,
            "currency": o.currency,
            "campaign_id": o.campaign_id,
            "product_id": json.dumps(extra.get("product_id")) if False else (extra.get("product_id") or getattr(o, "product_id", None)),
            "affiliate_link_available": extra.get("affiliate_link_available"),
            "domain": extra.get("domain"),
            "sku": extra.get("sku"),
            "discount": extra.get("discount"),
            "discount_amount": extra.get("discount_amount"),
            "discount_rate": extra.get("discount_rate"),
            "status_discount": extra.get("status_discount"),
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
            "desc": extra.get("desc"),
            "cate": extra.get("cate"),
            "shop_name": extra.get("shop_name"),
            "update_time_raw": extra.get("update_time_raw") or extra.get("update_time"),
        })

    # ---------------------------
    # Build Campaigns rows (independent)
    # ---------------------------
    df_campaigns_rows = []
    for c in campaigns_all:
        cid = c.campaign_id
        df_campaigns_rows.append({
            "campaign_id": c.campaign_id,
            "merchant": c.merchant,
            "campaign_name": c.name,
            "approval_type": c.approval,
            "user_status": c.user_registration_status,
            "status": c.status or _campaign_field_from_log(cid, "status"),
            "start_time": c.start_time,
            "end_time": c.end_time if c.end_time else _campaign_field_from_log(cid, "end_time"),
            "category": _campaign_field_from_log(cid, "category"),
            "conversion_policy": _campaign_field_from_log(cid, "conversion_policy"),
            "cookie_duration": _campaign_field_from_log(cid, "cookie_duration"),
            "cookie_policy": _campaign_field_from_log(cid, "cookie_policy"),
            "description": _campaign_field_from_log(cid, "description"),
            "scope": _campaign_field_from_log(cid, "scope"),
            "sub_category": _campaign_field_from_log(cid, "sub_category"),
            "type": _campaign_field_from_log(cid, "type"),
            "campaign_url": _campaign_field_from_log(cid, "url"),
        })

    # ---------------------------
    # Build Commissions rows (independent)
    # ---------------------------
    df_commissions_rows = []
    for cp in commissions_all:
        df_commissions_rows.append({
            "campaign_id": cp.campaign_id,
            "reward_type": cp.reward_type,
            "sales_ratio": cp.sales_ratio,
            "sales_price": cp.sales_price,
            "target_month": cp.target_month,
        })

    # ---------------------------
    # Build Promotions rows (independent + merchant)
    # ---------------------------
    df_promotions_rows = []
    for pr in promotions_all:
        m = None
        if pr.campaign_id and pr.campaign_id in campaign_map:
            m = campaign_map[pr.campaign_id].merchant
        df_promotions_rows.append({
            "campaign_id": pr.campaign_id,
            "merchant": m,
            "name": pr.name,
            "content": pr.content,
            "start_time": pr.start_time,
            "end_time": pr.end_time,
            "coupon": pr.coupon,
            "link": pr.link,
        })

    # DataFrames
    df_products = pd.DataFrame(df_products_rows)
    df_campaigns = pd.DataFrame(df_campaigns_rows)
    df_commissions = pd.DataFrame(df_commissions_rows)
    df_promotions = pd.DataFrame(df_promotions_rows)

    # Header translations (Vietnamese) — add (*) markers for required in Products
    trans_products = {
        "id": "Mã ID", "source": "Nguồn", "source_id": "Mã nguồn", "source_type": "Loại nguồn",
        "merchant": "Nhà bán (*)", "title": "Tên sản phẩm (*)", "url": "Link gốc", "affiliate_url": "Link tiếp thị",
        "image_url": "Ảnh sản phẩm", "price": "Giá (*)", "currency": "Tiền tệ",
        "campaign_id": "Chiến dịch", "product_id": "Mã sản phẩm nguồn", "affiliate_link_available": "Có affiliate?",
        "domain": "Tên miền", "sku": "SKU", "discount": "Giá KM", "discount_amount": "Mức giảm",
        "discount_rate": "Tỷ lệ giảm (%)", "status_discount": "Có khuyến mãi?",
        "updated_at": "Ngày cập nhật", "desc": "Mô tả chi tiết",
        "cate": "Danh mục", "shop_name": "Tên cửa hàng", "update_time_raw": "Thời gian cập nhật từ nguồn",
    }
    trans_campaigns = {
        "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "campaign_name": "Tên chiến dịch",
        "approval_type": "Approval", "user_status": "Trạng thái của tôi", "status": "Tình trạng",
        "start_time": "Bắt đầu", "end_time": "Kết thúc",
        "category": "Danh mục chính", "conversion_policy": "Chính sách chuyển đổi",
        "cookie_duration": "Hiệu lực cookie (giây)", "cookie_policy": "Chính sách cookie",
        "description": "Mô tả", "scope": "Phạm vi", "sub_category": "Danh mục phụ",
        "type": "Loại", "campaign_url": "URL chiến dịch",
    }
    trans_commissions = {
        "campaign_id": "Mã chiến dịch", "reward_type": "Kiểu thưởng", "sales_ratio": "Tỷ lệ (%)",
        "sales_price": "Hoa hồng cố định", "target_month": "Tháng áp dụng",
    }
    trans_promotions = {
        "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "name": "Tên khuyến mãi", "content": "Nội dung",
        "start_time": "Bắt đầu KM", "end_time": "Kết thúc KM", "coupon": "Mã giảm", "link": "Link khuyến mãi",
    }

    def _with_header(df, trans):
        # Luôn tạo một hàng tiêu đề TV làm hàng đầu tiên
        # Nếu df đang rỗng, tạo hàng đầu với toàn bộ cột theo trans
        if df.empty:
            header = {c: trans.get(c, c) for c in trans.keys()}
            return pd.DataFrame([header])
        header = {c: trans.get(c, c) for c in df.columns}
        return pd.concat([pd.DataFrame([header]), df], ignore_index=True)

    df_products = _with_header(df_products, trans_products)
    df_campaigns = _with_header(df_campaigns, trans_campaigns)
    df_commissions = _with_header(df_commissions, trans_commissions)
    df_promotions = _with_header(df_promotions, trans_promotions)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Nếu DataFrame rỗng, vẫn cần tạo cột theo trans để sheet có header
        def _ensure_cols(df, trans_map):
            cols = list(trans_map.keys())
            if df.empty:
                return pd.DataFrame(columns=cols)
            # Reorder/align columns to match trans_map keys; include missing columns as empty
            for c in cols:
                if c not in df.columns:
                    df[c] = None
            return df[cols]

        df_products = _ensure_cols(df_products, trans_products)
        df_campaigns = _ensure_cols(df_campaigns, trans_campaigns)
        df_commissions = _ensure_cols(df_commissions, trans_commissions)
        df_promotions = _ensure_cols(df_promotions, trans_promotions)

        df_products.to_excel(writer, sheet_name="Products", index=False)
        df_campaigns.to_excel(writer, sheet_name="Campaigns", index=False)
        df_commissions.to_excel(writer, sheet_name="Commissions", index=False)
        df_promotions.to_excel(writer, sheet_name="Promotions", index=False)

        # Style the Vietnamese header row (row index 1) as bold + italic
        workbook = writer.book
        fmt_vi_header = workbook.add_format({"bold": True, "italic": True})
        for sheet_name in ("Products", "Campaigns", "Commissions", "Promotions"):
            ws = writer.sheets.get(sheet_name)
            if ws is not None:
                try:
                    ws.set_row(1, None, fmt_vi_header)
                except Exception:
                    pass
    output.seek(0)

    filename = f"offers_export_{int(time.time())}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@app.get(
    "/offers/export-template",
    tags=["Offers 🛒"],
    summary="Tải template Excel (4 sheet)",
    description="Tải file mẫu có sẵn 4 sheet với header 2 hàng; đánh dấu (*) ở các cột bắt buộc của Products."
)
def export_excel_template():
    import pandas as pd
    # Tạo DataFrames rỗng với đúng cột và chèn hàng tiêu đề TV
    trans_products = {
        "id": "Mã ID", "source": "Nguồn", "source_id": "Mã nguồn", "source_type": "Loại nguồn",
        "merchant": "Nhà bán (*)", "title": "Tên sản phẩm (*)", "url": "Link gốc", "affiliate_url": "Link tiếp thị",
        "image_url": "Ảnh sản phẩm", "price": "Giá (*)", "currency": "Tiền tệ",
        "campaign_id": "Chiến dịch", "product_id": "Mã sản phẩm nguồn", "affiliate_link_available": "Có affiliate?",
        "domain": "Tên miền", "sku": "SKU", "discount": "Giá KM", "discount_amount": "Mức giảm",
        "discount_rate": "Tỷ lệ giảm (%)", "status_discount": "Có khuyến mãi?",
        "updated_at": "Ngày cập nhật", "desc": "Mô tả chi tiết",
        "cate": "Danh mục", "shop_name": "Tên cửa hàng", "update_time_raw": "Thời gian cập nhật từ nguồn",
    }
    trans_campaigns = {
        "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "campaign_name": "Tên chiến dịch",
        "approval_type": "Approval", "user_status": "Trạng thái của tôi", "status": "Tình trạng",
        "start_time": "Bắt đầu", "end_time": "Kết thúc",
        "category": "Danh mục chính", "conversion_policy": "Chính sách chuyển đổi",
        "cookie_duration": "Hiệu lực cookie (giây)", "cookie_policy": "Chính sách cookie",
        "description": "Mô tả", "scope": "Phạm vi", "sub_category": "Danh mục phụ",
        "type": "Loại", "campaign_url": "URL chiến dịch",
    }
    trans_commissions = {
        "campaign_id": "Mã chiến dịch", "reward_type": "Kiểu thưởng", "sales_ratio": "Tỷ lệ (%)",
        "sales_price": "Hoa hồng cố định", "target_month": "Tháng áp dụng",
    }
    trans_promotions = {
        "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "name": "Tên khuyến mãi", "content": "Nội dung",
        "start_time": "Bắt đầu KM", "end_time": "Kết thúc KM", "coupon": "Mã giảm", "link": "Link khuyến mãi",
    }

    def _df_with_header(cols_map):
        df = pd.DataFrame(columns=list(cols_map.keys()))
        header = {c: cols_map.get(c, c) for c in df.columns}
        return pd.concat([pd.DataFrame([header]), df], ignore_index=True)

    df_products = _df_with_header(trans_products)
    df_campaigns = _df_with_header(trans_campaigns)
    df_commissions = _df_with_header(trans_commissions)
    df_promotions = _df_with_header(trans_promotions)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_products.to_excel(writer, sheet_name="Products", index=False)
        df_campaigns.to_excel(writer, sheet_name="Campaigns", index=False)
        df_commissions.to_excel(writer, sheet_name="Commissions", index=False)
        df_promotions.to_excel(writer, sheet_name="Promotions", index=False)

        # Style the Vietnamese header row (row index 1) as bold + italic
        workbook = writer.book
        fmt_vi_header = workbook.add_format({"bold": True, "italic": True})
        for sheet_name in ("Products", "Campaigns", "Commissions", "Promotions"):
            ws = writer.sheets.get(sheet_name)
            if ws is not None:
                try:
                    ws.set_row(1, None, fmt_vi_header)
                except Exception:
                    pass
    output.seek(0)

    filename = f"offers_template_{int(time.time())}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )
@app.get(
    "/alerts/campaigns-registration",
    tags=["Campaigns 📢"],
    summary="Cảnh báo đăng ký chiến dịch",
    description="Liệt kê các campaign đang chạy và đã có sản phẩm trong DB, nhưng user chưa ở trạng thái APPROVED (chưa đăng ký hoặc đang chờ duyệt)."
)
def campaigns_registration_alerts(db: Session = Depends(get_db)):
    return crud.campaigns_need_registration_alerts(db)
