import logging
import traceback
import os, hmac, hashlib, base64, json, time, asyncio
from urllib.parse import urlparse, quote_plus
from typing import Optional, Dict, List, Any, Literal

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from providers import ProviderRegistry, ProviderOps
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.responses import HTMLResponse
import io
from fastapi.exceptions import RequestValidationError

from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_, func

from ai_service import suggest_products_with_config
import models, schemas, crud
from database import Base, engine, SessionLocal, apply_simple_migrations
from pydantic import BaseModel, HttpUrl, Field
from accesstrade_service import (
    fetch_products, map_at_product_to_offer, _check_url_alive, fetch_promotions,
    fetch_campaign_detail, fetch_commission_policies  # NEW
)

# FastAPI application instance with organized Swagger tags and VN docs
tags_metadata = [
    {"name": "System 🛠️", "description": "Các API kiểm tra sức khỏe hệ thống và vận hành."},
    {"name": "Links 🔗", "description": "Quản lý link tiếp thị (CRUD)."},
    {"name": "API Configs ⚙️", "description": "Cấu hình nhà cung cấp AI/API (ví dụ: Accesstrade, mô hình AI)."},
    {"name": "Settings ⚙️", "description": "Cài đặt/policy hệ thống: cấu hình ingest, bật/tắt kiểm tra link khi import Excel."},
    {"name": "Affiliate 🎯", "description": "Mẫu deeplink, chuyển đổi link gốc → deeplink, shortlink an toàn."},
    {"name": "Campaigns 📢", "description": "Chiến dịch: danh sách, summary, merchants đã duyệt."},
    {"name": "Offers 🛒", "description": "Sản phẩm/offer: liệt kê, cập nhật, xoá, import Excel, kiểm tra link sống."},
    {"name": "Ingest 🌐", "description": "Đồng bộ dữ liệu từ nhà cung cấp (Accesstrade): campaigns, datafeeds, promotions, top products."},
    {"name": "AI 🤖", "description": "Các tính năng AI: gợi ý sản phẩm và kiểm tra nhanh."},
]

