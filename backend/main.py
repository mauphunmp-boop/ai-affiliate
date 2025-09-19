# backend/main.py
import logging, traceback
import os, hmac, hashlib, base64, json, time, asyncio
from urllib.parse import urlparse, quote_plus
from typing import Optional, Dict, List, Any

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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

# ---------------- Logging ----------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("affiliate_api")

# Hạ mức log của httpx/httpcore/uvicorn để tránh spam dài dòng
for noisy in ("httpx", "httpcore", "uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ---------------- DB init ----------------
Base.metadata.create_all(bind=engine)

# --- Default ingest policy on startup ---
# Mặc định:
# - only_with_commission=false  (Excel mới áp dụng)
# - check_urls=false            (tắt check link khi ingest qua API/Excel)
# - linkcheck_cursor=0          (scheduler quét luân phiên 10 "lát cắt")
try:
    _db = SessionLocal()
    existing = crud.get_api_config(_db, "ingest_policy")
    if not existing:
        crud.create_api_config(_db, schemas.APIConfigCreate(
            name="ingest_policy", base_url="-", api_key="-",
            model="only_with_commission=false;check_urls=false;linkcheck_cursor=0"
        ))
    else:
        model_str = (existing.model or "").lower()
        if "check_urls=" not in model_str or "linkcheck_cursor=" not in model_str:
            # Bổ sung phần còn thiếu, không phá giá trị cũ
            parts = [model_str] if model_str else []
            if "check_urls=" not in model_str:
                parts.append("check_urls=false")
            if "linkcheck_cursor=" not in model_str:
                parts.append("linkcheck_cursor=0")
            updated = ";".join([p for p in parts if p])
            crud.upsert_api_config_by_name(_db, schemas.APIConfigCreate(
                name="ingest_policy", base_url=existing.base_url or "-",
                api_key=existing.api_key or "-", model=updated
            ))
finally:
    try:
        _db.close()
    except Exception:
        pass

# --- DB MIGRATION V2 (thêm cột & bảng phục vụ hybrid 3 lớp) ---
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE product_offers ADD COLUMN IF NOT EXISTS approval_status VARCHAR"))
        conn.execute(text("ALTER TABLE product_offers ADD COLUMN IF NOT EXISTS eligible_commission BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE product_offers ADD COLUMN IF NOT EXISTS source_type VARCHAR"))
        conn.execute(text("ALTER TABLE product_offers ADD COLUMN IF NOT EXISTS affiliate_link_available BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE product_offers ADD COLUMN IF NOT EXISTS product_id VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_offers_approval_status ON product_offers (approval_status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_offers_campaign_id ON product_offers (campaign_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_offers_product_id ON product_offers (product_id)"))
        # NEW: unique index chống trùng (source, source_id)
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_product_offers_source_source_id ON product_offers (source, source_id)"))
except Exception as e:
    logger.error("DB migration V2 failed: %s", e)

# ---------------- FastAPI App (UI đẹp & có nhóm) ----------------
app = FastAPI(
    title="AI Affiliate Advisor API",
    version="1.0.0",
    description=(
        "📘 **Tài liệu API hệ thống Affiliate**\n\n"
        "Quản lý link tiếp thị liên kết, ingest sản phẩm, kiểm tra alive/dead, "
        "và sử dụng AI để tư vấn sản phẩm.\n\n"
        "Các endpoint được nhóm theo **tags** để dễ sử dụng."
    ),
    openapi_tags=[
    {"name": "System 🛠️", "description": "Kiểm tra trạng thái hệ thống & sức khỏe dịch vụ."},
    {"name": "Links 🔗", "description": "CRUD link tiếp thị (hiển thị, thêm, sửa, xoá)."},
    {"name": "API Configs ⚙️", "description": "Quản lý cấu hình AI/API (tạo, danh sách, cập nhật, xoá)."},
    {"name": "Affiliate 🎯", "description": "Mẫu deeplink, chuyển link gốc → deeplink & shortlink, redirect an toàn."},
    {"name": "Offers 🛒", "description": "Quản lý sản phẩm (ingest từ Accesstrade, danh sách, cleanup link chết, kiểm tra 1 sản phẩm)."},
    {"name": "AI 🤖", "description": "Gợi ý/Trả lời của AI dựa trên các sản phẩm đã ingest trong DB."},
    {"name": "Campaigns 📢", "description": "Cảnh báo đăng ký chiến dịch & tình trạng user."}
    ],
    swagger_ui_parameters={
        "docExpansion": "list",               # Mở theo nhóm, gọn gàng
        "defaultModelsExpandDepth": -1,       # Ẩn schema mặc định cho đỡ rối
        "displayRequestDuration": True,       # Hiện thời gian thực thi
        "deepLinking": True,                  # Cho phép deep link tới từng API
        "filter": True                        # Ô lọc endpoint nhanh
    }
)

# --- Scheduler để cleanup + ingest datafeeds hằng ngày ---
from fastapi_utils.tasks import repeat_every

@app.on_event("startup")
@repeat_every(seconds=86400, wait_first=True)  # chạy mỗi ngày, chờ 1 ngày mới chạy lần đầu
async def scheduled_ingest_accesstrade() -> None:
    db = SessionLocal()
    try:
        # --- Cleanup link chết: chuyển sang xoay vòng 10%/lượt ---
        try:
            # mỗi ngày kiểm 1 "lát cắt": id % 10 = cursor; xong tự tăng cursor (mod 10)
            res = await scheduler_linkcheck_rotate(delete_dead=True, db=db)
            logger.info("[ROTATE] daily linkcheck: %s", res)
        except Exception as e:
            logger.error("[ROTATE] daily linkcheck failed: %s", e)

        # --- Lấy campaign đang chạy ---
        from accesstrade_service import fetch_active_campaigns
        active_campaigns = await fetch_active_campaigns(db)
        logger.info("Fetched %d active campaigns", len(active_campaigns))

        # Tạo map merchant -> campaign_id từ danh sách active để suy ngược
        merchant_campaign_map = {v: k for k, v in active_campaigns.items()}

        # --- Ingest khuyến mãi & top products theo kiến trúc mới ---
        try:
            await ingest_v2_promotions(IngestV2PromotionsReq(merchant=None, create_offers=True), db)
            approved_merchants = list_approved_merchants_api(db)  # danh sách merchant đã APPROVED & running
            for m in approved_merchants:
                await ingest_v2_top_products(
                    IngestV2TopProductsReq(merchant=m, limit_per_page=100, max_pages=1, throttle_ms=0), db
                )
        except Exception as e:
            logger.error("Scheduled v2 ingest (promotions/top-products) failed: %s", e)

        # --- Ingest datafeeds full (tùy chọn, chạy sau cùng) ---
        try:
            res = await ingest_accesstrade_datafeeds_all(
                IngestAllDatafeedsReq(limit_per_page=100, max_pages=2000, throttle_ms=200),
                db
            )
            logger.info("Scheduled full ingest done: %s", res)
        except Exception as e:
            logger.error("Scheduled full ingest failed: %s", e)

    except Exception as e:
        logger.error("Scheduled ingest failed: %s", e)
    finally:
        db.close()

# ---------------- CORS ----------------
origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DB dependency ----------------
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
    logger.error("Unhandled exception: %s\n%s", exc, tb)
    return JSONResponse(status_code=500, content={"error": str(exc), "traceback": tb})

# ---------------- System ----------------
@app.get(
    "/",
    tags=["System 🛠️"],
    summary="Chào mừng",
    description="Thông báo API đang chạy và hướng dẫn truy cập tài liệu tại **/docs**."
)
def root():
    return {"message": "Affiliate API is running. See /docs"}

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
    - params: có thể truyền campaign/domain nếu muốn lọc (vd: {"campaign":"shopee","domain":"shopee.vn"})
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
    limit_per_page: int = 100
    max_pages: int = 200
    throttle_ms: int = 0

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

    # --- Provider: Accesstrade (đã hỗ trợ) ---
    if provider == "accesstrade":
        from accesstrade_service import fetch_active_campaigns, fetch_campaign_detail
        active_campaigns = await fetch_active_campaigns(db)
        logger.info("Fetched %d active campaigns", len(active_campaigns))
        merchant_campaign_map = {v: k for k, v in active_campaigns.items()}

        items = await fetch_products(db, req.path, req.params or {})
        if not items:
            return {"ok": True, "imported": 0}

        # API ingest bỏ qua policy; policy chỉ áp dụng cho import Excel
        only_with_commission = False

        imported = 0
        for it in items:
            camp_id = str(it.get("campaign_id") or it.get("campaign_id_str") or "").strip()
            merchant = str(it.get("merchant") or it.get("campaign") or "").lower().strip()
            # Chuẩn hoá merchant để khớp với merchant_campaign_map (vd: "shopee.vn" -> "shopee")
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

            # Chỉ ingest nếu campaign_id thuộc campaign đang chạy
            if not camp_id or camp_id not in active_campaigns:
                logger.info("Skip product vì campaign_id=%s không active [manual ingest] (merchant=%s)", camp_id, merchant_norm)
                continue
            
            # YÊU CẦU: user APPROVED (API ingest bỏ qua policy, nhưng vẫn cần APPROVED)
            try:
                _row = crud.get_campaign_by_cid(db, camp_id)
                if not _row or (_row.user_registration_status or "").upper() != "APPROVED":
                    logger.info("Skip product vì campaign_id=%s chưa APPROVED [manual ingest]", camp_id)
                    continue
            except Exception:
                continue

            # 1) Commission hiện chưa dùng để lọc/ghi riêng
            commission_data = None

            # 2) Promotions theo merchant (vừa enrich extra, vừa ghi bảng promotions)
            promotions_data = await fetch_promotions(db, merchant_norm) if merchant_norm else []
            if promotions_data:
                # NEW: upsert promotions theo campaign_id
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

            # 3) Campaign detail (để có approval/status/time & trạng thái đăng ký user)
            try:
                camp = await fetch_campaign_detail(db, camp_id)
                if camp:
                    status_val = camp.get("status")
                    approval_val = camp.get("approval")
                    # KHÔNG default "unregistered" khi API không trả user_status
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

            # 4) Commission policies (ghi bảng commission_policies) + eligibility fallback
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

                if only_with_commission:
                    # Fallback giống /ingest/accesstrade/datafeeds/all:
                    # nếu campaign đang running + user APPROVED thì coi như "có commission"
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
                        logger.info(
                            "Skip product vì campaign_id=%s không có commission policy và chưa đủ điều kiện (policy.only_with_commission=true)",
                            camp_id
                        )
                        continue

            except Exception as e:
                logger.debug("Skip commission upsert: %s", e)

            # 5) Map + enrich extra trên product_offers
            commission_data = policies  # dùng chính policies vừa fetch
            data = map_at_product_to_offer(it, commission=commission_data, promotion=promotions_data)
            if not data.get("url") or not data.get("source_id"):
                continue

            # Bổ sung campaign_id rõ ràng
            data["campaign_id"] = camp_id

            # NEW: gắn loại nguồn + trạng thái phê duyệt & eligibility
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

            # 6) Chỉ check link gốc để tránh click ảo
            if not await _check_url_alive(data["url"]):
                logger.info("Skip dead product [manual ingest]: title='%s'", data.get("title"))
                continue

            # 7) Ghi/Update product_offers
            crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(**data))
            imported += 1

        return {"ok": True, "imported": imported}

    raise HTTPException(status_code=400, detail=f"Provider '{provider}' hiện chưa được hỗ trợ")

