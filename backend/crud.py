# backend/crud.py
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import ProductOffer
from sqlalchemy import delete as sa_delete
import models, schemas


# =====================================================
# ===============  AFFILIATE LINKS CRUD  ==============
# =====================================================

def get_links(db: Session, skip: int = 0, limit: int = 100) -> List[models.AffiliateLink]:
    return db.query(models.AffiliateLink).offset(skip).limit(limit).all()


def get_link(db: Session, link_id: int) -> Optional[models.AffiliateLink]:
    return db.query(models.AffiliateLink).filter(models.AffiliateLink.id == link_id).first()


def create_link(db: Session, link: schemas.AffiliateLinkCreate) -> models.AffiliateLink:
    # Pydantic v2 ưu tiên model_dump(); fallback .dict() nếu cần
    # Dùng mode="json" để đảm bảo HttpUrl -> str trước khi ghi DB
    payload = link.model_dump(mode="json") if hasattr(link, "model_dump") else link.dict()
    obj = models.AffiliateLink(**payload)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_link(db: Session, link_id: int, link: schemas.AffiliateLinkUpdate) -> Optional[models.AffiliateLink]:
    obj = get_link(db, link_id)
    if not obj:
        return None
    # Dùng mode="json" để đảm bảo HttpUrl -> str trước khi cập nhật DB
    payload = link.model_dump(mode="json") if hasattr(link, "model_dump") else link.dict()
    for k, v in payload.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_link(db: Session, link_id: int) -> Optional[models.AffiliateLink]:
    obj = get_link(db, link_id)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj


# =====================================================
# =================  API CONFIG CRUD  =================
# =====================================================

def create_api_config(db: Session, config: schemas.APIConfigCreate) -> models.APIConfig:
    payload = config.model_dump() if hasattr(config, "model_dump") else config.dict()
    obj = models.APIConfig(**payload)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_api_config(db: Session, name: str) -> Optional[models.APIConfig]:
    """Lấy config theo name (ví dụ: 'deepseek', 'openai', ...)"""
    return db.query(models.APIConfig).filter(models.APIConfig.name == name).first()

def get_ingest_policy(db: Session) -> bool:
    """
    Đọc ingest_policy từ DB, mặc định False (API ingest bỏ qua policy; policy chỉ áp dụng cho import Excel).
    Lưu trong bảng api_configs, với name='ingest_policy' và model='only_with_commission=true/false'.
    """
    cfg = get_api_config(db, "ingest_policy")
    if not cfg or not cfg.model:
        return False
    return "only_with_commission=true" in cfg.model.lower()

def get_policy_flags(db: Session) -> dict:
    """
    Trả về dict cờ policy lấy từ api_configs.name='ingest_policy', field model (chuỗi dạng key=value;key2=value2).
    Hỗ trợ:
      - only_with_commission=true/false
      - check_urls=true/false
      - linkcheck_cursor=<int>
    """
    cfg = get_api_config(db, "ingest_policy")
    s = (cfg.model or "").lower() if cfg else ""
    flags = {
        "only_with_commission": "only_with_commission=true" in s,
        "check_urls": "check_urls=true" in s,
        "linkcheck_cursor": 0,
        "linkcheck_mod": 10,
        "linkcheck_limit": None,
    }
    # Đọc cursor nếu có
    import re
    m = re.search(r"linkcheck_cursor=(\d+)", s)
    if m:
        try:
            flags["linkcheck_cursor"] = int(m.group(1))
        except Exception:
            flags["linkcheck_cursor"] = 0
    m = re.search(r"linkcheck_mod=(\d+)", s)
    if m:
        try:
            flags["linkcheck_mod"] = max(1, int(m.group(1)))
        except Exception:
            flags["linkcheck_mod"] = 10
    m = re.search(r"linkcheck_limit=(\d+)", s)
    if m:
        try:
            flags["linkcheck_limit"] = max(1, int(m.group(1)))
        except Exception:
            flags["linkcheck_limit"] = None
    return flags


