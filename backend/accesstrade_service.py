import httpx
from typing import Any, Dict, List
from sqlalchemy.orm import Session
import crud
import logging
import json
from urllib.parse import urlparse
import os
from datetime import datetime, UTC

logger = logging.getLogger("affiliate_api")

# --- JSONL raw logger ---
_LOG_DIR = os.getenv("API_LOG_DIR", "./logs")

def _ensure_log_dir() -> None:
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except Exception:
        pass

def _log_jsonl(filename: str, payload: dict) -> None:
    try:
        _ensure_log_dir()
        fpath = os.path.join(_LOG_DIR, filename)
        data = dict(payload)
        data.setdefault("ts", datetime.now(UTC).isoformat())
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("rawlog error %s: %s", filename, e)

def _get_at_config(db: Session):
    cfg = crud.get_api_config(db, "accesstrade")
    if not cfg or not cfg.api_key or not cfg.base_url:
        raise ValueError("Chưa cấu hình APIConfig 'accesstrade'")
    return cfg

def _is_mock_cfg(cfg) -> bool:
    try:
        if str(os.getenv("AT_MOCK", "")).strip() == "1":
            return True
        base = (getattr(cfg, "base_url", "") or "").strip().lower()
        return base.startswith("mock://")
    except Exception:
        return False

def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Token {api_key}",
        "Accept": "application/json",
    }

# --- Lấy toàn bộ campaign (song song theo "window" trang) ---
import time, asyncio

async def fetch_campaigns_full_all(
    db: Session,
    status: str | None = None,
    limit_per_page: int = 50,
    max_pages: int = 1000,
    throttle_ms: int = 0,
    page_concurrency: int = 6,
    window_pages: int = 10,
) -> List[Dict[str, Any]]:
    """
    Quét /v1/campaigns theo "cửa sổ" trang, mỗi cửa sổ tải song song (giới hạn bởi page_concurrency).
    Kết thúc khi 1 cửa sổ trả về toàn trang rỗng.
    """
    cfg = _get_at_config(db)
    if _is_mock_cfg(cfg):
        return [
            {"campaign_id": "CAMP1", "merchant": "shopee", "name": "Shopee", "status": "running", "approval": "manual"},
            {"campaign_id": "CAMP2", "merchant": "lazada", "name": "Lazada", "status": "paused", "approval": "manual"},
            {"campaign_id": "CAMP3", "merchant": "tiki", "name": "Tiki", "status": "running", "approval": "successful"},
        ]
    base_url = cfg.base_url.rstrip("/") + "/v1/campaigns"

    # Map status về 'running' / 'paused'
    status_param = None
    if status is not None:
        s = str(status).strip().lower()
        if s in ("running", "1", "active"):
            status_param = "running"
        elif s in ("paused", "0", "stopped", "stop"):
            status_param = "paused"
        else:
            status_param = s

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=60.0)
    out: List[Dict[str, Any]] = []
    sem = asyncio.Semaphore(max(1, int(page_concurrency)))

    async def fetch_one(client: httpx.AsyncClient, page: int, limit_hint: int) -> List[Dict[str, Any]]:
        curr_limit = int(limit_hint)
        for attempt in range(1, 4):
            params: Dict[str, str] = {"page": str(page), "limit": str(curr_limit)}
            if status_param is not None:
                params["status"] = status_param
            try:
                async with sem:
                    r = await client.get(base_url, headers=_headers(cfg.api_key), params=params)
                ok = (r.status_code == 200)
                j = r.json() if ok else None
                items = j.get("data") if ok and isinstance(j, dict) else []
                _log_jsonl("campaigns_full.jsonl", {
                    "endpoint": "campaigns_full",
                    "page": page,
                    "limit": curr_limit,
                    "status_filter": status_param,
                    "ok": ok,
                    "count": len(items),
                    "attempt": attempt,
                    "status_code": getattr(r, "status_code", None),
                })
                return items
            except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                _log_jsonl("campaigns_full.jsonl", {
                    "endpoint": "campaigns_full",
                    "page": page,
                    "limit": curr_limit,
                    "status_filter": status_param,
                    "ok": False,
                    "error": f"{type(e).__name__}: {e}",
                    "attempt": attempt,
                })
                await asyncio.sleep(1.2 * attempt)
                curr_limit = max(20, curr_limit // 2)
        return []

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, http2=True) as client:
        page = 1
        while page <= max_pages:
            end = min(max_pages, page + int(window_pages) - 1)
            tasks = [fetch_one(client, p, limit_per_page) for p in range(page, end + 1)]
            results = await asyncio.gather(*tasks)
            got_any = False
            for items in results:
                if items:
                    out.extend(items)
                    got_any = True
            if not got_any:
                break
            page = end + 1
            if throttle_ms:
                await asyncio.sleep(throttle_ms / 1000.0)

    return out