app = FastAPI(
    title="AI Affiliate API",
    description=(
        "Bộ API quản lý affiliate: chiến dịch, sản phẩm, deeplink và ingest từ Accesstrade.\n\n"
        "Hướng dẫn chung:\n"
        "- Các nhóm API được sắp xếp theo chức năng để dễ tìm.\n"
        "- Các ví dụ đi kèm (Example) bằng tiếng Việt ngay trong schema request.\n"
        "- Khi cần demo nhanh, bật biến môi trường AT_MOCK=1 để dùng dữ liệu giả lập.\n"
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
    swagger_ui_parameters={
        "docExpansion": "list",                # mở rộng theo danh sách, gọn hơn
        "defaultModelsExpandDepth": -1,         # thu gọn mục Schemas mặc định
        "defaultModelExpandDepth": 0,           # không auto mở từng schema
        "displayRequestDuration": True,
    },
)

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

# --- DB init: create tables and apply lightweight migrations (no Alembic here) ---
Base.metadata.create_all(bind=engine)
# Ensure older Postgres DBs get new columns added idempotently
try:
    apply_simple_migrations(engine)
except Exception:
    # Non-fatal: continue startup even if migration helper fails
    logger = logging.getLogger("affiliate_api")
    logger.warning("apply_simple_migrations failed during startup", exc_info=True)

# Thiết lập mặc định cho policy link-check nếu chưa có trong DB
def _ensure_default_policy_flags():
    db = SessionLocal()
    try:
        cfg = crud.get_api_config(db, "ingest_policy")
        s = (cfg.model or "") if cfg else ""
        # Chỉ đặt nếu CHƯA có trong chuỗi model
        if "linkcheck_mod=" not in (s or ""):
            crud.set_policy_flag(db, "linkcheck_mod", 24)
        if "linkcheck_limit=" not in (s or ""):
            crud.set_policy_flag(db, "linkcheck_limit", 1000)
    except Exception:
        pass
    finally:
        db.close()

_ensure_default_policy_flags()

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
    description=(
        "Trả về ok=true nếu kết nối DB hoạt động.\n\n"
        "Ví dụ: gọi GET /health → {\"ok\": true}"
    )
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
    description=(
        "Tạo mới một link tiếp thị và lưu vào DB.\n\n"
        "- Bắt buộc: name, url, affiliate_url.\n"
        "- Tuỳ chọn: (không có).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"name\": \"Link Shopee điện thoại\",\n  \"url\": \"https://shopee.vn/product/123\",\n  \"affiliate_url\": \"https://go.example/?url=https%3A%2F%2Fshopee.vn%2Fproduct%2F123\"\n}"
    ),
    response_model=schemas.AffiliateLinkOut
)
def create_link(
    link: schemas.AffiliateLinkCreate = Body(
        ...,
        examples={
            "default": {
                "summary": "Link Shopee",
                "value": {
                    "name": "Link Shopee điện thoại",
                    "url": "https://shopee.vn/product/123",
                    "affiliate_url": "https://go.example/?url=https%3A%2F%2Fshopee.vn%2Fproduct%2F123"
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
    logger.debug("Create link payload: %s", link.model_dump() if hasattr(link, "model_dump") else link.dict())
    return crud.create_link(db, link)

@app.put(
    "/links/{link_id}",
    tags=["Links 🔗"],
    summary="Cập nhật link",
    description=(
        "Cập nhật thông tin một link tiếp thị theo **ID**.\n\n"
        "- Bắt buộc: name, url, affiliate_url (hiện schema yêu cầu đủ 3 trường).\n"
        "- Tuỳ chọn: (không có).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"name\": \"Link Shopee A\",\n  \"url\": \"https://shopee.vn/product/123\",\n  \"affiliate_url\": \"https://go.example/?url=...\"\n}"
    ),
    response_model=schemas.AffiliateLinkOut
)
def update_link(
    link_id: int,
    link: schemas.AffiliateLinkUpdate = Body(
        ...,
        examples={
            "default": {
                "summary": "Cập nhật đủ trường",
                "value": {
                    "name": "Link Shopee A",
                    "url": "https://shopee.vn/product/123",
                    "affiliate_url": "https://go.example/?url=..."
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
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
    description=(
        "**Tạo mới hoặc cập nhật** cấu hình dựa trên `name`. Thuận tiện để cập nhật nhanh.\n\n"
        "- Bắt buộc: name, base_url, api_key.\n"
        "- Tuỳ chọn: model (chuỗi lưu trữ flags/tuỳ biến).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"name\": \"accesstrade\",\n  \"base_url\": \"https://api.accesstrade.vn\",\n  \"api_key\": \"AT-XXXX\",\n  \"model\": \"only_with_commission=true\"\n}"
    ),
    response_model=schemas.APIConfigOut
)
def upsert_api_config(
    config: schemas.APIConfigCreate = Body(
        ...,
        examples={
            "default": {
                "summary": "Accesstrade",
                "value": {
                    "name": "accesstrade",
                    "base_url": "https://api.accesstrade.vn",
                    "api_key": "AT-XXXX",
                    "model": "only_with_commission=true"
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
    """Tạo mới hoặc cập nhật API config theo name."""
    return crud.upsert_api_config_by_name(db, config)

@app.put(
    "/api-configs/{config_id}",
    tags=["API Configs ⚙️"],
    summary="Cập nhật cấu hình API",
    description=(
        "Cập nhật thông tin cấu hình theo **ID**.\n\n"
        "- Bắt buộc: name, base_url, api_key.\n"
        "- Tuỳ chọn: model.\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"name\": \"accesstrade\",\n  \"base_url\": \"https://api.accesstrade.vn\",\n  \"api_key\": \"AT-XXXX\",\n  \"model\": \"check_urls=true\"\n}"
    ),
    response_model=schemas.APIConfigOut
)
def update_api_config(
    config_id: int,
    config: schemas.APIConfigCreate = Body(
        ...,
        examples={
            "default": {
                "summary": "Cập nhật khoá",
                "value": {
                    "name": "accesstrade",
                    "base_url": "https://api.accesstrade.vn",
                    "api_key": "AT-NEW-KEY",
                    "model": "check_urls=true"
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
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
    description=(
        "Hiển thị đầy đủ các mẫu deeplink hiện có trong DB.\n\n"
        "Gợi ý: cấu hình một mẫu cho mỗi cặp (merchant, network)."
    ),
    response_model=list[schemas.AffiliateTemplateOut]
)
def list_templates(db: Session = Depends(get_db)):
    return crud.list_affiliate_templates(db)

@app.post(
    "/aff/templates/upsert",
    tags=["Affiliate 🎯"],
    summary="Upsert mẫu deeplink",
    description=(
        "Thêm/cập nhật mẫu deeplink cho từng merchant/network.\n\n"
        "- Bắt buộc: merchant, network, template.\n"
        "- Tuỳ chọn: default_params (object), enabled (bool, mặc định true).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"merchant\": \"shopee\",\n  \"network\": \"accesstrade\",\n  \"template\": \"https://go.example/?url={target}&sub1={sub1}\",\n  \"default_params\": {\"sub1\": \"my_subid\"}\n}"
    ),
    response_model=schemas.AffiliateTemplateOut
)
def upsert_template(
    data: schemas.AffiliateTemplateCreate = Body(
        ...,
        examples={
            "default": {
                "summary": "Mẫu Shopee",
                "value": {
                    "merchant": "shopee",
                    "network": "accesstrade",
                    "template": "https://go.example/?url={target}&sub1={sub1}",
                    "default_params": {"sub1": "my_subid"}
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
    tpl = crud.upsert_affiliate_template(db, data)
    return tpl

@app.put(
    "/aff/templates/{template_id}",
    tags=["Affiliate 🎯"],
    summary="Cập nhật mẫu deeplink",
    description=(
        "Sửa mẫu deeplink theo ID.\n\n"
        "- Bắt buộc: merchant, network, template.\n"
        "- Tuỳ chọn: default_params, enabled.\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"merchant\": \"lazada\",\n  \"network\": \"accesstrade\",\n  \"template\": \"https://go.example/?url={target}&sub1={sub1}\",\n  \"default_params\": {\"sub1\": \"ads2025\"},\n  \"enabled\": true\n}"
    ),
    response_model=schemas.AffiliateTemplateOut
)
def update_template(
    template_id: int,
    data: schemas.AffiliateTemplateCreate = Body(
        ...,
        examples={
            "default": {
                "summary": "Sửa mẫu Lazada",
                "value": {
                    "merchant": "lazada",
                    "network": "accesstrade",
                    "template": "https://go.example/?url={target}&sub1={sub1}",
                    "default_params": {"sub1": "ads2025"},
                    "enabled": True
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "merchant": "shopee",
                    "url": "https://shopee.vn/product/12345",
                    "network": "accesstrade",
                    "params": {"sub1": "campaign_fb", "utm_source": "fbad"}
                }
            ]
        }
    }

class ConvertRes(BaseModel):
    affiliate_url: str
    short_url: str

# Convert link gốc -> deeplink + shortlink /r/{token}
@app.post(
    "/aff/convert",
    tags=["Affiliate 🎯"],
    summary="Chuyển link gốc → deeplink + shortlink",
    description=(
        "Nhận link gốc + merchant → trả về affiliate_url (deeplink) và short_url dạng /r/{token}.\n\n"
        "- Bắt buộc: merchant, url.\n"
        "- Tuỳ chọn: params (object), network (mặc định \"accesstrade\").\n\n"
        "Lưu ý: URL phải thuộc domain hợp lệ của merchant (ví dụ shopee.vn).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"merchant\": \"shopee\",\n  \"url\": \"https://shopee.vn/product/123\",\n  \"params\": {\"sub1\": \"abc\"}\n}"
    ),
    response_model=ConvertRes
)
def aff_convert(
    req: ConvertReq = Body(
        ...,
        examples={
            "default": {
                "summary": "Convert Shopee",
                "value": {
                    "merchant": "shopee",
                    "url": "https://shopee.vn/product/123",
                    "params": {"sub1": "abc"}
                }
            }
        }
    ),
    db: Session = Depends(get_db)
):
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
    # Tuỳ chọn chung (không bắt buộc, có thể bị bỏ qua tuỳ provider)
    check_urls: bool = False
    verbose: bool = False
    throttle_ms: int = 50

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "provider": "accesstrade",
                    "path": "/v1/datafeeds",
                    "params": {"merchant": "tikivn", "page": "1", "limit": "50"},
                    "check_urls": False,
                    "verbose": False,
                    "throttle_ms": 50
                }
            ]
        }
    }

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
    - throttle_ms: nghỉ giữa các lần gọi để tôn trọng rate-limit (mặc định 50ms)
    - check_urls: nếu True mới kiểm tra link sống (mặc định False).
    """
    params: Dict[str, str] | None = None
    limit_per_page: int = 100
    max_pages: int = 2000
    throttle_ms: int = 50
    check_urls: bool = False
    verbose: bool = False
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "params": {"merchant": "tikivn"},
                    "limit_per_page": 100,
                    "max_pages": 1,
                    "throttle_ms": 50,
                    "check_urls": False,
                    "verbose": False
                }
            ]
        }
    }
    
class CampaignsSyncReq(BaseModel):
    """
    Đồng bộ campaigns từ Accesstrade (tối ưu tốc độ).
    - statuses: danh sách trạng thái cần quét, mặc định ["running","paused"].
    - only_my: True -> chỉ giữ approval in {"successful","pending"} (nhanh hơn, ít ghi DB).
    - enrich_user_status: lấy user_status thật từ campaign detail (chậm). Mặc định False để nhanh.
    - limit_per_page, page_concurrency, window_pages, throttle_ms: tinh chỉnh tốc độ vs độ ổn định.
    - merchant: nếu truyền sẽ lọc theo merchant sau khi fetch.
    """
    statuses: List[str] = Field(default_factory=lambda: ["running", "paused"])
    only_my: bool = True
    enrich_user_status: bool = True
    limit_per_page: int = 50
    page_concurrency: int = 6
    window_pages: int = 10
    throttle_ms: int = 50
    merchant: str | None = None
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "statuses": ["running", "paused"],
                    "only_my": True,
                    "enrich_user_status": False,
                    "limit_per_page": 50,
                    "page_concurrency": 6,
                    "window_pages": 10,
                    "throttle_ms": 50
                }
            ]
        }
    }

class IngestV2PromotionsReq(BaseModel):
    """
    Ingest khuyến mãi (offers_informations) theo merchant đã duyệt.
    - merchant: nếu truyền, chỉ ingest đúng merchant này; nếu bỏ trống sẽ chạy cho tất cả merchant active.
    - Lưu ý: KHÔNG tạo ProductOffer từ Promotions.
    """
    merchant: str | None = None
    verbose: bool = False
    throttle_ms: int = 50
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "merchant": "tikivn",
                    "verbose": False,
                    "throttle_ms": 50
                }
            ]
        }
    }

class IngestV2TopProductsReq(BaseModel):
    """
    Ingest top_products (bán chạy) theo merchant & khoảng ngày.
    - date_from/date_to: 'YYYY-MM-DD' (tùy Accesstrade hỗ trợ); nếu bỏ trống có thể lấy mặc định phía API.
    - limit_per_page: kích thước trang (<=100)
    - max_pages: số trang tối đa sẽ quét
    - throttle_ms: nghỉ giữa các lần gọi
    - check_urls: nếu True mới kiểm tra link sống (mặc định False).
    """
    merchant: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    check_urls: bool = False
    verbose: bool = False
    limit_per_page: int = 100
    max_pages: int = 200
    throttle_ms: int = 50
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "merchant": "tikivn",
                    "date_from": "2025-09-15",
                    "date_to": "2025-09-22",
                    "limit_per_page": 50,
                    "max_pages": 1,
                    "check_urls": False,
                    "verbose": False,
                    "throttle_ms": 50
                }
            ]
        }
    }
## (old) Removed duplicated unified request classes — sử dụng nhóm *Unified* phía dưới

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
    """Summary theo chuẩn mới: chỉ dựa trên user_registration_status."""
    rows = db.query(
        models.Campaign.status,
        models.Campaign.user_registration_status,
        models.Campaign.merchant,
    ).all()

    total = len(rows)

    def _norm_user(us: str | None) -> str | None:
        if not us:
            return None
        u = str(us).strip().upper()
        # chấp nhận SUCCESSFUL như APPROVED để tương thích nguồn dữ liệu
        if u == "SUCCESSFUL":
            return "APPROVED"
        return u

    by_status: dict[str, int] = {}
    by_user_status: dict[str, int] = {}
    running_approved_count = 0
    approved_merchants_set: set[str] = set()

    for status, us, merchant in rows:
        st_key = status or "NULL"
        by_status[st_key] = by_status.get(st_key, 0) + 1

        eff_user = _norm_user(us)
        us_key = eff_user or "NULL"
        by_user_status[us_key] = by_user_status.get(us_key, 0) + 1

        if (status == "running") and (eff_user == "APPROVED"):
            running_approved_count += 1
            if merchant:
                approved_merchants_set.add(merchant)

    approved_merchants = sorted(approved_merchants_set)

    return {
        "total": total,
        "by_status": by_status,
        "by_user_status": by_user_status,
        "running_approved_count": running_approved_count,
        "approved_merchants": approved_merchants,
    }

@app.post(
    "/campaigns/backfill-user-status",
    tags=["Campaigns 📢"],
    summary="Backfill user_registration_status cho campaigns bị NULL/empty",
    description=(
        "Dò các campaign có user_registration_status NULL/empty, gọi campaign detail để lấy trạng thái,\n"
        "chuẩn hoá (SUCCESSFUL→APPROVED) và upsert lại. Trả về thống kê trước/sau và số lượng cập nhật.\n\n"
        "Lưu ý: Dùng AT_MOCK=1 để chạy ở chế độ mock nếu chưa cấu hình Accesstrade."
    )
)
async def backfill_user_status(limit: int = 200, db: Session = Depends(get_db)):
    # Helper: normalize user status
    def _norm(us: str | None) -> str | None:
        if not us:
            return None
        s = str(us).strip().upper()
        if not s:
            return None
        if s == "SUCCESSFUL":
            return "APPROVED"
        return s

    def _summary() -> dict:
        rows = db.query(models.Campaign.status, models.Campaign.user_registration_status).all()
        total = len(rows)
        by_status: dict[str,int] = {}
        by_user: dict[str,int] = {}
        for st, us in rows:
            st_key = st or "NULL"
            by_status[st_key] = by_status.get(st_key, 0) + 1
            eff = _norm(us) or "NULL"
            by_user[eff] = by_user.get(eff, 0) + 1
        return {"total": total, "by_status": by_status, "by_user_status": by_user}

    before = _summary()

    targets = (
        db.query(models.Campaign)
        .filter(or_(models.Campaign.user_registration_status.is_(None), func.trim(models.Campaign.user_registration_status) == ""))
        .limit(limit)
        .all()
    )
    fixed = 0
    for c in targets:
        try:
            det = await fetch_campaign_detail(db, c.campaign_id)
            if not det:
                continue
            user_raw = (
                det.get("user_registration_status")
                or det.get("publisher_status")
                or det.get("user_status")
            )
            if not user_raw:
                appr = det.get("approval")
                if isinstance(appr, str) and appr.lower() in ("successful", "pending", "unregistered"):
                    user_raw = "APPROVED" if appr.lower() == "successful" else appr.upper()
            eff = _norm(user_raw)
            if not eff:
                continue
            crud.upsert_campaign(db, schemas.CampaignCreate(
                campaign_id=str(c.campaign_id),
                user_registration_status=eff,
            ))
            fixed += 1
        except Exception:
            continue

    after = _summary()
    return {"fixed": fixed, "before": before, "after": after}

# Legacy maintenance endpoints removed; project uses the new standard exclusively.

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
    # approval giờ chỉ mang nghĩa kiểu duyệt campaign; không dùng cho user status filter nữa
    if approval:
        q = q.filter(models.Campaign.approval == approval)
    # Filter user_status theo chuẩn mới trực tiếp
    if user_status:
        us = user_status.strip().upper()
        if us == "SUCCESSFUL":
            us = "APPROVED"
        q = q.filter(func.upper(func.trim(models.Campaign.user_registration_status)) == us)
    if merchant:
        q = q.filter(models.Campaign.merchant == merchant)
    return q.order_by(models.Campaign.updated_at.desc()).all()

@app.get("/campaigns/approved-merchants", response_model=list[str], tags=["Campaigns 📢"])
def list_approved_merchants_api(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Campaign.merchant)
        .filter(models.Campaign.status == "running")
        .filter(func.upper(func.trim(models.Campaign.user_registration_status)).in_(["APPROVED", "SUCCESSFUL"]))
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
    category: Literal["offers", "top-products"] = Query(
        "offers",
        description="Nhóm dữ liệu: offers | top-products"
    ),
    db: Session = Depends(get_db)
):
    """
    🛒 Lấy danh sách sản phẩm trong DB có phân trang  
    - `merchant`: lọc theo tên merchant (vd: `shopee`, `lazada`, `tiki`)  
    - `skip`: số bản ghi bỏ qua (offset)  
    - `limit`: số bản ghi tối đa trả về  
    - `category`: 'offers' (mặc định) hoặc 'top-products'.
    """
    cat = (category or "offers").strip().lower()
    if cat not in ("offers", "top-products"):
        raise HTTPException(status_code=400, detail="category không hợp lệ; chỉ hỗ trợ: offers | top-products")

    if cat == "top-products":
        rows = crud.list_offers(db, merchant=merchant, skip=skip, limit=limit, source_type="top_products")
    else:
        # 'offers' mặc định: loại trừ các nhóm không phải catalog chính
        rows = crud.list_offers(db, merchant=merchant, skip=skip, limit=limit, exclude_source_types=["top_products", "promotions"])

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
    tags=["Settings ⚙️"],
    summary="Cấu hình policy ingest",
    description=(
        "Bật/tắt chế độ chỉ ingest sản phẩm có commission policy.\n"
        "Bắt buộc: (không có) — dùng query only_with_commission=true/false.\n"
        "Ví dụ: /ingest/policy?only_with_commission=true"
    )
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
    tags=["Settings ⚙️"],
    summary="Bật/tắt kiểm tra link khi IMPORT EXCEL",
    description=(
        "Chỉ ảnh hưởng import Excel. API ingest (V1/V2) luôn mặc định KHÔNG check link.\n"
        "Bắt buộc: (không có) — dùng query enable=true/false.\n"
        "Ví dụ: /ingest/policy/check-urls?enable=true"
    )
)
def set_ingest_policy_check_urls(enable: bool = False, db: Session = Depends(get_db)):
    # dùng store flags trong api_configs.name='ingest_policy'
    crud.set_policy_flag(db, "check_urls", enable)
    flags = crud.get_policy_flags(db)
    return {"ok": True, "flags": flags}

@app.post(
    "/ingest/products",
    tags=["Ingest 🌐"],
    summary="Ingest sản phẩm từ nhiều provider",
    description=(
        "Nhập sản phẩm vào DB từ các provider. Hiện hỗ trợ Accesstrade.\n\n"
        "- Bắt buộc: (không có — provider mặc định \"accesstrade\", path mặc định \"/v1/publishers/product_search\").\n"
        "- Tuỳ chọn: path, params (chuyển xuống API của provider).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"provider\": \"accesstrade\",\n  \"path\": \"/v1/datafeeds\",\n  \"params\": {\"merchant\": \"tikivn\", \"page\": \"1\", \"limit\": \"50\"}\n}"
    )
)
async def ingest_products(
    req: IngestReq = Body(
        ...,
        examples={
            "default": {
                "summary": "Datafeeds theo merchant",
                "value": {
                    "provider": "accesstrade",
                    "path": "/v1/datafeeds",
                    "params": {"merchant": "tikivn", "page": "1", "limit": "50"}
                }
            }
        }
    ),
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
            _us = (_row.user_registration_status or "").upper() if _row else ""
            if _us == "SUCCESSFUL":
                _us = "APPROVED"
            if not _row or _us != "APPROVED":
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
            if us == "SUCCESSFUL":
                us = "APPROVED"
            data["approval_status"] = (
                "successful" if us == "APPROVED" else
                "pending" if us == "PENDING" else
                "unregistered" if us == "NOT_REGISTERED" else None
            )
            data["eligible_commission"] = (
                (_camp_row.status == "running") and (us == "APPROVED")
            )

        if not await _check_url_alive(str(data.get("url") or "")):
            logger.info("Skip dead product [manual ingest]: title='%s'", data.get("title"))
            _vlog("dead_url", {"url": data.get("url")})
            continue

        try:
            crud.upsert_offer_for_excel(db, schemas.ProductOfferCreate(**data))
        except Exception:
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
                # Ghi user_status hiệu dụng (ưu tiên giá trị mới; nếu None dùng giá trị cũ để tránh NULL)
                user_registration_status=eff_user,           # NOT_REGISTERED/PENDING/APPROVED hoặc None
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

    # Map merchant -> approved campaign_id (running + user APPROVED) for fallback rebinding
    approved_cid_by_merchant: dict[str, str] = {}
    try:
        for cid, m in active_campaigns.items():
            _row = crud.get_campaign_by_cid(db, cid)
            if _row:
                _us = (_row.user_registration_status or "").upper()
                if _us == "SUCCESSFUL":
                    _us = "APPROVED"
                if _us == "APPROVED":
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
            if _row:
                _us = (_row.user_registration_status or "").upper()
                if _us == "SUCCESSFUL":
                    _us = "APPROVED"
                if _us == "APPROVED":
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
                    if us == "SUCCESSFUL":
                        us = "APPROVED"
                    if (not _row) or (us != "APPROVED"):
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
                            if _us == "SUCCESSFUL":
                                _us = "APPROVED"
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
                    if us == "SUCCESSFUL":
                        us = "APPROVED"
                    data["approval_status"] = (
                        "successful" if us == "APPROVED" else
                        "pending" if us == "PENDING" else
                        "unregistered" if us == "NOT_REGISTERED" else None
                    )
                    data["eligible_commission"] = (
                        (_camp_row.status == "running") and (us == "APPROVED")
                    )

                # Link gốc: chỉ kiểm tra khi bật cờ (để tránh bỏ sót do chặn bot/timeout trong môi trường container)
                if req.check_urls:
                    if not await _check_url_alive(data["url"]):
                        if req.verbose:
                            _vlog("dead_url", {"url": data.get("url"), "merchant": merchant_norm, "page": page})
                        continue

                try:
                    crud.upsert_offer_for_excel(db, schemas.ProductOfferCreate(**data))
                except Exception:
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
    statuses = (req.statuses or ["running", "paused"])  # mặc định: chạy cả running và paused
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
                # Ghi user_status hiệu dụng (ưu tiên giá trị mới; nếu None dùng giá trị cũ để tránh NULL)
                user_registration_status=eff_user,   # NOT_REGISTERED / PENDING / APPROVED / None
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
    from accesstrade_service import fetch_promotions, fetch_active_campaigns, _log_jsonl
    imported_promos = 0

    # Helper: phân loại chuỗi theo yêu cầu
    def _classify_str(rec: dict, key: str) -> str | None:
        if key in rec:
            v = rec.get(key)
            s = (str(v).strip() if v is not None else "")
            # Tránh lưu placeholder vào DB: trả về None nếu trống
            return s if s else None
        # key không tồn tại → không có dữ liệu mới
        return None

    # 0) Tập merchant cần chạy = theo yêu cầu hoặc theo DB các campaign đã APPROVED/SUCCESSFUL
    #    KHÔNG bắt buộc campaign đang running đối với việc lưu promotions
    #    Lưu ý: KHÔNG filter theo req.merchant ở đây để tránh miss do alias (vd tikivn ↔ tiki)
    approved_rows = (
        db.query(models.Campaign)
        .filter(func.upper(func.trim(models.Campaign.user_registration_status)).in_(["APPROVED", "SUCCESSFUL"]))  # type: ignore
        .all()
    )

    # Map merchant -> danh sách campaign đã APPROVED (ưu tiên chọn status=running sau này)
    approved_by_merchant: dict[str, list[models.Campaign]] = {}
    for c in approved_rows:
        if not c.merchant:
            continue
        mkey = c.merchant.lower()
        approved_by_merchant.setdefault(mkey, []).append(c)

    merchants: set[str] = set(approved_by_merchant.keys())
    if not merchants and not req.merchant:
        # Fallback mềm: nếu DB chưa có dữ liệu user_status (lần đầu sync), lấy merchants từ campaigns running
        active = await fetch_active_campaigns(db)  # {cid: merchant}
        merchants = {m for m in active.values() if m}
    if req.merchant:
        merchants = {req.merchant.strip().lower()}

    # 1) Vòng lặp từng merchant
    for m in sorted(merchants):
        _alias = {"lazadacps": "lazada", "tikivn": "tiki"}
        m_fetch = _alias.get(m, m)
        promos = await fetch_promotions(db, m_fetch) or []

        # Chọn campaign_id đã APPROVED & RUNNING cho merchant này
        cid_candidates = approved_by_merchant.get(m, []) or approved_by_merchant.get(m_fetch, [])
        cid_pick: str | None = None
        for row in cid_candidates:
            if (row.status or "").lower() == "running":
                cid_pick = row.campaign_id
                break

        if not cid_pick:
            # Không có campaign APPROVED đang chạy cho merchant này → không lưu promotions, chỉ log
            _log_jsonl("promotions.jsonl", {
                "endpoint": "promotions",
                "merchant": m,
                "ok": True,
                "items_count": len(promos),
                "skip_reason": "no_running_approved_campaign",
            })
            continue

        # upsert bảng promotions (CHỈ khi có campaign đã APPROVED)
        for p in promos:
            try:
                # Phân loại các trường chuỗi
                name_val = _classify_str(p, "name")
                # content ưu tiên content; nếu thiếu content nhưng có description thì dùng description thực
                if ("content" not in p or not (p.get("content") or "").strip()) and (p.get("description") or "").strip():
                    content_val = str(p.get("description")).strip()
                else:
                    content_val = _classify_str(p, "content")
                coupon_val = _classify_str(p, "coupon")
                # link ưu tiên 'link' > 'url'; nếu cả hai thiếu → phân loại theo key
                if ("link" not in p or not (p.get("link") or "").strip()) and (p.get("url") or "").strip():
                    link_val = str(p.get("url")).strip()
                else:
                    link_val = _classify_str(p, "link")

                start_time = p.get("start_time")
                end_time = p.get("end_time")

                # Không truyền placeholder; None được phép trong schema/model
                crud.upsert_promotion(db, schemas.PromotionCreate(
                    campaign_id=cid_pick,
                    name=name_val,
                    content=content_val,
                    start_time=start_time,
                    end_time=end_time,
                    coupon=coupon_val,
                    link=link_val,
                ))
                imported_promos += 1

                # Không còn auto tạo ProductOffer từ Promotions
            except Exception as e:
                logger.debug("Skip promotion/offer upsert: %s", e)

        # nghỉ giữa các merchant nếu có cấu hình throttle_ms
        sleep_ms = getattr(req, "throttle_ms", 0) or 0
        if sleep_ms:
            await asyncio.sleep(sleep_ms / 1000.0)

    return {"ok": True, "promotions": imported_promos}

"""Legacy provider-specific routes have been removed. Use unified endpoints."""

async def ingest_v2_top_products(
    req: IngestV2TopProductsReq,
    db: Session = Depends(get_db),
):
    from accesstrade_service import fetch_top_products, fetch_active_campaigns, _check_url_alive

    # 0) Lấy map campaign đang chạy {campaign_id: merchant}
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

    # Xây danh sách merchants đã APPROVED & running
    approved_running_merchants: set[str] = set()
    for cid, m in active.items():
        row = crud.get_campaign_by_cid(db, cid)
        if not row:
            continue
        us = (row.user_registration_status or "").upper()
        if us == "SUCCESSFUL":
            us = "APPROVED"
        if us == "APPROVED" and (row.status or "").lower() == "running":
            approved_running_merchants.add((m or "").lower())

    # Toàn bộ merchants đang active (chỉ xét running theo API)
    all_active_merchants: set[str] = { (m or "").lower() for m in active.values() if m }

    # Nếu truyền merchant → chỉ chạy merchant đó; nếu không → chạy tất cả merchant đã approved_running
    if req.merchant:
        merchants = {req.merchant.strip().lower()}
    else:
        merchants = set(approved_running_merchants)

    # DEFAULT date range: 30 ngày gần nhất nếu không truyền
    if not req.date_from or not req.date_to:
        from datetime import datetime, timedelta, UTC
        _to = datetime.now(UTC).date()
        _from = _to - timedelta(days=30)
        date_from_use = req.date_from or _from.strftime("%Y-%m-%d")
        date_to_use = req.date_to or _to.strftime("%Y-%m-%d")
    else:
        date_from_use = req.date_from
        date_to_use = req.date_to

    imported_total = 0
    result_by_merchant: dict[str, int] = {}
    skipped_merchants: set[str] = set()

    _alias = {"lazadacps": "lazada", "tikivn": "tiki"}

    for m_req in sorted(merchants):
        m_fetch = _alias.get(m_req, m_req)

        # map merchant -> campaign_id đang chạy
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

        if not campaign_id:
            # Không tìm thấy campaign đang chạy cho merchant này
            skipped_merchants.add(m_req)
            continue

        page = 1
        imported = 0
        while page <= max(1, req.max_pages):
            items = await fetch_top_products(
                db,
                merchant=m_fetch,
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
                    url_to_check = link or aff

                    alive = True if not req.check_urls else await _check_url_alive(str(url_to_check or ""))
                    if not alive:
                        logger.debug("[TOP] skip: dead url %s", url_to_check)
                        continue

                    base_key = str(product_id or url_to_check)
                    sid = hashlib.md5(base_key.encode("utf-8")).hexdigest()

                    extra = {
                        "source_type": "top_products",
                        "raw": it,
                    }
                    try:
                        _row = crud.get_campaign_by_cid(db, campaign_id) if campaign_id else None
                        _user = (_row.user_registration_status or "").upper() if _row else ""
                        if not _row or _user not in ("APPROVED", "SUCCESSFUL"):
                            continue
                    except Exception:
                        continue

                    payload = schemas.ProductOfferCreate(
                        source="accesstrade",
                        source_id=f"top:{m_req}:{sid}",
                        merchant=m_req,
                        title=title,
                        url=link or aff,
                        affiliate_url=aff,
                        image_url=img,
                        price=price,
                        currency="VND",
                        campaign_id=campaign_id,
                        source_type="top_products",
                        eligible_commission=bool(
                            _row and _row.status == "running" and (_row.user_registration_status or "").upper() in ("APPROVED", "SUCCESSFUL")
                        ),
                        affiliate_link_available=bool(aff),
                        product_id=str(product_id) if product_id is not None else None,
                        extra=json.dumps(extra, ensure_ascii=False),
                    )

                    try:
                        crud.upsert_offer_for_excel(db, payload)
                    except Exception:
                        crud.upsert_offer_by_source(db, payload)
                    imported += 1
                except Exception as e:
                    logger.debug("Skip top_product upsert: %s", e)

            page += 1
            sleep_ms = getattr(req, "throttle_ms", 0) or 0
            if sleep_ms:
                await asyncio.sleep(sleep_ms / 1000.0)

        imported_total += imported
        result_by_merchant[m_req] = imported

    resp = {"ok": True, "imported": imported_total, "by_merchant": result_by_merchant}
    if req.verbose:
        # Nếu không truyền merchant: coi các merchant active nhưng không approved là bị bỏ qua
        # Nếu có truyền merchant cụ thể: thêm vào skipped nếu merchant đó không thuộc approved_running
        skipped = set(skipped_merchants)
        if not req.merchant:
            skipped.update(all_active_merchants - approved_running_merchants)
        else:
            m_norm = req.merchant.strip().lower()
            if m_norm not in approved_running_merchants:
                skipped.add(m_norm)
        resp["skipped_merchants"] = sorted(skipped)
    return resp

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

class IngestCommissionsReq(ProviderReq, BaseModel):
    """
    Ingest commission policies (hoa hồng) cho campaign.
    - campaign_ids: danh sách campaign_id cần lấy. Nếu không có, chọn theo merchant hoặc tất cả campaign đang chạy đã APPROVED.
    - merchant: lọc theo merchant (nếu không truyền campaign_ids).
    - max_campaigns: giới hạn số campaign tối đa sẽ quét (để an toàn). Mặc định 100.
    - verbose: ghi log chi tiết vào JSONL.
    """
    campaign_ids: list[str] | None = None
    merchant: str | None = None
    max_campaigns: int = 100
    verbose: bool = False

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Theo campaign cụ thể",
                    "value": {"provider": "accesstrade", "campaign_ids": ["CAMP3"]}
                },
                {
                    "summary": "Theo merchant",
                    "value": {"provider": "accesstrade", "merchant": "tikivn"}
                },
                {
                    "summary": "Tất cả campaign APPROVED đang chạy",
                    "value": {"provider": "accesstrade"}
                }
            ]
        }
    }

@app.post(
    "/ingest/campaigns/sync",
    tags=["Campaigns 📢"],
    summary="Đồng bộ campaigns (provider-agnostic)",
    description=(
        "Đồng bộ danh sách campaigns.\n\n"
        "- Bắt buộc: (không có).\n"
        "- Tuỳ chọn: provider (mặc định \"accesstrade\"), statuses (mặc định [\"running\",\"paused\"]), only_my (mặc định true),\n"
        "  enrich_user_status (mặc định true), limit_per_page, page_concurrency, window_pages, throttle_ms (mặc định 50ms), merchant.\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"provider\": \"accesstrade\",\n  \"statuses\": [\"running\", \"paused\"],\n  \"only_my\": true,\n  \"throttle_ms\": 50\n}"
    )
)
async def ingest_campaigns_sync_unified(
    req: CampaignsSyncUnifiedReq = Body(
        ...,
        example={
            "provider": "accesstrade",
            "statuses": ["running", "paused"],
            "only_my": True,
            "enrich_user_status": True,
            "limit_per_page": 50,
            "page_concurrency": 6,
            "window_pages": 10,
            "throttle_ms": 50
        }
    ),
    db: Session = Depends(get_db)
):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = CampaignsSyncReq(**req.model_dump(exclude={"provider"}))
        return await ingest_v2_campaigns_sync(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

@app.post(
    "/ingest/promotions",
    tags=["Ingest 🌐"],
    summary="Ingest promotions (provider-agnostic)",
    description=(
        "Nhập khuyến mãi theo merchant.\n\n"
        "- Bắt buộc: (không có).\n"
        "- Tuỳ chọn: provider (mặc định \"accesstrade\"), merchant (lọc theo merchant), verbose (mặc định false), throttle_ms (mặc định 50ms).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"provider\": \"accesstrade\",\n  \"merchant\": \"tikivn\",\n  \"verbose\": false,\n  \"throttle_ms\": 50\n}"
    )
)
async def ingest_promotions_unified(
    req: PromotionsUnifiedReq = Body(
        ...,
        examples={
            "default": {
                "summary": "Ví dụ merchant",
                "value": {"provider": "accesstrade", "merchant": "tikivn", "verbose": False, "throttle_ms": 50}
            }
        }
    ),
    db: Session = Depends(get_db)
):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = IngestV2PromotionsReq(**req.model_dump(exclude={"provider"}))
        return await ingest_v2_promotions(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

@app.post(
    "/ingest/top-products",
    tags=["Ingest 🌐"],
    summary="Ingest top products (provider-agnostic)",
    description=(
        "Nhập sản phẩm bán chạy theo merchant.\n\n"
        "- Bắt buộc: (không có). Nếu không truyền merchant, hệ thống sẽ chạy cho TẤT CẢ merchant có campaign đang chạy và đã duyệt (APPROVED/SUCCESSFUL).\n"
        "- Tuỳ chọn: provider (mặc định \"accesstrade\"), date_from/date_to (YYYY-MM-DD), limit_per_page (<=100),\n"
        "  max_pages, check_urls (mặc định false), verbose (mặc định false), throttle_ms (mặc định 50ms).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"provider\": \"accesstrade\",\n  \"merchant\": \"tikivn\",\n  \"limit_per_page\": 50,\n  \"max_pages\": 1,\n  \"check_urls\": false,\n  \"verbose\": false,\n  \"throttle_ms\": 50\n}"
    )
)
async def ingest_top_products_unified(
    req: TopProductsUnifiedReq = Body(
        ...,
        examples={
            "default": {
                "summary": "Top products 1 trang",
                "value": {"provider": "accesstrade", "merchant": "tikivn", "limit_per_page": 50, "max_pages": 1, "check_urls": False, "verbose": False, "throttle_ms": 50}
            }
        }
    ),
    db: Session = Depends(get_db)
):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = IngestV2TopProductsReq(**req.model_dump(exclude={"provider"}))
        return await ingest_v2_top_products(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

@app.post(
    "/ingest/datafeeds/all",
    tags=["Ingest 🌐"],
    summary="Ingest datafeeds toàn bộ (provider-agnostic)",
    description=(
        "Gọi datafeeds cho tất cả merchant đã duyệt.\n\n"
        "- Bắt buộc: (không có).\n"
        "- Tuỳ chọn: provider (mặc định \"accesstrade\"), params (truyền xuống API AT), limit_per_page (mặc định 100),\n"
        "  max_pages (mặc định 2000), check_urls (mặc định false), verbose (mặc định false), throttle_ms (mặc định 50ms).\n\n"
        "Ví dụ body JSON:\n"
        "{\n  \"provider\": \"accesstrade\",\n  \"params\": {\"merchant\": \"tikivn\"},\n  \"max_pages\": 1,\n  \"check_urls\": false,\n  \"verbose\": false,\n  \"throttle_ms\": 50\n}"
    )
)
async def ingest_datafeeds_all_unified(
    req: DatafeedsAllUnifiedReq = Body(
        ...,
        examples={
            "default": {
                "summary": "Quét toàn bộ đã duyệt",
                "value": {"provider": "accesstrade", "params": {"merchant": "tikivn"}, "max_pages": 1, "check_urls": False, "verbose": False, "throttle_ms": 50}
            }
        }
    ),
    db: Session = Depends(get_db)
):
    prov = (req.provider or "accesstrade").lower()
    if prov == "accesstrade":
        inner = IngestAllDatafeedsReq(**req.model_dump(exclude={"provider"}))
        return await ingest_accesstrade_datafeeds_all(inner, db)
    raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

"""Legacy provider-specific routes have been removed. Use unified endpoints."""

@app.post(
    "/ingest/commissions",
    tags=["Ingest 🌐"],
    summary="Ingest commission policies (hoa hồng)",
    description=(
        "Gọi datafeeds commissions cho danh sách campaign đã chọn.\n\n"
        "- Bắt buộc: (không có).\n"
        "- Tuỳ chọn: provider (mặc định 'accesstrade'), campaign_ids (danh sách), merchant (lọc theo merchant nếu không truyền campaign_ids),\n"
        "  max_campaigns (mặc định 100), verbose (mặc định false).\n\n"
        "Ví dụ body JSON: { \"provider\": \"accesstrade\", \"merchant\": \"tikivn\", \"max_campaigns\": 50 }"
    )
)
async def ingest_commissions_unified(
    req: IngestCommissionsReq = Body(
        ...,
        examples={
            "by_campaign": {
                "summary": "Theo campaign cụ thể",
                "value": {"provider": "accesstrade", "campaign_ids": ["CAMP3"]},
            },
            "by_merchant": {
                "summary": "Theo merchant",
                "value": {"provider": "accesstrade", "merchant": "tikivn"},
            },
            "all_running": {
                "summary": "Tất cả campaign APPROVED đang chạy",
                "value": {"provider": "accesstrade"},
            },
        },
    ),
    db: Session = Depends(get_db),
):
    from accesstrade_service import fetch_active_campaigns, fetch_commission_policies
    prov = (req.provider or "accesstrade").lower()
    if prov != "accesstrade":
        raise HTTPException(status_code=400, detail=f"Provider '{prov}' hiện chưa được hỗ trợ")

    # Xác định danh sách campaign_id cần lấy
    campaign_ids: list[str] = []
    if req.campaign_ids:
        campaign_ids = [str(c).strip() for c in req.campaign_ids if str(c).strip()]
    else:
        # tất cả campaign đang chạy đã APPROVED (hoặc lọc theo merchant)
        active = await fetch_active_campaigns(db)  # {cid: merchant}
        for cid, m in active.items():
            row = crud.get_campaign_by_cid(db, cid)
            if not row:
                continue
            us = (row.user_registration_status or "").upper()
            if us == "SUCCESSFUL":
                us = "APPROVED"
            if us != "APPROVED":
                continue
            if req.merchant and (m or "").lower() != req.merchant.strip().lower():
                continue
            campaign_ids.append(cid)
        if req.max_campaigns and len(campaign_ids) > req.max_campaigns:
            campaign_ids = campaign_ids[: max(1, int(req.max_campaigns))]

    imported = 0
    for cid in campaign_ids:
        try:
            items = await fetch_commission_policies(db, cid)
            for rec in (items or []):
                crud.upsert_commission_policy(db, schemas.CommissionPolicyCreate(
                    campaign_id=str(cid),
                    reward_type=rec.get("reward_type") or rec.get("type"),
                    sales_ratio=rec.get("sales_ratio") or rec.get("ratio"),
                    sales_price=rec.get("sales_price"),
                    target_month=rec.get("target_month"),
                ))
                imported += 1
        except Exception as e:
            if req.verbose:
                logger.debug("Ingest commission failed for %s: %s", cid, e)
            continue

    return {"ok": True, "campaigns": len(campaign_ids), "policies_imported": imported}

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
def update_offer_api(
    offer_id: int,
    data: schemas.ProductOfferUpdate = Body(
        ...,
        examples={
            "patch-minimal": {
                "summary": "Cập nhật một phần",
                "value": {"title": "Sản phẩm mới", "price": 199000, "currency": "VND"}
            }
        }
    ),
    db: Session = Depends(get_db)
):
    obj = crud.update_offer(db, offer_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Offer not found")
    return obj

@app.delete(
    "/offers/{offer_id}",
    tags=["Offers 🛒"],
    summary="Xoá 1 bản ghi theo ID",
    description=(
        "Xoá một bản ghi duy nhất theo ID.\n\n"
        "- category: offers (mặc định) | top-products | promotions | commissions.\n"
        "- Lưu ý: bulk delete theo campaign_id hãy dùng DELETE /offers (không kèm {offer_id})."
    )
)
def delete_offer_api(
    offer_id: int,
    category: Literal["offers", "top-products", "promotions", "commissions"] = Query(
        "offers", description="offers | top-products | promotions | commissions"
    ),
    db: Session = Depends(get_db)
):
    cat = (category or "offers").strip().lower()
    if cat in ("offers", "top-products"):
        obj = crud.delete_offer(db, offer_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Offer not found")
        return {"ok": True, "deleted_id": offer_id, "category": "top-products" if cat == "top-products" else "offers"}
    elif cat == "promotions":
        obj = crud.delete_promotion(db, offer_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Promotion not found")
        return {"ok": True, "deleted_id": offer_id, "category": "promotions"}
    elif cat == "commissions":
        obj = crud.delete_commission_policy(db, offer_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Commission policy not found")
        return {"ok": True, "deleted_id": offer_id, "category": "commissions"}
    else:
        raise HTTPException(status_code=400, detail="category không hợp lệ")

# --- API cleanup: xóa sản phẩm có link chết ---
@app.delete(
    "/offers/cleanup/dead",
    tags=["Offers 🛒"],
    summary="Dọn link chết (cleanup)",
    description=(
        "Bắt buộc: (không có).\n"
        "Tác vụ quét toàn bộ sản phẩm trong DB, kiểm tra link sống/chết và **xoá tất cả** link chết."
    )
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
    tags=["Settings ⚙️"],
    summary="Kiểm tra link sống theo lát cắt và xoay vòng",
    description=(
        "Cách dùng: gọi 1 lần sẽ kiểm tra một lát cắt theo điều kiện id % M = cursor.\n"
        "- Bắt buộc: (không có) — endpoint không yêu cầu body.\n"
        "- Tuỳ chọn: query delete_dead=true để xoá link chết trong lát hiện tại.\n"
        "- M: số lát cắt (mặc định 24 do hệ thống đặt sẵn — có thể đổi qua /settings/linkcheck/config).\n"
        "- linkcheck_limit: giới hạn số bản ghi mỗi lần (đặt qua /settings/linkcheck/config).\n"
        "Sau mỗi lần chạy, cursor tự tăng (mod M)."
    )
)
async def scheduler_linkcheck_rotate(
    delete_dead: bool = False,
    db: Session = Depends(get_db),
):
    from accesstrade_service import _check_url_alive
    flags = crud.get_policy_flags(db)
    mod = int(flags.get("linkcheck_mod", 10) or 10)
    if mod < 1:
        mod = 10
    cursor = int(flags.get("linkcheck_cursor", 0)) % mod
    limit = flags.get("linkcheck_limit")

    from models import ProductOffer
    # lọc theo modulo tuỳ biến
    slice_q = db.query(ProductOffer).filter(text("id % :mod = :cur")).params(mod=mod, cur=cursor)
    if isinstance(limit, int) and limit > 0:
        slice_q = slice_q.limit(limit)
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

    next_cursor = (cursor + 1) % mod
    crud.set_policy_flag(db, "linkcheck_cursor", next_cursor)

    return {
        "cursor_used": cursor,
        "next_cursor": next_cursor,
        "mod": mod,
        "limit": limit,
        "scanned": total,
        "alive": alive_count,
        "deleted": removed,
    }

class LinkcheckConfigBody(BaseModel):
    linkcheck_mod: int | None = None
    linkcheck_limit: int | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"linkcheck_mod": 24, "linkcheck_limit": 1000},
                {"linkcheck_mod": 20},
                {"linkcheck_limit": 500},
            ],
            "description": (
                "Bắt buộc: không có trường nào bắt buộc.\n"
                "- linkcheck_mod (tuỳ chọn): số lát cắt (ví dụ 24 → 1/24 mỗi lần).\n"
                "- linkcheck_limit (tuỳ chọn): giới hạn số record mỗi lần."
            ),
        }
    }

@app.post(
    "/settings/linkcheck/config",
    tags=["Settings ⚙️"],
    summary="Cấu hình tham số link-check (mod/limit)",
    description=(
        "Thiết lập tham số xoay vòng kiểm tra link.\n"
        "- Bắt buộc: (không có).\n"
        "- Tuỳ chọn trong body JSON: linkcheck_mod, linkcheck_limit.\n"
        "Ngoài ra có thể gửi qua query string (tương thích ngược). Giá trị được lưu trong API Config name=ingest_policy.\n\n"
        "Ví dụ body JSON:\n{\n  \"linkcheck_mod\": 24,\n  \"linkcheck_limit\": 1000\n}"
    )
)
def settings_linkcheck_config(
    body: LinkcheckConfigBody | None = Body(
        None,
        examples={
            "default": {"summary": "Thiết lập mặc định 24/1000", "value": {"linkcheck_mod": 24, "linkcheck_limit": 1000}},
            "gioi_han_nho": {"summary": "Giới hạn 500 mỗi lượt", "value": {"linkcheck_limit": 500}}
        }
    ),
    linkcheck_mod: int | None = None,
    linkcheck_limit: int | None = None,
    db: Session = Depends(get_db),
):
    # Ưu tiên body; nếu không có, lấy từ query để tương thích ngược
    mod_val = body.linkcheck_mod if body else linkcheck_mod
    limit_val = body.linkcheck_limit if body else linkcheck_limit
    if mod_val is not None:
        crud.set_policy_flag(db, "linkcheck_mod", max(1, int(mod_val)))
    if limit_val is not None:
        crud.set_policy_flag(db, "linkcheck_limit", max(1, int(limit_val)))
    flags = crud.get_policy_flags(db)
    return {"ok": True, "flags": flags}

# --- API test nhanh: check 1 sản phẩm trong DB ---
from datetime import datetime, UTC

@app.get(
    "/offers/check/{offer_id}",
    tags=["Offers 🛒"],
    summary="Kiểm tra 1 sản phẩm (alive/dead)",
    description=(
        "Bắt buộc: offer_id trong path.\n"
        "Tuỳ chọn: (không có).\n"
        "Kiểm tra nhanh trạng thái link của một sản phẩm trong DB theo ID."
    )
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
    summary="Xoá dữ liệu theo nhóm (bulk)",
    description=(
        "Xoá nhiều bản ghi theo nhóm và (tuỳ chọn) campaign_id.\n\n"
        "- category: offers (mặc định) | top-products | promotions | commissions.\n"
        "- Với category=offers: sẽ xoá tất cả ProductOffer TRỪ nhóm top-products (bao gồm cả các offer có source_type='promotions').\n"
        "- Dùng campaign_id để giới hạn theo chiến dịch."
    )
)
def delete_all_offers_api(
    category: Literal["offers", "top-products", "promotions", "commissions"] = Query(
        "offers", description="offers | top-products | promotions | commissions"
    ),
    campaign_id: str | None = Query(None, description="Xoá theo campaign_id (tuỳ chọn)"),
    db: Session = Depends(get_db)
):
    cat = (category or "offers").strip().lower()
    deleted = 0
    if cat in ("offers", "top-products"):
        if cat in ("top-products",):
            deleted = crud.delete_offers_by_filter(db, source_type="top_products", campaign_id=campaign_id)
            effective_cat = "top-products"
        else:
            # Xoá tất cả offer nhưng loại trừ nhóm top-products; giữ lại promotions-source để xoá được theo campaign
            if campaign_id:
                deleted = crud.delete_offers_by_filter(db, exclude_source_types=["top_products"], campaign_id=campaign_id)
            else:
                deleted = crud.delete_offers_by_filter(db, exclude_source_types=["top_products"])
            effective_cat = "offers"
    elif cat == "promotions":
        deleted = crud.delete_promotions_by_campaign(db, campaign_id) if campaign_id else crud.delete_all_promotions(db)
        effective_cat = "promotions"
    elif cat == "commissions":
        deleted = crud.delete_commission_policies_by_campaign(db, campaign_id) if campaign_id else crud.delete_all_commission_policies(db)
        effective_cat = "commissions"
    else:
        raise HTTPException(status_code=400, detail="category không hợp lệ")
    return {"ok": True, "deleted": deleted, "category": effective_cat}

# ---- Catalog listing for other categories ----
@app.get(
    "/catalog/promotions",
    tags=["Offers 🛒"],
    response_model=list[schemas.PromotionOut],
    summary="Liệt kê promotions",
    description="Danh sách promotions trong DB (phân trang)."
)
def list_catalog_promotions(
    skip: int = 0,
    limit: int = 50,
    campaign_id: str | None = Query(None, description="Lọc theo campaign_id (tuỳ chọn)"),
    db: Session = Depends(get_db)
):
    return crud.list_promotions(db, skip=skip, limit=limit, campaign_id=campaign_id)

@app.get(
    "/catalog/commissions",
    tags=["Offers 🛒"],
    response_model=list[schemas.CommissionPolicyOut],
    summary="Liệt kê commission policies",
    description="Danh sách chính sách hoa hồng theo chiến dịch (phân trang)."
)
def list_catalog_commissions(
    skip: int = 0,
    limit: int = 50,
    campaign_id: str | None = Query(None, description="Lọc theo campaign_id (tuỳ chọn)"),
    db: Session = Depends(get_db)
):
    return crud.list_commission_policies(db, skip=skip, limit=limit, campaign_id=campaign_id)

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

    # Đọc toàn bộ nội dung file một lần để parse nhiều sheet an toàn
    try:
        content = file.file.read()
        xls = pd.ExcelFile(io.BytesIO(content))
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

    # Helper: kiểm tra 2 hàng header và bỏ hàng TV cho một DataFrame
    def _validate_and_strip_header(df: pd.DataFrame, trans_map: dict, sheet_name: str):
        if df.empty:
            raise HTTPException(status_code=400, detail=f"Sheet {sheet_name} trống hoặc không đúng định dạng (thiếu dữ liệu)")
        first = df.iloc[0]
        matches = 0
        total_keys = 0
        for k, v in trans_map.items():
            if k in df.columns:
                total_keys += 1
                try:
                    def _norm_header(s: str) -> str:
                        s = str(s or "").strip()
                        return s.replace("(*)", "").replace("( * )", "").replace("(*) ", "").strip()
                    if _norm_header(str(first[k])) == _norm_header(str(v)):
                        matches += 1
                except Exception:
                    pass
        threshold = max(3, total_keys // 3)
        if not (total_keys and matches >= threshold):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Sheet {sheet_name}: thiếu hàng tiêu đề tiếng Việt (hàng 2). "
                    "Mọi sheet phải có 2 hàng tiêu đề: hàng 1 là tên cột kỹ thuật, hàng 2 là tên cột tiếng Việt."
                ),
            )
        return df.iloc[1:].reset_index(drop=True)

    # Helper: sinh mã theo format ex+prefix+digits tổng độ dài 14; đảm bảo không trùng cho Products
    import secrets, string
    def _gen_code(prefix: str, exists_check=None, max_tries: int = 20) -> str:
        base = "ex" + prefix
        digits_len = max(1, 14 - len(base))
        for _ in range(max_tries):
            n = ''.join(secrets.choice(string.digits) for _ in range(digits_len))
            code = base + n
            if exists_check is None:
                return code
            if not exists_check(code):
                return code
        # fallback: vẫn trả về code cuối cùng nếu quá số lần thử
        return code
    # Lấy sheet Products nếu có; nếu không có, fallback sheet đầu tiên để tương thích
    if "Products" in xls.sheet_names:
        df_products = xls.parse("Products")
    else:
        df_products = xls.parse(0)

    # Xác thực header cho Products
    df = _validate_and_strip_header(df_products, trans_products, "Products")

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

        # Auto-generate source_id nếu thiếu: theo format ex + 'p' + số ngẫu nhiên (độ dài tổng 14)
        if not base["source_id"]:
            def _exists_in_db(sid: str) -> bool:
                from sqlalchemy import select
                from models import ProductOffer
                stmt = select(ProductOffer.id).where(ProductOffer.source == "excel", ProductOffer.source_id == sid)
                return db.execute(stmt).first() is not None
            base["source_id"] = _gen_code("p", exists_check=_exists_in_db)

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

        # Các cột mở rộng trong ảnh: domain, sku, discount, discount_amount, discount_rate, status_discount, updated_at, desc, cate, shop_name, update_time_raw
        extra_fields = {
            "domain": row.get("domain"),
            "sku": row.get("sku"),
            "discount": row.get("discount"),
            "discount_amount": row.get("discount_amount"),
            "discount_rate": row.get("discount_rate"),
            "status_discount": row.get("status_discount"),
            "updated_at": row.get("updated_at"),
            "desc": row.get("desc"),
            "cate": row.get("cate"),
            "shop_name": row.get("shop_name"),
            "update_time_raw": row.get("update_time_raw"),
        }
        # Lọc bỏ các giá trị NaN
        extra_fields = {k: v for k, v in extra_fields.items() if pd.notna(v)}

        # Gộp vào extra (không còn xuất extra_raw trong Excel, nhưng DB vẫn giữ extra nếu có)
        extra = {}
        if promotion:
            extra["promotion"] = promotion
        if commission:
            extra["commission"] = commission
        # Thêm các trường mở rộng
        for k, v in extra_fields.items():
            extra[k] = v
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

        # affiliate_url: nếu file có thì ưu tiên giữ đúng theo file; nếu không có và có url + template → auto convert
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

        # Dùng upsert đặc thù cho Excel: ưu tiên cập nhật theo source_id (bất kể source hiện có)
        try:
            crud.upsert_offer_for_excel(db, data)
        except Exception:
            # fallback an toàn nếu hàm mới không khả dụng
            crud.upsert_offer_by_source(db, data)
        imported += 1

    # =========================
    # IMPORT: Campaigns sheet
    # =========================
    imported_campaigns = 0
    if "Campaigns" in xls.sheet_names:
        trans_campaigns = {
            "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "campaign_name": "Tên chiến dịch",
            "approval_type": "Approval", "user_status": "Trạng thái của tôi", "status": "Tình trạng",
            "start_time": "Bắt đầu", "end_time": "Kết thúc",
            "category": "Danh mục chính", "conversion_policy": "Chính sách chuyển đổi",
            "cookie_duration": "Hiệu lực cookie (giây)", "cookie_policy": "Chính sách cookie",
            "description_url": "Mô tả (Web)", "scope": "Phạm vi", "sub_category": "Danh mục phụ",
            "type": "Loại", "campaign_url": "URL chiến dịch",
        }
        df_camp_raw = xls.parse("Campaigns")
        df_camp = _validate_and_strip_header(df_camp_raw, trans_campaigns, "Campaigns")

        # set dùng để tránh sinh trùng trong cùng file
        generated_ids_camp: set[str] = set()
        for _, row in df_camp.iterrows():
            cid = row.get("campaign_id")
            cid = str(cid).strip() if pd.notna(cid) else None
            if not cid:
                def _exists_campaign(c: str) -> bool:
                    return crud.get_campaign_by_cid(db, c) is not None or (c in generated_ids_camp)
                cid = _gen_code("ca", exists_check=_exists_campaign)
                generated_ids_camp.add(cid)
            try:
                payload = schemas.CampaignCreate(
                    campaign_id=cid,
                    merchant=(str(row.get("merchant")).strip().lower() if pd.notna(row.get("merchant")) else None),
                    name=(str(row.get("campaign_name")).strip() if pd.notna(row.get("campaign_name")) else None),
                    status=(str(row.get("status")).strip() if pd.notna(row.get("status")) else None),
                    approval=(str(row.get("approval_type")).strip() if pd.notna(row.get("approval_type")) else None),
                    start_time=(str(row.get("start_time")).strip() if pd.notna(row.get("start_time")) else None),
                    end_time=(str(row.get("end_time")).strip() if pd.notna(row.get("end_time")) else None),
                    user_registration_status=(str(row.get("user_status")).strip() if pd.notna(row.get("user_status")) else None),
                )
                crud.upsert_campaign(db, payload)
                imported_campaigns += 1
            except Exception:
                continue

    # =========================
    # IMPORT: Commissions sheet
    # =========================
    imported_commissions = 0
    if "Commissions" in xls.sheet_names:
        trans_commissions = {
            "id": "Mã ID",
            "campaign_id": "Mã chiến dịch", "reward_type": "Kiểu thưởng", "sales_ratio": "Tỷ lệ (%)",
            "sales_price": "Hoa hồng cố định", "target_month": "Tháng áp dụng",
        }
        df_comm_raw = xls.parse("Commissions")
        df_comm = _validate_and_strip_header(df_comm_raw, trans_commissions, "Commissions")

        # Nếu có cột id: ưu tiên cập nhật theo ID để tránh phát sinh trùng; nếu không có thì upsert theo (campaign_id,reward_type,target_month)
        for _, row in df_comm.iterrows():
            cid = row.get("campaign_id")
            cid = str(cid).strip() if pd.notna(cid) else None
            if not cid:
                # Không yêu cầu uniqueness tuyệt đối với campaign_id ảo trong bảng commissions, nhưng tránh va chạm nhẹ
                cid = _gen_code("cm")
            try:
                payload = schemas.CommissionPolicyCreate(
                    campaign_id=cid,
                    reward_type=(str(row.get("reward_type")).strip() if pd.notna(row.get("reward_type")) else None),
                    sales_ratio=(float(row.get("sales_ratio")) if pd.notna(row.get("sales_ratio")) else None),
                    sales_price=(float(row.get("sales_price")) if pd.notna(row.get("sales_price")) else None),
                    target_month=(str(row.get("target_month")).strip() if pd.notna(row.get("target_month")) else None),
                )
                _id_val = row.get("id")
                if pd.notna(_id_val):
                    try:
                        _id_int = int(_id_val)
                    except Exception:
                        _id_int = None
                else:
                    _id_int = None
                if _id_int:
                    # cập nhật theo ID, bỏ qua giá trị rỗng trong payload (đã xử lý ở CRUD)
                    updated = crud.update_commission_policy_by_id(db, _id_int, payload)
                    if updated is None:
                        # nếu ID không tồn tại → fallback upsert theo khóa nghiệp vụ
                        crud.upsert_commission_policy(db, payload)
                else:
                    crud.upsert_commission_policy(db, payload)
                imported_commissions += 1
            except Exception:
                continue

    # =========================
    # IMPORT: Promotions sheet
    # =========================
    imported_promotions = 0
    if "Promotions" in xls.sheet_names:
        trans_promotions = {
            "id": "Mã ID",
            "campaign_id": "Mã chiến dịch", "merchant": "Nhà bán", "name": "Tên khuyến mãi", "content": "Nội dung",
            "start_time": "Bắt đầu KM", "end_time": "Kết thúc KM", "coupon": "Mã giảm", "link": "Link khuyến mãi",
        }
        df_prom_raw = xls.parse("Promotions")
        df_prom = _validate_and_strip_header(df_prom_raw, trans_promotions, "Promotions")

        for _, row in df_prom.iterrows():
            cid = row.get("campaign_id")
            cid = str(cid).strip() if pd.notna(cid) else None
            if not cid:
                cid = _gen_code("pr")
            try:
                payload = schemas.PromotionCreate(
                    campaign_id=cid,
                    name=(str(row.get("name")).strip() if pd.notna(row.get("name")) else None),
                    content=(str(row.get("content")).strip() if pd.notna(row.get("content")) else None),
                    start_time=(row.get("start_time") if pd.notna(row.get("start_time")) else None),
                    end_time=(row.get("end_time") if pd.notna(row.get("end_time")) else None),
                    coupon=(str(row.get("coupon")).strip() if pd.notna(row.get("coupon")) else None),
                    link=(str(row.get("link")).strip() if pd.notna(row.get("link")) else None),
                )
                _id_val = row.get("id")
                if pd.notna(_id_val):
                    try:
                        _id_int = int(_id_val)
                    except Exception:
                        _id_int = None
                else:
                    _id_int = None
                if _id_int:
                    updated = crud.update_promotion_by_id(db, _id_int, payload)
                    if updated is None:
                        crud.upsert_promotion(db, payload)
                else:
                    crud.upsert_promotion(db, payload)
                imported_promotions += 1
            except Exception:
                continue

    result = {
        "ok": True,
        "imported": imported,  # backward-compatible: số sản phẩm Products
        "campaigns": imported_campaigns,
        "commissions": imported_commissions,
        "promotions": imported_promotions,
    }
    if required_errors:
        result.update({
            "skipped_required": skipped_required,
            "errors": required_errors[:50]
        })
    return result

# --- Export sản phẩm từ DB ra file Excel ---
@app.get(
    "/offers/export-excel",
    tags=["Offers 🛒"],
    summary="Xuất Excel chuyên biệt (Products/Campaigns/Commissions/Promotions)",
    description=(
        "Xuất Excel gồm 4 sheet độc lập. Products chỉ gồm sản phẩm gốc (datafeeds/top-products/manual/excel) và có cột source_type; "
        "Campaigns chỉ các campaign đã APPROVED/SUCCESSFUL; Commissions/Promotions độc lập, không phụ thuộc sản phẩm."
    )
)
def export_offers_excel(
    merchant: str | None = None,
    title: str | None = None,
    skip: int = 0,
    limit: int = 0,  # nếu =0 thì xuất toàn bộ
    max_text_len: int | None = None,  # tuỳ chọn: giới hạn ký tự cho các trường văn bản dài
    db: Session = Depends(get_db)
):
    import os, json
    import pandas as pd
    from collections import defaultdict

    # 1) Products: chỉ lấy offers gốc (datafeeds/top-products/manual/excel) — KHÔNG bao gồm promotions-source
    q_offers = db.query(models.ProductOffer).filter(
        models.ProductOffer.source_type.in_(["datafeeds", "top_products", "manual", "excel"])  # loại bỏ "promotions"
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

    # 2) Campaigns: độc lập, chỉ APPROVED/SUCCESSFUL (chuẩn hoá theo uppercase/trim)
    norm_user = func.upper(func.trim(models.Campaign.user_registration_status))
    campaigns_all = (
        db.query(models.Campaign)
        .filter(norm_user.in_(["APPROVED", "SUCCESSFUL"]))
        .order_by(models.Campaign.campaign_id.asc())
        .all()
    )
    campaign_map = {c.campaign_id: c for c in campaigns_all}

    # 3) Commissions: độc lập, lấy từ bảng CommissionPolicy
    commissions_all = db.query(models.CommissionPolicy).all()

    # 4) Promotions: độc lập, lấy từ bảng Promotion (kèm merchant từ campaign nếu có)
    promotions_all = db.query(models.Promotion).all()

    # Helper: sanitize values for Excel XML (remove control chars, limit length)
    import re
    _illegal_xml_re = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
    def _sanitize_val(v):
        import datetime as _dt
        if v is None:
            return None
        # Convert dict/list to JSON string
        if isinstance(v, (dict, list)):
            try:
                v = json.dumps(v, ensure_ascii=False)
            except Exception:
                v = str(v)
        # Convert datetime to ISO
        if hasattr(v, 'isoformat') and not isinstance(v, str):
            try:
                v = v.isoformat()
            except Exception:
                v = str(v)
        s = str(v)
        # Remove illegal XML control characters and truncate to Excel cell limit
        s = _illegal_xml_re.sub(" ", s)
        # Ngăn Excel hiểu nhầm chuỗi là công thức (='+-@) → prefix bằng dấu nháy đơn
        if s and s[0] in ("=", "+", "-", "@"):
            s = "'" + s
        # Giới hạn độ dài: ưu tiên max_text_len nếu được truyền, ngược lại 32K (giới hạn Excel ~32767)
        _limit = 32000 if (max_text_len is None or max_text_len <= 0) else max_text_len
        if len(s) > _limit:
            s = s[:_limit]
        return s

    # Helper: strip HTML to plain text (simple, dependency-free)
    def _strip_html(val):
        if val in (None, "", []):
            return None
        try:
            import re, html as _html
            s = str(val)
            # Remove script/style blocks
            s = re.sub(r"<\s*(script|style)[^>]*>[\s\S]*?<\s*/\s*\1\s*>", " ", s, flags=re.IGNORECASE)
            # Remove all tags
            s = re.sub(r"<[^>]+>", " ", s)
            # Unescape HTML entities
            s = _html.unescape(s)
            # Collapse whitespace
            s = re.sub(r"\s+", " ", s).strip()
            return s
        except Exception:
            return str(val)

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
            return None
        if field_name == "end_time" and rec.get("has_end_time") is False:
            return None
        if field_name == "user_registration_status" and rec.get("has_user_status") is False:
            return None
        if rec.get("empty") is True:
            return None
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
                    return None
                v = data.get(field_name, None)
                return v if v not in (None, "", []) else None
        return None

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
            "merchant": _sanitize_val(o.merchant),
            "title": _sanitize_val(o.title),
            "url": _sanitize_val(o.url),
            "affiliate_url": _sanitize_val(o.affiliate_url),
            "image_url": _sanitize_val(o.image_url),
            "price": o.price,
            "currency": _sanitize_val(o.currency),
            "campaign_id": o.campaign_id,
            "product_id": _sanitize_val(extra.get("product_id") or getattr(o, "product_id", None)),
            "affiliate_link_available": o.affiliate_link_available,
            "domain": _sanitize_val(extra.get("domain")),
            "sku": _sanitize_val(extra.get("sku")),
            "discount": extra.get("discount"),
            "discount_amount": extra.get("discount_amount"),
            "discount_rate": extra.get("discount_rate"),
            "status_discount": extra.get("status_discount"),
            "updated_at": _sanitize_val(o.updated_at.isoformat() if o.updated_at else None),
            "desc": _sanitize_val(extra.get("desc")),
            "cate": _sanitize_val(extra.get("cate")),
            "shop_name": _sanitize_val(extra.get("shop_name")),
            "update_time_raw": _sanitize_val(extra.get("update_time_raw") or extra.get("update_time")),
        })

    # ---------------------------
    # Build Campaigns rows (independent)
    # ---------------------------
    df_campaigns_rows = []
    # Chuẩn bị base URL công khai (nếu có) để tạo link mở trình duyệt
    PUBLIC_BASE = os.getenv("EXPORT_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or "http://localhost:8000"

    for idx, c in enumerate(campaigns_all, start=1):
        cid = c.campaign_id
        _desc_raw = _campaign_field_from_log(cid, "description")
        has_desc = bool(_strip_html(_desc_raw))
        df_campaigns_rows.append({
            "campaign_id": c.campaign_id,
            "merchant": _sanitize_val(c.merchant),
            "campaign_name": _sanitize_val(c.name),
            "approval_type": _sanitize_val(c.approval),
            "user_status": _sanitize_val(c.user_registration_status),
            "status": _sanitize_val(c.status or _campaign_field_from_log(cid, "status")),
            "start_time": _sanitize_val(c.start_time),
            "end_time": _sanitize_val(c.end_time if c.end_time else _campaign_field_from_log(cid, "end_time")),
            "category": _sanitize_val(_campaign_field_from_log(cid, "category")),
            "conversion_policy": _sanitize_val(_campaign_field_from_log(cid, "conversion_policy")),
            "cookie_duration": _sanitize_val(_campaign_field_from_log(cid, "cookie_duration")),
            "cookie_policy": _sanitize_val(_campaign_field_from_log(cid, "cookie_policy")),
            # Chỉ tạo link ngoài nếu thực sự có mô tả
            "description_url": (f"{PUBLIC_BASE}/campaigns/{cid}/description" if (PUBLIC_BASE and has_desc) else None),
            "scope": _sanitize_val(_campaign_field_from_log(cid, "scope")),
            "sub_category": _sanitize_val(_campaign_field_from_log(cid, "sub_category")),
            "type": _sanitize_val(_campaign_field_from_log(cid, "type")),
            "campaign_url": _sanitize_val(_campaign_field_from_log(cid, "url")),
        })

    # ---------------------------
    # Build Commissions rows (independent)
    # ---------------------------
    df_commissions_rows = []
    for cp in commissions_all:
        df_commissions_rows.append({
            "id": cp.id,
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
            "id": pr.id,
            "campaign_id": pr.campaign_id,
            "merchant": _sanitize_val(m),
            "name": _sanitize_val(pr.name),
            "content": _sanitize_val(pr.content),
            "start_time": _sanitize_val(pr.start_time),
            "end_time": _sanitize_val(pr.end_time),
            "coupon": _sanitize_val(pr.coupon),
            "link": _sanitize_val(pr.link),
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
        "description_url": "Mô tả (Web)", "scope": "Phạm vi", "sub_category": "Danh mục phụ",
        "type": "Loại", "campaign_url": "URL chiến dịch",
    }
    trans_commissions = {
        "id": "Mã ID",
        "campaign_id": "Mã chiến dịch", "reward_type": "Kiểu thưởng", "sales_ratio": "Tỷ lệ (%)",
        "sales_price": "Hoa hồng cố định", "target_month": "Tháng áp dụng",
    }
    trans_promotions = {
        "id": "Mã ID",
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
    # Tắt auto-detect công thức/URL của xlsxwriter để tránh Excel tự tạo công thức hoặc hyperlink
    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_formulas": False, "strings_to_urls": False}},
    ) as writer:
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

        # Re-add clickable hyperlinks explicitly for known URL columns
        wb = writer.book
        url_format = wb.add_format({"font_color": "blue", "underline": 1})
        def _write_urls(ws, df, cols: list[str]):
            for col in cols:
                if col not in df.columns:
                    continue
                c_idx = df.columns.get_loc(col)
                # Skip the Vietnamese header row at df index 0; Excel row = df_index + 1
                for r_idx, row in df.iloc[1:].iterrows():
                    val = row.get(col)
                    if not val:
                        continue
                    s = str(val)
                    if s.lower().startswith(("http://", "https://")):
                        excel_row = r_idx + 1  # account for header row
                        try:
                            ws.write_url(excel_row, c_idx, s, url_format, string=s)
                        except Exception:
                            pass

        ws_prod = writer.sheets.get("Products")
        ws_camp = writer.sheets.get("Campaigns")
        ws_prom = writer.sheets.get("Promotions")
        if ws_prod is not None:
            _write_urls(ws_prod, df_products, ["url", "affiliate_url", "image_url"])
        if ws_camp is not None:
            _write_urls(ws_camp, df_campaigns, ["campaign_url", "description_url"])
        if ws_prom is not None:
            _write_urls(ws_prom, df_promotions, ["link"])

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
        "description_url": "Mô tả (Web)", "scope": "Phạm vi", "sub_category": "Danh mục phụ",
        "type": "Loại", "campaign_url": "URL chiến dịch",
    }
    trans_commissions = {
        "id": "Mã ID",
        "campaign_id": "Mã chiến dịch", "reward_type": "Kiểu thưởng", "sales_ratio": "Tỷ lệ (%)",
        "sales_price": "Hoa hồng cố định", "target_month": "Tháng áp dụng",
    }
    trans_promotions = {
        "id": "Mã ID",
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
    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_formulas": False, "strings_to_urls": False}},
    ) as writer:
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

# ---------------- Optional helper page: campaign description as HTML ----------------
@app.get(
        "/campaigns/{campaign_id}/description",
        tags=["Campaigns 📢"],
        summary="Xem mô tả chiến dịch (HTML rút gọn)",
)
def campaign_description_page(campaign_id: str, db: Session = Depends(get_db)):
        import html, re
        # Lấy từ log đã lưu (ưu tiên, vì đầy đủ hơn DB)
        LOG_DIR = os.getenv("API_LOG_DIR", "./logs")
        path = os.path.join(LOG_DIR, "campaign_detail.jsonl")
        raw_html = None
        try:
                with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                                try:
                                        rec = json.loads(line)
                                        if str(rec.get("campaign_id")) == str(campaign_id):
                                                data = rec.get("raw", {}).get("data")
                                                if isinstance(data, list) and data:
                                                        data = data[0]
                                                if isinstance(data, dict):
                                                        raw_html = data.get("description")
                                except Exception:
                                        continue
        except FileNotFoundError:
                pass
        # Fallback rỗng nếu không có
        raw_html = raw_html or "<p>Không tìm thấy mô tả.</p>"
        # Vệ sinh tối thiểu: chặn script/style
        raw_html = re.sub(r"<\s*(script|style)[^>]*>[\s\S]*?<\s*/\s*\1\s*>", "", str(raw_html), flags=re.IGNORECASE)
        body = f"""
        <!doctype html>
        <html lang=vi>
        <head>
            <meta charset="utf-8" />
            <title>Mô tả chiến dịch {html.escape(str(campaign_id))}</title>
            <style>
                body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; line-height: 1.6; }}
                .container {{ max-width: 980px; margin: 0 auto; }}
                .meta {{ color: #666; margin-bottom: 16px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="meta">Campaign ID: {html.escape(str(campaign_id))}</div>
                <div class="content">{raw_html}</div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=body)