@app.post(
    "/ingest/accesstrade/datafeeds/all",
    tags=["Offers 🛒"],
    summary="Ingest TOÀN BỘ datafeeds (tự phân trang)",
    description=(
        "Gọi Accesstrade /v1/datafeeds nhiều lần (page=1..N) cho đến khi hết dữ liệu, "
        "không yêu cầu client truyền page/limit."
    )
)
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
    merchant_campaign_map = {v: k for k, v in active_campaigns.items()}  # {merchant: campaign_id}

    # chính sách ingest (API bỏ qua policy; policy chỉ áp dụng cho import Excel)
    only_with_commission = False

    # 2) Cache promotions theo merchant để tránh gọi trùng
    promotion_cache: dict[str, list[dict]] = {}

    # NEW: Cache commission theo campaign_id để tránh spam API (fix NameError)
    cache_commissions: dict[str, list[dict]] = {}

    # 3) Tham số gọi API datafeeds
    base_params = dict(req.params or {})
    base_params.pop("page", None)   # client không cần truyền
    base_params.pop("limit", None)  # client không cần truyền

    imported = 0
    total_pages = 0
    page = 1

    while page <= max(1, req.max_pages):
        params = dict(base_params)
        params["page"]  = str(page)
        params["limit"] = str(req.limit_per_page)

        items = await fetch_products(db, "/v1/datafeeds", params)
        if not items:
            break
        total_pages += 1

        for it in items:
            # Lấy campaign/merchant từ record
            camp_id = str(it.get("campaign_id") or it.get("campaign_id_str") or "").strip()
            merchant = str(it.get("merchant") or it.get("campaign") or "").lower().strip()
            _base = merchant.split(".")[0] if "." in merchant else merchant
            _alias = {"lazadacps": "lazada", "tikivn": "tiki"}
            merchant_norm = _alias.get(_base, _base)

            # Fallback campaign_id theo merchant nếu thiếu
            if not camp_id:
                # exact
                if merchant_norm in merchant_campaign_map:
                    camp_id = merchant_campaign_map[merchant_norm]
                else:
                    # suffix match kiểu "xxx_shopee" hoặc "..._shopee"
                    for m_key, cid in merchant_campaign_map.items():
                        if m_key.endswith(merchant_norm) or f"_{merchant_norm}" in m_key:
                            camp_id = cid
                            break
                    if not camp_id:
                        # contains match (vd: 'lazada' ⊂ 'lazadacps')
                        for m_key, cid in merchant_campaign_map.items():
                            if merchant_norm in m_key:
                                camp_id = cid
                                break

            # Bỏ qua nếu campaign không active
            if not camp_id or camp_id not in active_campaigns:
                continue
            # YÊU CẦU: user APPROVED (API ingest bỏ qua policy, nhưng vẫn cần APPROVED)
            try:
                _row = crud.get_campaign_by_cid(db, camp_id)
                if not _row or (_row.user_registration_status or "").upper() != "APPROVED":
                    continue
            except Exception:
                continue

            # Lấy commission theo camp_id (cache để tránh spam API)
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
            # Bật policy: chỉ ingest khi có commission (giả định mới: campaign đang chạy + user APPROVED được xem là có commission)
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

            # Chuẩn hoá record → ProductOfferCreate (nhúng commission để extra có dữ liệu)
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

            # Link gốc phải "sống"
            if not await _check_url_alive(data["url"]):
                continue

            # Ghi/Update product_offers
            crud.upsert_offer_by_source(db, schemas.ProductOfferCreate(**data))
            imported += 1

        # Early stop nếu trang hiện tại ít hơn limit -> có thể là trang cuối
        if len(items) < (req.limit_per_page or 100):
            total_pages += 1
            break

        # Tiếp trang
        page += 1
        total_pages += 1
        sleep_ms = getattr(req, "throttle_ms", 0) or 0
        if sleep_ms:
            await asyncio.sleep(sleep_ms / 1000.0)

    return {"ok": True, "imported": imported, "pages": total_pages}