# --- Lấy sản phẩm từ datafeeds ---
async def fetch_products(db: Session, path: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    cfg = _get_at_config(db)
    if _is_mock_cfg(cfg):
        p = dict(params or {})
        page = int(p.get("page", 1) or 1)
        limit = int(p.get("limit", 100) or 100)
        if page > 1:
            return []
        items: list[dict] = []
        for i in range(min(5, limit)):
            idx = i + 1
            items.append({
                "id": f"P{page}{idx}",
                "name": f"SP Tiki {idx}",
                "url": f"https://tiki.vn/product/{idx}",
                "aff_link": f"https://go.mock/aff?pid={idx}",
                "image": "https://via.placeholder.com/300",
                "price": 99000 + idx,
                "currency": "VND",
                "campaign_id": "CAMP3",
                "merchant": "tikivn",
                "cate": "cat1",
                "shop_name": "Shop Mock",
                "update_time": "2025-09-20T00:00:00Z",
            })
        return items
    url = cfg.base_url.rstrip("/") + "/" + path.lstrip("/")

    # Chuẩn hoá params cho /v1/datafeeds: dùng 'campaign' thay vì 'merchant'
    _params = dict(params or {})
    if url.endswith("/v1/datafeeds"):
        if "merchant" in _params and "campaign" not in _params:
            _params["campaign"] = _params.pop("merchant")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_headers(cfg.api_key), params=_params)
        ok = (r.status_code == 200)
        try:
            data = r.json() if ok else None
        except Exception:
            data = None
        items = data.get("data") if ok and isinstance(data, dict) else []
        # JSONL log for diagnostics
        _log_jsonl("datafeeds.jsonl", {
            "endpoint": "datafeeds" if url.endswith("/v1/datafeeds") else path,
            "status_code": r.status_code,
            "ok": ok,
            "params": _params,
            "items_count": len(items),
            "raw_total": (data.get("total") if isinstance(data, dict) else None),
        })
        if not ok:
            r.raise_for_status()
        return items or []