def set_policy_flag(db: Session, key: str, value: str | int | bool) -> None:
    """
    Ghi 1 flag vào ingest_policy.model, giữ nguyên các flag còn lại.
    """
    cfg = get_api_config(db, "ingest_policy")
    from schemas import APIConfigCreate
    if not cfg:
        model = f"{key}={value}"
        upsert_api_config_by_name(db, APIConfigCreate(name="ingest_policy", base_url="-", api_key="-", model=model))
        return
    s = cfg.model or ""
    # Loại bỏ key cũ
    parts = [p for p in s.split(";") if p and not p.strip().lower().startswith(f"{key.lower()}=")]
    parts.append(f"{key}={str(value).lower()}")
    new_model = ";".join(parts)
    upsert_api_config_by_name(db, APIConfigCreate(name="ingest_policy",
        base_url=cfg.base_url or "-", api_key=cfg.api_key or "-", model=new_model))

def list_api_configs(db: Session) -> List[models.APIConfig]:
    return db.query(models.APIConfig).all()


def get_api_config_by_id(db: Session, config_id: int) -> Optional[models.APIConfig]:
    return db.query(models.APIConfig).filter(models.APIConfig.id == config_id).first()


def delete_api_config(db: Session, config_id: int) -> Optional[models.APIConfig]:
    obj = get_api_config_by_id(db, config_id)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj


def upsert_api_config_by_name(db: Session, config: schemas.APIConfigCreate) -> models.APIConfig:
    """
    Nếu name đã tồn tại: cập nhật base_url, api_key, model.
    Nếu chưa có: tạo mới.
    """
    existing = get_api_config(db, config.name)
    if existing:
        existing.base_url = config.base_url
        existing.api_key = config.api_key
        existing.model = config.model
        db.commit()
        db.refresh(existing)
        return existing
    else:
        return create_api_config(db, config)

# [THÊM MỚI — đặt sau nhóm hàm cho APIConfig]
from sqlalchemy import select
from models import AffiliateTemplate

def get_affiliate_template_by_network(db, network: str, platform: str | None = None):
    # 1) Ưu tiên network + platform
    if platform:
        stmt = select(AffiliateTemplate).where(
            AffiliateTemplate.network == network,
            AffiliateTemplate.platform == platform,
            AffiliateTemplate.enabled == True,
        )
        tpl = db.execute(stmt).scalars().first()
        if tpl:
            return tpl
    # 2) Fallback network-only (template mặc định cho network)
    stmt2 = select(AffiliateTemplate).where(
        AffiliateTemplate.network == network,
        AffiliateTemplate.platform.is_(None),
        AffiliateTemplate.enabled == True,
    )
    tpl2 = db.execute(stmt2).scalars().first()
    if tpl2:
        return tpl2
    return None

def upsert_affiliate_template(db, data: "schemas.AffiliateTemplateCreate"):
    # Ưu tiên key: (network, platform) nếu platform có; nếu không có platform thì (network-only)
    if getattr(data, "platform", None):
        stmt = select(AffiliateTemplate).where(
            AffiliateTemplate.network == data.network,
            AffiliateTemplate.platform == data.platform,
        )
        tpl = db.execute(stmt).scalars().first()
    else:
        stmt = select(AffiliateTemplate).where(
            AffiliateTemplate.network == data.network,
            AffiliateTemplate.platform.is_(None),
        )
        tpl = db.execute(stmt).scalars().first()

    if tpl:
        # merchant legacy không còn dùng; giữ nguyên giá trị cũ nếu có nhưng không cập nhật nữa
        tpl.template = data.template
        tpl.default_params = data.default_params
        tpl.enabled = data.enabled
        tpl.platform = getattr(data, "platform", None)
        db.add(tpl); db.commit(); db.refresh(tpl)
        return tpl

    new_tpl = AffiliateTemplate(
        merchant=None,
        network=data.network,
        platform=getattr(data, "platform", None),
        template=data.template,
        default_params=data.default_params,
        enabled=data.enabled,
    )
    db.add(new_tpl); db.commit(); db.refresh(new_tpl)
    return new_tpl

def get_affiliate_template_by_id(db: Session, tpl_id: int):
    return db.query(models.AffiliateTemplate).filter(models.AffiliateTemplate.id == tpl_id).first()