@app.post(
    "/ingest/v2/campaigns/sync",
    tags=["Campaigns 📢"],
    summary="Đồng bộ danh sách campaigns từ Accesstrade",
    description="Lưu/ cập nhật campaigns vào DB để làm chuẩn eligibility và theo dõi."
)
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

@app.post(
    "/ingest/v2/promotions",
    tags=["Offers 🛒"],
    summary="Ingest khuyến mãi (offers_informations) cho merchant đã duyệt",
    description="Đồng bộ promotions và (tùy chọn) map thành offers tối thiểu để hiển thị."
)
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
                    alive = True if not req.check_urls else await _check_url_alive(url_to_check)
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

@app.post(
    "/ingest/v2/top-products",
    tags=["Offers 🛒"],
    summary="Ingest Top Products (bán chạy) theo merchant & khoảng ngày",
    description="Đồng bộ top_products theo trang (1..N), map thành offers tối thiểu."
)
async def ingest_v2_top_products(
    req: IngestV2TopProductsReq,
    db: Session = Depends(get_db),
):
    from accesstrade_service import fetch_top_products, fetch_active_campaigns, _check_url_alive

    # 0) map merchant -> campaign_id để gắn campaign_id cho offer
    active = await fetch_active_campaigns(db)  # {campaign_id: merchant}
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
        from datetime import datetime, timedelta
        _to = datetime.utcnow().date()
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
                alive = True if not req.check_urls else await _check_url_alive(url_to_check)
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