# --- Compatibility helper cho main.py: lấy datafeeds theo trang ---
async def fetch_datafeeds(
    db: Session,
    merchant: str,
    page: int = 1,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Wrapper tương thích main.py:
    - Nhận merchant, page, limit
    - Gọi lại fetch_products('/v1/datafeeds', ...) và map 'merchant' -> 'campaign' theo spec AT
    """
    params: Dict[str, Any] = {
        "merchant": merchant,   # sẽ được fetch_products đổi thành 'campaign'
        "page": str(page),
        "limit": str(limit),
    }
    return await fetch_products(db, "/v1/datafeeds", params)

# --- Lấy thông tin khuyến mãi ---
async def fetch_promotions(db: Session, merchant: str) -> List[Dict[str, Any]]:
    """
    Lấy danh sách khuyến mãi của merchant từ Accesstrade.
    """
    cfg = _get_at_config(db)
    if _is_mock_cfg(cfg):
        return [{
            "name": f"Promo {merchant.upper()} 15%",
            "content": "Giảm 15% cho đơn hàng trên 200k",
            "start_time": "2025-09-01",
            "end_time": "2025-10-01",
            "coupon": "SALE15",
            "link": f"https://{merchant}.vn/promo",
        }]
    url = cfg.base_url.rstrip("/") + "/v1/offers_informations"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_headers(cfg.api_key), params={"merchant": merchant})
        ok = (r.status_code == 200)
        j = r.json() if ok else None
        items: List[Dict[str, Any]] = []
        if ok and isinstance(j, dict):
            items = j.get("data") or []

        _log_jsonl("promotions.jsonl", {
            "endpoint": "promotions",
            "merchant": (merchant or "").lower(),
            "status_code": r.status_code,
            "ok": ok,
            "items_count": len(items),
            "raw": j,
        })
        return items

# --- Lấy Top products (bán chạy) ---
async def fetch_top_products(
    db: Session,
    merchant: str,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Lấy danh sách sản phẩm bán chạy theo merchant & khoảng ngày.
    Trả về list các record có thể gồm: product_id, name, image, link, aff_link, price, discount, ...
    """
    cfg = _get_at_config(db)
    if _is_mock_cfg(cfg):
        out: list[dict] = []
        for i in range(3):
            out.append({
                "product_id": f"TP{i+1}",
                "name": f"Top {merchant} #{i+1}",
                "image": "https://via.placeholder.com/300",
                "link": f"https://{merchant}.vn/top/{i+1}",
                "aff_link": f"https://go.mock/top?i={i+1}",
                "price": 150000 + i * 10000,
            })
        return out
    url = cfg.base_url.rstrip("/") + "/v1/top_products"
    params = {
        "merchant": merchant,
        "page": str(page),
        "limit": str(limit),
    }
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_headers(cfg.api_key), params=params)
        ok = (r.status_code == 200)
        j = r.json() if ok else None
        items: List[Dict[str, Any]] = []
        if ok and isinstance(j, dict):
            items = j.get("data") or []

        _log_jsonl("top_products.jsonl", {
            "endpoint": "top_products",
            "merchant": (merchant or "").lower(),
            "status_code": r.status_code,
            "ok": ok,
            "items_count": len(items),
            "raw": j,
        })
        return items

# --- Lấy danh sách campaign đang chạy ---
async def fetch_active_campaigns(db: Session) -> Dict[str, str]:
    """
    Lấy toàn bộ campaign đang chạy từ Accesstrade.
    Trả về dict {campaign_id: merchant_name_lower}.
    """
    cfg = _get_at_config(db)
    if _is_mock_cfg(cfg):
        return {"CAMP1": "shopee", "CAMP3": "tikivn"}
    url = cfg.base_url.rstrip("/") + "/v1/campaigns"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_headers(cfg.api_key), params={"status": "running"})
        ok = (r.status_code == 200)
        result: Dict[str, str] = {}
        raw = None

        if ok:
            raw = r.json()
            if isinstance(raw, dict):
                for camp in raw.get("data", []):
                    camp_id = str(camp.get("campaign_id") or camp.get("id") or "").strip()
                    merchant = str(camp.get("merchant") or camp.get("name") or "").lower().strip()
                    if camp_id and merchant:
                        result[camp_id] = merchant

        _log_jsonl("campaigns_active.jsonl", {
            "endpoint": "campaigns_active",
            "status_code": r.status_code,
            "ok": ok,
            "items_count": len(result),
            "raw": raw if ok else None,
        })
        return result