def update_affiliate_template(db: Session, tpl_id: int, data: "schemas.AffiliateTemplateCreate"):
    tpl = get_affiliate_template_by_id(db, tpl_id)
    if not tpl:
        return None
    tpl.merchant = data.merchant
    tpl.network = data.network
    tpl.template = data.template
    tpl.default_params = data.default_params
    tpl.enabled = data.enabled
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl

def delete_affiliate_template_by_id(db: Session, tpl_id: int):
    tpl = get_affiliate_template_by_id(db, tpl_id)
    if not tpl:
        return None
    db.delete(tpl)
    db.commit()
    return tpl

def list_affiliate_templates(db: Session):
    return db.query(models.AffiliateTemplate).all()

# --- THÊM MỚI: upsert offer theo (source, source_id) ---
def upsert_offer_by_source(db, data: "schemas.ProductOfferCreate"):
    stmt = select(ProductOffer).where(
        ProductOffer.source == data.source,
        ProductOffer.source_id == data.source_id,
    )
    obj = db.execute(stmt).scalars().first()
    if obj:
        def _set_if_not_blank(attr: str, val):
            # Không ghi đè nếu None hoặc chuỗi rỗng (sau strip)
            if val is None:
                return
            if isinstance(val, str) and val.strip() == "":
                return
            setattr(obj, attr, val)

        _set_if_not_blank("title", data.title)
        # url là chuỗi: chuyển str và không ghi đè nếu chuỗi rỗng
        _set_if_not_blank("url", str(data.url) if getattr(data, "url", None) is not None else None)
        _set_if_not_blank("affiliate_url", data.affiliate_url)
        _set_if_not_blank("image_url", data.image_url)
        # số/bool: 0/False vẫn ghi đè
        if getattr(data, "price", None) is not None:
            obj.price = data.price
        _set_if_not_blank("currency", (data.currency or "VND"))
        _set_if_not_blank("merchant", data.merchant)
        # campaign_id có thể là chuỗi; chỉ ghi khi không rỗng
        _set_if_not_blank("campaign_id", getattr(data, "campaign_id", None))
        # --- V2 flags ---
        if hasattr(data, "approval_status") and (getattr(data, "approval_status") is not None) and (not (isinstance(getattr(data, "approval_status"), str) and str(getattr(data, "approval_status")).strip() == "")):
            obj.approval_status = getattr(data, "approval_status")
        if hasattr(data, "eligible_commission") and getattr(data, "eligible_commission") is not None:
            obj.eligible_commission = getattr(data, "eligible_commission")
        _set_if_not_blank("source_type", getattr(data, "source_type", None))
        if hasattr(data, "affiliate_link_available") and getattr(data, "affiliate_link_available") is not None:
            obj.affiliate_link_available = getattr(data, "affiliate_link_available")
        _set_if_not_blank("product_id", getattr(data, "product_id", None))
        if getattr(data, "extra", None) is not None:
            obj.extra = data.extra
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    obj = ProductOffer(
        source=data.source,
        source_id=data.source_id,
        merchant=data.merchant,
        title=data.title,
        url=str(data.url),
        affiliate_url=data.affiliate_url,
        image_url=data.image_url,
        price=data.price,
        currency=data.currency or "VND",
        campaign_id=getattr(data, "campaign_id", None),
        # --- V2 flags ---
        approval_status=getattr(data, "approval_status", None),
        eligible_commission=getattr(data, "eligible_commission", False),
        source_type=getattr(data, "source_type", None),
        affiliate_link_available=getattr(data, "affiliate_link_available", False),
        product_id=getattr(data, "product_id", None),
        extra=data.extra,
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

# Hỗ trợ import Excel: ưu tiên cập nhật theo source_id (bất kể source hiện hữu)
def _apply_offer_update_fields(obj: ProductOffer, data: "schemas.ProductOfferCreate"):
    def _set_if_not_blank(attr: str, val):
        if val is None:
            return
        if isinstance(val, str) and val.strip() == "":
            return
        setattr(obj, attr, val)

    _set_if_not_blank("title", data.title)
    if getattr(data, "url", None) is not None:
        _set_if_not_blank("url", str(data.url))
    _set_if_not_blank("affiliate_url", data.affiliate_url)
    _set_if_not_blank("image_url", data.image_url)
    if getattr(data, "price", None) is not None:
        obj.price = data.price
    _set_if_not_blank("currency", (data.currency or "VND"))
    _set_if_not_blank("merchant", data.merchant)
    _set_if_not_blank("campaign_id", getattr(data, "campaign_id", None))
    if hasattr(data, "approval_status") and (getattr(data, "approval_status") is not None) and (not (isinstance(getattr(data, "approval_status"), str) and str(getattr(data, "approval_status")).strip() == "")):
        obj.approval_status = getattr(data, "approval_status")
    if hasattr(data, "eligible_commission") and getattr(data, "eligible_commission") is not None:
        obj.eligible_commission = getattr(data, "eligible_commission")
    _set_if_not_blank("source_type", getattr(data, "source_type", None))
    if hasattr(data, "affiliate_link_available") and getattr(data, "affiliate_link_available") is not None:
        obj.affiliate_link_available = getattr(data, "affiliate_link_available")
    _set_if_not_blank("product_id", getattr(data, "product_id", None))
    if getattr(data, "extra", None) is not None:
        obj.extra = data.extra

def upsert_offer_for_excel(db: Session, data: "schemas.ProductOfferCreate") -> ProductOffer:
    """Upsert cho Excel: nếu tìm thấy bất kỳ ProductOffer nào có source_id trùng thì cập nhật record đó,
    không phụ thuộc vào trường source. Nếu không có, tạo mới với source='excel'."""
    # 1) Thử tìm theo (source='excel', source_id)
    stmt = select(ProductOffer).where(ProductOffer.source == "excel", ProductOffer.source_id == data.source_id)
    obj = db.execute(stmt).scalars().first()
    if not obj:
        # 2) Fallback: tìm theo source_id bất kể source
        stmt2 = select(ProductOffer).where(ProductOffer.source_id == data.source_id)
        obj = db.execute(stmt2).scalars().first()
    if obj:
        _apply_offer_update_fields(obj, data)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    # 3) Không có record nào → tạo mới chuẩn hoá như upsert_offer_by_source
    obj = ProductOffer(
        source=(getattr(data, "source", None) or "excel"),
        source_id=data.source_id,
        merchant=data.merchant,
        title=data.title,
        url=str(data.url),
        affiliate_url=data.affiliate_url,
        image_url=data.image_url,
        price=data.price,
        currency=data.currency or "VND",
        campaign_id=getattr(data, "campaign_id", None),
        approval_status=getattr(data, "approval_status", None),
        eligible_commission=getattr(data, "eligible_commission", False),
        source_type=getattr(data, "source_type", "excel"),
        affiliate_link_available=getattr(data, "affiliate_link_available", False),
        product_id=getattr(data, "product_id", None),
        extra=data.extra,
    )
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def list_offers(
    db: Session,
    merchant: str | None = None,
    skip: int = 0,
    limit: int = 50,
    source_type: str | None = None,
    exclude_source_types: list[str] | None = None,
):
    """
    List product offers with optional filters.
    - merchant: filter by merchant name
    - source_type: exact match on ProductOffer.source_type
    - exclude_source_types: list of source_types to exclude
    """
    q = db.query(models.ProductOffer)
    if merchant:
        q = q.filter(models.ProductOffer.merchant == merchant)
    if source_type:
        q = q.filter(models.ProductOffer.source_type == source_type)
    if exclude_source_types:
        q = q.filter(models.ProductOffer.source_type.notin_(exclude_source_types))
    return q.offset(skip).limit(limit).all()

def get_offer_by_id(db: Session, offer_id: int):
    return db.query(models.ProductOffer).filter(models.ProductOffer.id == offer_id).first()

def update_offer(db: Session, offer_id: int, data: "schemas.ProductOfferUpdate"):
    obj = get_offer_by_id(db, offer_id)
    if not obj:
        return None
    payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
    for k, v in payload.items():
        if v is not None:
            setattr(obj, k, str(v) if k == "url" else v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def delete_offer(db: Session, offer_id: int):
    obj = get_offer_by_id(db, offer_id)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj

def delete_all_offers(db: Session) -> int:
    res = db.execute(sa_delete(models.ProductOffer))
    db.commit()
    return res.rowcount or 0

def delete_offers_by_filter(
    db: Session,
    source_type: str | None = None,
    exclude_source_types: list[str] | None = None,
    campaign_id: str | None = None,
) -> int:
    """Bulk delete offers by simple filters. Returns number of deleted rows."""
    q = db.query(models.ProductOffer)
    if source_type:
        q = q.filter(models.ProductOffer.source_type == source_type)
    if exclude_source_types:
        q = q.filter(models.ProductOffer.source_type.notin_(exclude_source_types))
    if campaign_id:
        q = q.filter(models.ProductOffer.campaign_id == campaign_id)
    # Use SQLAlchemy delete() for efficiency
    res = q.delete(synchronize_session=False)
    db.commit()
    return int(res or 0)

# ===== Campaign CRUD =====
def get_campaign_by_cid(db: Session, campaign_id: str):
    return db.query(models.Campaign).filter(models.Campaign.campaign_id == campaign_id).first()

def upsert_campaign(db: Session, data: "schemas.CampaignCreate"):
    """Upsert campaign but NEVER persist placeholder strings.

    Rules:
    - Treat None/""/"API_MISSING"/"NO_DATA" as "no new information" and do not overwrite existing values.
    - Normalize user_registration_status (SUCCESSFUL -> APPROVED; uppercase; skip if empty).
    """
    PLACEHOLDERS = {None, "", "API_MISSING", "NO_DATA"}

    obj = get_campaign_by_cid(db, data.campaign_id)
    if obj:
        # cập nhật các trường có giá trị
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)

        # Drop placeholders to preserve existing DB values
        for k, v in list(payload.items()):
            if v in PLACEHOLDERS:
                payload.pop(k, None)

        # Chuẩn hoá trạng thái user_registration_status theo chuẩn mới (SUCCESSFUL -> APPROVED; uppercase, trim)
        if "user_registration_status" in payload:
            us_val = payload.get("user_registration_status")
            # Không ghi đè bằng None/"" → xoá khỏi payload để giữ nguyên giá trị hiện có trong DB
            if us_val in (None, ""):
                payload.pop("user_registration_status", None)
            else:
                us = str(us_val).strip().upper()
                if us == "SUCCESSFUL":
                    us = "APPROVED"
                payload["user_registration_status"] = us
        for k, v in payload.items():
            setattr(obj, k, v)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    # Remove placeholders on insert as well
    for k, v in list(payload.items()):
        if v in (None, "", "API_MISSING", "NO_DATA"):
            payload[k] = None
    # Chuẩn hoá khi tạo mới
    if "user_registration_status" in payload and payload["user_registration_status"] is not None:
        us = str(payload["user_registration_status"]).strip().upper()
        if us == "SUCCESSFUL":
            us = "APPROVED"
        payload["user_registration_status"] = us
    obj = models.Campaign(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def list_campaigns(db: Session, status: str | None = None):
    q = db.query(models.Campaign)
    if status:
        q = q.filter(models.Campaign.status == status)
    return q.all()

def campaigns_need_registration_alerts(db: Session) -> list[dict]:
    """
    Trả về danh sách campaign đang chạy & có sản phẩm trong DB,
    nhưng user chưa ở trạng thái APPROVED.
    """
    # Lấy set campaign_id đang có trong product_offers
    offer_cids = {cid for (cid,) in db.query(models.ProductOffer.campaign_id).filter(models.ProductOffer.campaign_id.isnot(None)).distinct().all()}
    if not offer_cids:
        return []

    rows = (
        db.query(models.Campaign)
        .filter(models.Campaign.campaign_id.in_(offer_cids))
        .filter(models.Campaign.status == "running")
        .filter(models.Campaign.user_registration_status.isnot(None))
        .filter(models.Campaign.user_registration_status != "APPROVED")
        .all()
    )
    return [
        {
            "campaign_id": r.campaign_id,
            "merchant": r.merchant,
            "name": r.name,
            "status": r.status,
            "approval": r.approval,
            "user_status": r.user_registration_status,
            "start_time": r.start_time,
            "end_time": r.end_time,
        }
        for r in rows
    ]

# ===== Promotion CRUD =====
def upsert_promotion(db: Session, data: "schemas.PromotionCreate"):
    obj = db.query(models.Promotion).filter(
        models.Promotion.campaign_id == data.campaign_id,
        models.Promotion.name == data.name,
        models.Promotion.start_time == data.start_time,
        models.Promotion.end_time == data.end_time,
    ).first()
    if obj:
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
        for k, v in payload.items():
            # Không ghi đè bằng None/chuỗi rỗng
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            setattr(obj, k, v)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    obj = models.Promotion(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def list_promotions(db: Session, skip: int = 0, limit: int = 50, campaign_id: str | None = None):
    q = db.query(models.Promotion)
    if campaign_id:
        q = q.filter(models.Promotion.campaign_id == campaign_id)
    return q.offset(skip).limit(limit).all()

def get_promotion_by_id(db: Session, pid: int):
    return db.query(models.Promotion).filter(models.Promotion.id == pid).first()

def delete_promotion(db: Session, pid: int):
    obj = get_promotion_by_id(db, pid)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj

def delete_all_promotions(db: Session) -> int:
    res = db.execute(sa_delete(models.Promotion))
    db.commit()
    return res.rowcount or 0

def delete_promotions_by_campaign(db: Session, campaign_id: str) -> int:
    q = db.query(models.Promotion).filter(models.Promotion.campaign_id == campaign_id)
    res = q.delete(synchronize_session=False)
    db.commit()
    return int(res or 0)

# ===== CommissionPolicy CRUD =====
def upsert_commission_policy(db: Session, data: "schemas.CommissionPolicyCreate"):
    obj = db.query(models.CommissionPolicy).filter(
        models.CommissionPolicy.campaign_id == data.campaign_id,
        models.CommissionPolicy.reward_type == data.reward_type,
        models.CommissionPolicy.target_month == data.target_month,
    ).first()
    if obj:
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
        for k, v in payload.items():
            # Không ghi đè bằng None/chuỗi rỗng; số 0 vẫn cập nhật
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            setattr(obj, k, v)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    obj = models.CommissionPolicy(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

# ====== Update by ID helpers for Commissions & Promotions ======
def update_commission_policy_by_id(db: Session, cid: int, data: "schemas.CommissionPolicyCreate"):
    obj = get_commission_policy_by_id(db, cid)
    if not obj:
        return None
    payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        setattr(obj, k, v)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def update_promotion_by_id(db: Session, pid: int, data: "schemas.PromotionCreate"):
    obj = get_promotion_by_id(db, pid)
    if not obj:
        return None
    payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        setattr(obj, k, v)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def list_commission_policies(db: Session, skip: int = 0, limit: int = 50, campaign_id: str | None = None):
    q = db.query(models.CommissionPolicy)
    if campaign_id:
        q = q.filter(models.CommissionPolicy.campaign_id == campaign_id)
    return q.offset(skip).limit(limit).all()

def get_commission_policy_by_id(db: Session, cid: int):
    return db.query(models.CommissionPolicy).filter(models.CommissionPolicy.id == cid).first()

def delete_commission_policy(db: Session, cid: int):
    obj = get_commission_policy_by_id(db, cid)
    if not obj:
        return None
    db.delete(obj)
    db.commit()
    return obj

def delete_all_commission_policies(db: Session) -> int:
    res = db.execute(sa_delete(models.CommissionPolicy))
    db.commit()
    return res.rowcount or 0

def delete_commission_policies_by_campaign(db: Session, campaign_id: str) -> int:
    q = db.query(models.CommissionPolicy).filter(models.CommissionPolicy.campaign_id == campaign_id)
    res = q.delete(synchronize_session=False)
    db.commit()
    return int(res or 0)