# ================================
# NEW: One-shot ingest ALL sources for APPROVED merchants
# ================================
class IngestAllApprovedReq(BaseModel):
    # Bật/tắt từng nguồn
    include_promotions: bool = True
    include_top_products: bool = True
    include_datafeeds: bool = True

    # Tham số cho top_products
    top_date_from: str | None = None
    top_date_to: str | None = None
    top_limit_per_page: int = 100
    top_max_pages: int = 2

    # Tham số cho datafeeds
    datafeeds_limit_per_page: int = 100
    datafeeds_max_pages: int = 5

    # Nghỉ giữa các lần gọi (ms) để tôn trọng rate-limit
    throttle_ms: int = 200


@app.post(
    "/ingest/v2/offers/all-approved",
    tags=["Offers 🛒"],
    summary="Ingest tất cả sản phẩm từ approved merchants (promotions + top_products + datafeeds)",
    description=(
        "Một lệnh duy nhất:\n"
        "1) Promotions (offers_informations) theo từng merchant đã APPROVED (tạo offer tối thiểu nếu có link sống)\n"
        "2) Top products theo từng merchant đã APPROVED (tự phân trang theo limit/max_pages)\n"
        "3) Datafeeds full (tự phân trang 1..N)\n"
        "— Tuân thủ doc Accesstrade và logic APPROVED đang có."
    )
)
async def ingest_v2_offers_all_approved(
    req: IngestAllApprovedReq,
    db: Session = Depends(get_db),
):
    # Lấy danh sách merchant đã APPROVED & campaign đang chạy
    approved_merchants = list_approved_merchants_api(db)  # ['shopee', 'lazada', ...]
    logger.info("[ALL-APPROVED] merchants=%s", approved_merchants)

    out = {
        "ok": True,
        "approved_merchants": approved_merchants,
        "promotions": 0,
        "offers_from_promotions": 0,
        "top_products_offers": 0,
        "datafeeds_offers": 0,
        "datafeeds_pages": 0,
    }

    # 1) Promotions (chạy theo từng merchant đã APPROVED để tránh rác)
    if req.include_promotions and approved_merchants:
        for m in approved_merchants:
            try:
                res = await ingest_v2_promotions(
                    IngestV2PromotionsReq(merchant=m, create_offers=True),
                    db
                )
                out["promotions"] += int(res.get("promotions") or 0)
                out["offers_from_promotions"] += int(res.get("offers_from_promotions") or 0)
                if req.throttle_ms:
                    await asyncio.sleep(req.throttle_ms / 1000.0)
            except Exception as e:
                logger.error("[ALL-APPROVED] promotions for %s failed: %s", m, e)

    # 2) Top products (theo từng merchant đã APPROVED)
    if req.include_top_products and approved_merchants:
        for m in approved_merchants:
            try:
                res = await ingest_v2_top_products(
                    IngestV2TopProductsReq(
                        merchant=m,
                        date_from=req.top_date_from,
                        date_to=req.top_date_to,
                        limit_per_page=req.top_limit_per_page,
                        max_pages=req.top_max_pages,
                        throttle_ms=req.throttle_ms,
                    ),
                    db
                )
                out["top_products_offers"] += int(res.get("imported") or 0)
                if req.throttle_ms:
                    await asyncio.sleep(req.throttle_ms / 1000.0)
            except Exception as e:
                logger.error("[ALL-APPROVED] top_products for %s failed: %s", m, e)

    # 3) Datafeeds (full, tự phân trang) — bản thân hàm đã yêu cầu APPROVED trong quá trình ghi
    if req.include_datafeeds:
        try:
            res = await ingest_accesstrade_datafeeds_all(
                IngestAllDatafeedsReq(
                    params=None,
                    limit_per_page=req.datafeeds_limit_per_page,
                    max_pages=req.datafeeds_max_pages,
                    throttle_ms=req.throttle_ms,
                ),
                db
            )
            out["datafeeds_offers"] = int(res.get("imported") or 0)
            out["datafeeds_pages"] = int(res.get("pages") or 0)
        except Exception as e:
            logger.error("[ALL-APPROVED] datafeeds failed: %s", e)

    return out

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
from datetime import datetime
@app.get(
    "/offers/check/{offer_id}",
    tags=["Offers 🛒"],
    summary="Kiểm tra 1 sản phẩm (alive/dead)",
    description="Kiểm tra nhanh **trạng thái link** của một sản phẩm trong DB theo **ID**."
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
        "checked_at": datetime.utcnow().isoformat() + "Z"
    }

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
        df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi đọc file Excel: {e}")
    # Chỉ import Excel mới áp dụng policy; mặc định False nếu chưa set
    flags = crud.get_policy_flags(db)
    only_with_commission = bool(flags.get("only_with_commission"))
    check_urls_excel = bool(flags.get("check_urls"))
    from accesstrade_service import _check_url_alive

    imported = 0
    for _, row in df.iterrows():
        base = {
            "source": "excel",
            "source_id": str(row.get("source_id") or row.get("id") or ""),
            "merchant": str(row.get("merchant") or "").lower(),
            "title": str(row.get("title") or ""),
            "url": str(row.get("url") or ""),
            "affiliate_url": row.get("affiliate_url"),
            "image_url": row.get("image_url"),
            "price": float(row.get("price")) if row.get("price") else None,
            "currency": row.get("currency") or "VND",
        }

        # Ghi campaign_id nếu có trong file Excel
        campaign_id = row.get("campaign_id")
        if pd.notna(campaign_id):
            base["campaign_id"] = str(campaign_id).strip()

        # Gom promotion
        promotion = {
            "name": row.get("promotion_name"),
            "content": row.get("promotion_content"),
            "start_time": row.get("promotion_start_time"),
            "end_time": row.get("promotion_end_time"),
            "coupon": row.get("promotion_coupon"),
            "link": row.get("promotion_link"),
        }
        promotion = {k: v for k, v in promotion.items() if pd.notna(v)}

        # Gom commission (nếu file có các cột này)
        commission = {
            "sales_ratio": row.get("commission_sales_ratio"),
            "sales_price": row.get("commission_sales_price"),
            "reward_type": row.get("commission_reward_type"),
            "target_month": row.get("commission_target_month"),
        }
        commission = {k: v for k, v in commission.items() if pd.notna(v)}

        # Gộp vào extra
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

    return {"ok": True, "imported": imported}