# --- NEW: Lấy chi tiết 1 campaign (kèm trạng thái đăng ký của user nếu API trả về) ---
async def fetch_campaign_detail(db: Session, campaign_id: str) -> Dict[str, Any] | None:
    cfg = _get_at_config(db)
    if _is_mock_cfg(cfg):
        return {
            "campaign_id": campaign_id,
            "merchant": "tikivn" if campaign_id == "CAMP3" else "shopee",
            "name": "Mock Campaign",
            "status": "running",
            "approval": "manual",
            "user_registration_status": "APPROVED",
            "start_time": "2025-01-01",
            "end_time": "2025-12-31",
            "category": "E-commerce",
            "conversion_policy": "CPS",
            "cookie_duration": 2592000,
            "cookie_policy": "Last click",
            "description": "Mock detail",
            "scope": "VN",
            "sub_category": "General",
            "type": "Retail",
            "url": "https://example.com/campaign",
        }
    url = cfg.base_url.rstrip("/") + "/v1/campaigns"
    params = {"campaign_id": str(campaign_id)}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_headers(cfg.api_key), params=params)
        ok = (r.status_code == 200)
        j = r.json() if ok else None
        detail = None
        if ok and isinstance(j, dict):
            d = j.get("data")
            if isinstance(d, dict):
                detail = d
            elif isinstance(d, list) and d:
                detail = d[0]

        _log_jsonl("campaign_detail.jsonl", {
            "endpoint": "campaign_detail",
            "campaign_id": str(campaign_id),
            "status_code": r.status_code,
            "ok": ok,
            "empty": (detail is None),
            "raw": j if ok else None,
        })
        return detail

# --- NEW: Lấy commission policies theo campaign_id ---
async def fetch_commission_policies(db: Session, campaign_id: str) -> List[Dict[str, Any]]:
    cfg = _get_at_config(db)
    if _is_mock_cfg(cfg):
        return [{
            "reward_type": "CPS",
            "sales_ratio": 12.5,
            "sales_price": None,
            "target_month": "2025-09",
        }]
    url = cfg.base_url.rstrip("/") + "/v1/commission_policies"

    async def _call(params: Dict[str, str]) -> tuple[list[dict], int, dict|None]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=_headers(cfg.api_key), params=params)
            ok = (r.status_code == 200)
            j = r.json() if ok else None
            items: List[Dict[str, Any]] = []
            if ok and isinstance(j, dict):
                payload = j.get("data")
                if isinstance(payload, list):
                    items = payload
                elif isinstance(payload, dict):
                    items = [payload]
            return items, r.status_code, j

    # Thử kiểu 'campaign_id' trước
    items, status_code, j = await _call({"campaign_id": str(campaign_id)})
    if not items:
        # Fallback sang 'camp_id'
        items, status_code, j = await _call({"camp_id": str(campaign_id)})

    _log_jsonl("commission_policies.jsonl", {
        "endpoint": "commission_policies",
        "campaign_id": str(campaign_id),
        "status_code": status_code,
        "ok": (status_code == 200),
        "items_count": len(items),
        "raw": j if status_code == 200 else None,
    })
    return items