# --- Export sản phẩm từ DB ra file Excel ---
@app.get(
    "/offers/export-excel",
    tags=["Offers 🛒"],
    summary="Xuất sản phẩm ra Excel",
    description="Xuất sản phẩm trong DB ra file Excel. Có thể lọc theo merchant, title (tương đối), skip, limit."
)
def export_offers_excel(
    merchant: str | None = None,
    title: str | None = None,
    skip: int = 0,
    limit: int = 0,  # nếu =0 thì xuất toàn bộ
    db: Session = Depends(get_db)
):
    # Lấy query gốc
    query = db.query(models.ProductOffer)

    # Lọc theo merchant nếu có
    if merchant:
        query = query.filter(models.ProductOffer.merchant == merchant.lower())

    # Lọc theo title tương đối (LIKE) nếu có
    if title:
        like_pattern = f"%{title.lower()}%"
        query = query.filter(models.ProductOffer.title.ilike(like_pattern))

    # Skip + limit
    if skip:
        query = query.offset(skip)
    if limit:
        query = query.limit(limit)

    offers = query.all()
    # Prefetch map/group từ các bảng chuẩn hoá để join nhanh theo campaign_id
    from collections import defaultdict
    campaign_map = {c.campaign_id: c for c in db.query(models.Campaign).all()}

    commissions_by_cid = defaultdict(list)
    for cp in db.query(models.CommissionPolicy).all():
        commissions_by_cid[cp.campaign_id].append(cp)

    promotions_by_cid = defaultdict(list)
    for pr in db.query(models.Promotion).all():
        promotions_by_cid[pr.campaign_id].append(pr)

    # === JSONL: đọc log API để gán API_EMPTY / API_MISSING ===
    import os, json
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

    # Commissions theo campaign_id
    COMM_POLLED, COMM_EMPTY = set(), set()
    for rec in _read_jsonl(os.path.join(LOG_DIR, "commission_policies.jsonl")) or []:
        cid = str(rec.get("campaign_id") or "")
        if not cid:
            continue
        COMM_POLLED.add(cid)
        if int(rec.get("items_count") or 0) == 0:
            COMM_EMPTY.add(cid)

    # Promotions theo merchant (viết thường)
    PROMO_POLLED, PROMO_EMPTY = set(), set()
    for rec in _read_jsonl(os.path.join(LOG_DIR, "promotions.jsonl")) or []:
        m = (rec.get("merchant") or "").lower()
        if not m:
            continue
        PROMO_POLLED.add(m)
        if int(rec.get("items_count") or 0) == 0:
            PROMO_EMPTY.add(m)

    # Campaign detail: giữ bản ghi cuối theo campaign_id
    CAMP_LAST = {}
    for rec in _read_jsonl(os.path.join(LOG_DIR, "campaign_detail.jsonl")) or []:
        cid = str(rec.get("campaign_id") or "")
        if cid:
            CAMP_LAST[cid] = rec  # overwrite để lấy bản mới nhất

    def _campaign_field_from_log(cid: str, field_name: str):
        rec = CAMP_LAST.get(str(cid) if cid is not None else "")
        if not rec:
            return "API_MISSING"

        # 1) Hỗ trợ log rút gọn (boolean flags)
        if field_name == "end_time" and rec.get("has_end_time") is False:
            return "API_EMPTY"
        if field_name == "user_registration_status" and rec.get("has_user_status") is False:
            return "API_EMPTY"

        # 2) Hỗ trợ log dạng đầy đủ (raw JSON)
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

        # 3) Không có raw và cũng không có cờ → coi như chưa ghi log đúng chuẩn
        return "API_MISSING"

    rows = []
    for o in offers:

        base = {
            "id": o.id,
            "source": o.source,
            "source_id": o.source_id,
            "merchant": o.merchant,
            "title": o.title,
            "url": o.url,
            "affiliate_url": o.affiliate_url,
            "image_url": o.image_url,
            "price": o.price,
            "currency": o.currency,
            "campaign_id": o.campaign_id,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        }
        # Parse extra nếu có
        extra = {}
        if o.extra:
            try:
                extra = json.loads(o.extra)
            except Exception:
                extra = {"extra_raw": o.extra}

        # NEW: Enrich theo campaign_id (nếu có) — giữ Products gọn,
        # không dàn tràn campaign/commission/promotion vào base ở đây.
        cid = str(o.campaign_id or "")
        # (Các sheet Campaigns/Commissions/Promotions sẽ xử lý bên dưới)

        # Tách thêm các trường lặp từ extra (nếu có)
        base["desc"] = extra.get("desc")
        base["cate"] = extra.get("cate")
        base["shop_name"] = extra.get("shop_name")
        # Ưu tiên 'update_time_raw' (key chuẩn mới), fallback 'update_time' để tương thích
        base["update_time_raw"] = extra.get("update_time_raw") or extra.get("update_time")

        # Luôn giữ full extra raw để không mất thông tin
        base["extra_raw"] = json.dumps(extra, ensure_ascii=False)

        rows.append(base)

    if not rows:
        raise HTTPException(status_code=404, detail="Không có sản phẩm nào phù hợp trong DB")

    # Xuất ra Excel
# ĐOẠN MỚI (thay thế toàn bộ khối export 1 sheet thành 4 sheet)

    # ---------------------------
    # TẠO 4 SHEET ĐỒNG BỘ THỨ TỰ
    # ---------------------------
    import pandas as pd

    df_products_rows = []
    df_campaigns_rows = []
    df_commissions_rows = []
    df_promotions_rows = []

    for base in rows:
        # base có: id, source, source_id, merchant, title, url, affiliate_url, image_url,
        # price, currency, campaign_id, updated_at, desc, cate, shop_name, update_time_raw,
        # promotion_* (nếu đã map), extra_raw (full JSON)
        # -> Ta vẫn giữ Products gọn: không dàn tràn commission/promotion vào đây
        prod_row = {
            "id": base.get("id"),
            "source": base.get("source"),
            "source_id": base.get("source_id"),
            "merchant": base.get("merchant"),
            "title": base.get("title"),
            "url": base.get("url"),
            "affiliate_url": base.get("affiliate_url"),
            "image_url": base.get("image_url"),
            "price": base.get("price"),
            "currency": base.get("currency"),
            "campaign_id": base.get("campaign_id"),
            "updated_at": base.get("updated_at"),
            # Một số trường extra tiện tra cứu
            "desc": base.get("desc"),
            "cate": base.get("cate"),
            "shop_name": base.get("shop_name"),
            "update_time_raw": base.get("update_time_raw"),
            "extra_raw": base.get("extra_raw"),
        }
        df_products_rows.append(prod_row)

        # Tách extra để đọc commission/promotion/campaign-info
        try:
            extra = json.loads(base.get("extra_raw", "{}")) if base.get("extra_raw") else {}
        except Exception:
            extra = {}


        # --- Campaigns sheet (join từ bảng Campaign)
        cid = str(base.get("campaign_id") or "") if base.get("campaign_id") is not None else ""
        c = campaign_map.get(cid)

        # Nếu DB có giá trị thì dùng; nếu trống → tra log để gán API_EMPTY / API_MISSING
        user_val = (c.user_registration_status if c else None)
        end_val = (c.end_time if c else None)
        if user_val in (None, "", []):
            user_val = _campaign_field_from_log(cid, "user_registration_status")
        if end_val in (None, "", []):
            end_val = _campaign_field_from_log(cid, "end_time")

        camp_row = {
            "product_id": base.get("id"),
            "merchant": base.get("merchant"),
            "campaign_id": cid,
            "campaign_name": (c.name if c else None),
            "approval_type": (c.approval if c else None),
            "user_status": user_val,  # NOT_REGISTERED/PENDING/APPROVED hoặc API_EMPTY/API_MISSING
            "status": (c.status if c else _campaign_field_from_log(cid, "status")),
            "start_time": (c.start_time if c else None),
            "end_time": end_val,      # yyyy-mm-dd hoặc API_EMPTY/API_MISSING
        }

        df_campaigns_rows.append(camp_row)

        # --- Commissions sheet (join từ bảng CommissionPolicy, gom nhiều chính sách về 1 hàng)
        cid = str(base.get("campaign_id") or "") if base.get("campaign_id") is not None else ""
        pols = commissions_by_cid.get(cid, [])
        def _join(vals): 
            vals = [str(v) for v in vals if v not in (None, "")]
            return "; ".join(sorted(set(vals))) if vals else None

        if pols:
            df_commissions_rows.append({
                "product_id": base.get("id"),
                "sales_ratio": _join([p.sales_ratio for p in pols]),
                "sales_price": _join([p.sales_price for p in pols]),
                "reward_type": _join([p.reward_type for p in pols]),
                "target_month": _join([p.target_month for p in pols]),
            })
        else:
            # Không có policy trong DB → tra log theo campaign_id để gắn nhãn
            tag = "API_EMPTY" if cid in COMM_EMPTY else ("API_MISSING" if (cid and cid not in COMM_POLLED) else "API_EMPTY")
            df_commissions_rows.append({
                "product_id": base.get("id"),
                "sales_ratio": None,
                "sales_price": None,
                "reward_type": tag,
                "target_month": None,
            })

        # --- Promotions sheet (join từ bảng Promotion, có thể nhiều khuyến mãi -> gộp)
        cid = str(base.get("campaign_id") or "") if base.get("campaign_id") is not None else ""
        pr_list = promotions_by_cid.get(cid, [])

        def _join(vals):
            vals = [str(v) for v in vals if v not in (None, "")]
            return "; ".join(sorted(set(vals))) if vals else None

        if pr_list:
            df_promotions_rows.append({
                "product_id": base.get("id"),
                "promotion_name": _join([p.name for p in pr_list]),
                "promotion_content": _join([p.content for p in pr_list]),
                "promotion_start_time": _join([p.start_time for p in pr_list]),
                "promotion_end_time": _join([p.end_time for p in pr_list]),
                "promotion_coupon": _join([p.coupon for p in pr_list]),
                "promotion_link": _join([p.link for p in pr_list]),
            })
        else:
            # Không có promotion trong DB → tra log theo merchant để gắn nhãn
            mkey = (base.get("merchant") or "").lower()
            if not mkey and cid and cid in campaign_map:
                mkey = (getattr(campaign_map[cid], "merchant", "") or "").lower()
            tag = "API_EMPTY" if (mkey in PROMO_EMPTY) else ("API_MISSING" if (mkey and mkey not in PROMO_POLLED) else "API_EMPTY")
            df_promotions_rows.append({
                "product_id": base.get("id"),
                "promotion_name": tag,
                "promotion_content": None,
                "promotion_start_time": None,
                "promotion_end_time": None,
                "promotion_coupon": None,
                "promotion_link": None,
            })

    # DataFrames
    df_products = pd.DataFrame(df_products_rows)
    df_campaigns = pd.DataFrame(df_campaigns_rows)
    df_commissions = pd.DataFrame(df_commissions_rows)
    df_promotions = pd.DataFrame(df_promotions_rows)

    # Hàng dịch nghĩa (tiếng Việt) cho từng sheet
    trans_products = {
        "id": "Mã ID", "source": "Nguồn", "source_id": "Mã nguồn", "merchant": "Nhà bán",
        "title": "Tên sản phẩm", "url": "Link gốc", "affiliate_url": "Link tiếp thị",
        "image_url": "Ảnh sản phẩm", "price": "Giá", "currency": "Tiền tệ",
        "campaign_id": "Chiến dịch", "updated_at": "Ngày cập nhật", "desc": "Mô tả chi tiết",
        "cate": "Danh mục", "shop_name": "Tên cửa hàng", "update_time_raw": "Thời gian cập nhật từ nguồn",
        "extra_raw": "Extra gốc",
    }
    trans_campaigns = {
        "product_id": "ID sản phẩm", "merchant": "Nhà bán",
        "campaign_name": "Tên chiến dịch", "approval_type": "Approval", "user_status": "Trạng thái của tôi",
        "status": "Tình trạng",  # NEW
        "start_time": "Bắt đầu", "end_time": "Kết thúc",
    }
    trans_commissions = {
        "product_id": "ID sản phẩm", "sales_ratio": "Tỷ lệ (%)",
        "sales_price": "Hoa hồng cố định", "reward_type": "Kiểu thưởng", "target_month": "Tháng áp dụng",
    }
    trans_promotions = {
        "product_id": "ID sản phẩm", "promotion_name": "Tên khuyến mãi", "promotion_content": "Nội dung",
        "promotion_start_time": "Bắt đầu KM", "promotion_end_time": "Kết thúc KM",
        "promotion_coupon": "Mã giảm", "promotion_link": "Link khuyến mãi",
    }

    def _with_header(df, trans):
        if df.empty:
            return df
        header = {c: trans.get(c, c) for c in df.columns}
        return pd.concat([pd.DataFrame([header]), df], ignore_index=True)

    df_products = _with_header(df_products, trans_products)
    df_campaigns = _with_header(df_campaigns, trans_campaigns)
    df_commissions = _with_header(df_commissions, trans_commissions)
    df_promotions = _with_header(df_promotions, trans_promotions)

    # Ghi 4 sheet
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_products.to_excel(writer, sheet_name="Products", index=False)
        df_campaigns.to_excel(writer, sheet_name="Campaigns", index=False)
        df_commissions.to_excel(writer, sheet_name="Commissions", index=False)
        df_promotions.to_excel(writer, sheet_name="Promotions", index=False)
    output.seek(0)

    filename = f"offers_export_{int(time.time())}.xlsx"
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