# --- Map sản phẩm ---
def map_at_product_to_offer(item: Dict[str, Any], commission: Any = None, promotion: Any = None) -> Dict[str, Any]:
    """
    Chuẩn hoá commission & promotion TẠI ĐÂY để export đọc được ngay:
    - commission_norm: dict có các key: sales_ratio, sales_price, reward_type, target_month
    - promotion_norm: dict có các key: name, content, start_time, end_time, coupon, link

    Chấp nhận commission/promotion truyền vào là dict hoặc list; tự chọn record phù hợp.
    """
    domain = (item.get("domain") or "").lower()
    campaign = (item.get("campaign") or "").lower()
    merchant = (
        item.get("merchant")
        or campaign
        or (domain.split(".")[0] if domain else "")
        or item.get("shop")
        or "unknown"
    ).lower()

    price_val = item.get("price")
    try:
        price = float(price_val) if price_val not in (None, "") else None
    except Exception:
        price = None

    # ---- Helpers ----
    def _extract_product_id(it: Dict[str, Any]) -> str | None:
        # product_id có thể là "322_2062448047" -> lấy phần sau cùng nếu cần
        pid = it.get("product_id") or it.get("id") or it.get("sku")
        if not pid:
            return None
        pid = str(pid)
        if "_" in pid:
            return pid.split("_")[-1]
        return pid

    def _norm_commission(raw: Any, it: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        Chuẩn hoá nhiều dạng structure từ API commission_policies về dict phẳng.
        Ưu tiên match theo product_id -> category -> default.
        Nếu 'raw' đã là dict phẳng có keys target -> dùng luôn.
        """
        if raw is None:
            return None

        # Nếu đã là dict phẳng (đúng keys)
        if isinstance(raw, dict) and (
            "sales_ratio" in raw or "ratio" in raw or "reward_type" in raw or "sales_price" in raw
        ):
            return {
                "sales_ratio": raw.get("sales_ratio") or raw.get("ratio"),
                "sales_price": raw.get("sales_price"),
                "reward_type": raw.get("reward_type"),
                "target_month": raw.get("target_month"),
            }

        # Nếu là dict kiểu policies tổng hợp: product/category/default
        pid = _extract_product_id(it)
        cate = it.get("cate") or it.get("category") or it.get("category_id")

        if isinstance(raw, dict):
            # product-level
            prod_list = raw.get("product") or raw.get("products")
            if isinstance(prod_list, list) and pid:
                for rec in prod_list:
                    if str(rec.get("product_id")) == str(pid):
                        return {
                            "sales_ratio": rec.get("sales_ratio") or rec.get("ratio"),
                            "sales_price": rec.get("sales_price"),
                            "reward_type": rec.get("reward_type"),
                            "target_month": rec.get("target_month"),
                        }
            # category-level
            cat_list = raw.get("category") or raw.get("categories")
            if isinstance(cat_list, list) and cate:
                for rec in cat_list:
                    if str(rec.get("category_id")) == str(cate):
                        return {
                            "sales_ratio": rec.get("sales_ratio") or rec.get("ratio"),
                            "sales_price": rec.get("sales_price"),
                            "reward_type": rec.get("reward_type"),
                            "target_month": rec.get("target_month"),
                        }
            # default-level
            default_val = raw.get("default")
            if isinstance(default_val, list) and default_val:
                rec = default_val[0]
                return {
                    "sales_ratio": rec.get("sales_ratio") or rec.get("ratio"),
                    "sales_price": rec.get("sales_price"),
                    "reward_type": rec.get("reward_type"),
                    "target_month": rec.get("target_month"),
                }
            if isinstance(default_val, dict):
                rec = default_val
                return {
                    "sales_ratio": rec.get("sales_ratio") or rec.get("ratio"),
                    "sales_price": rec.get("sales_price"),
                    "reward_type": rec.get("reward_type"),
                    "target_month": rec.get("target_month"),
                }

            # Nếu dict không có các key trên nhưng có mảng "data"
            data_block = raw.get("data")
            if isinstance(data_block, list) and data_block:
                rec = data_block[0]
                return {
                    "sales_ratio": rec.get("sales_ratio") or rec.get("ratio"),
                    "sales_price": rec.get("sales_price"),
                    "reward_type": rec.get("reward_type"),
                    "target_month": rec.get("target_month"),
                }
            if isinstance(data_block, dict):
                rec = data_block
                return {
                    "sales_ratio": rec.get("sales_ratio") or rec.get("ratio"),
                    "sales_price": rec.get("sales_price"),
                    "reward_type": rec.get("reward_type"),
                    "target_month": rec.get("target_month"),
                }

        # Nếu là list -> lấy phần tử đầu
        if isinstance(raw, list) and raw:
            rec = raw[0]
            if isinstance(rec, dict):
                return {
                    "sales_ratio": rec.get("sales_ratio") or rec.get("ratio"),
                    "sales_price": rec.get("sales_price"),
                    "reward_type": rec.get("reward_type"),
                    "target_month": rec.get("target_month"),
                }

        # Debug: log dữ liệu commission thô để phân tích format thật
        logger.debug("Commission raw for %s: %s",
                     it.get("id") or it.get("product_id") or it.get("name"),
                     raw)

        return None
    def _norm_promotion(raw: Any, it: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        Chuẩn hoá promotion:
        - Nếu list: ưu tiên record có merchant/cate phù hợp, không có thì lấy phần tử đầu.
        - Nếu dict: map về các keys chuẩn name/content/start_time/end_time/coupon/link
        """
        if raw is None:
            return None

        def _pick_prom(rec: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "name": rec.get("name"),
                "content": rec.get("content") or rec.get("description"),
                "start_time": rec.get("start_time"),
                "end_time": rec.get("end_time"),
                "coupon": rec.get("coupon"),
                "link": rec.get("link"),
            }

        if isinstance(raw, dict):
            return _pick_prom(raw)

        if isinstance(raw, list) and raw:
            # cố gắng match theo merchant/category
            it_merchant = (it.get("merchant") or "").lower()
            it_cate = it.get("cate") or it.get("category") or it.get("category_id")
            # ưu tiên match merchant
            for rec in raw:
                if isinstance(rec, dict) and (rec.get("merchant") or "").lower() == it_merchant:
                    # nếu có categories trong promo, thử match với cate sản phẩm
                    cats = rec.get("categories")
                    if not cats or (it_cate and it_cate in cats):
                        return _pick_prom(rec)
            # không match được -> lấy phần tử đầu tiên
            first = raw[0]
            if isinstance(first, dict):
                return _pick_prom(first)
        return None

    # ---- Normalize commission/promotion ----
    commission_norm = _norm_commission(commission, item)
    promotion_norm = _norm_promotion(promotion, item)

    # Chuẩn bị extra
    extra = dict(item)
    if commission_norm:
        extra["commission"] = commission_norm
    if promotion_norm:
        extra["promotion"] = promotion_norm

    # Chuẩn hoá thêm một số trường thường cần khi export
    extra["desc"] = item.get("desc") or item.get("description")
    extra["cate"] = item.get("cate") or item.get("category") or item.get("category_name")
    extra["shop_name"] = item.get("shop_name") or item.get("shop") or item.get("merchant_name")
    # Lưu thêm 'update_time_raw' để API/Export hiển thị thống nhất
    extra["update_time_raw"] = item.get("update_time") or item.get("last_update")
    # Giữ 'update_time' cho tương thích ngược
    extra["update_time"] = extra["update_time_raw"]

    return {
        "source": "accesstrade",
        "source_id": str(item.get("id") or item.get("product_id") or item.get("sku") or ""),
        "merchant": merchant,
        "title": item.get("name") or item.get("title") or "No title",
        # Một số payload dùng 'link' thay vì 'url'/'landing_url'/'product_url'
        "url": (
            item.get("url")
            or item.get("landing_url")
            or item.get("product_url")
            or item.get("link")
        ),
        "affiliate_url": item.get("aff_link") or item.get("affiliate_url") or item.get("deeplink") or None,
        "image_url": item.get("image") or item.get("thumbnail") or None,
        "price": price,
        "currency": item.get("currency") or "VND",
        "campaign_id": str(item.get("campaign_id") or item.get("campaign_id_str") or ""),
        # --- V2 flags ---
        "product_id": _extract_product_id(item),
        "affiliate_link_available": bool(item.get("aff_link") or item.get("affiliate_url") or item.get("deeplink")),
        "extra": json.dumps(extra, ensure_ascii=False),
    }

# --- Kiểm tra link sống/chết ---
async def _check_url_alive(url: str) -> bool:
    try:
        # UA giống trình duyệt để tránh bị chặn HEAD/GET
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = await client.head(url)
            # Chấp nhận 2xx, 3xx, thậm chí 401/403 (nhiều site chặn bot nhưng link vẫn sống)
            if resp.status_code < 400 or resp.status_code in (401, 403):
                return True
            if resp.status_code == 405:
                resp = await client.get(url)
                return resp.status_code < 400 or resp.status_code in (401, 403)
            return False
    except Exception as e:
        # Trong môi trường container, nhiều site chặn/timeout -> coi là "không chắc chắn"
        # Để tránh loại nhầm, tạm thời coi là alive (True) nhưng vẫn log để theo dõi
        logger.debug("Check exception: %s -> %s", url, str(e))
        return True
