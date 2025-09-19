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
    payload = link.model_dump() if hasattr(link, "model_dump") else link.dict()
    obj = models.AffiliateLink(**payload)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_link(db: Session, link_id: int, link: schemas.AffiliateLinkUpdate) -> Optional[models.AffiliateLink]:
    obj = get_link(db, link_id)
    if not obj:
        return None
    payload = link.model_dump() if hasattr(link, "model_dump") else link.dict()
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
    }
    # Đọc cursor nếu có
    import re
    m = re.search(r"linkcheck_cursor=(\d+)", s)
    if m:
        try:
            flags["linkcheck_cursor"] = int(m.group(1))
        except Exception:
            flags["linkcheck_cursor"] = 0
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

def get_affiliate_template(db, merchant: str, network: str):
    stmt = select(AffiliateTemplate).where(
        AffiliateTemplate.merchant == merchant,
        AffiliateTemplate.network == network,
        AffiliateTemplate.enabled == True
    )
    return db.execute(stmt).scalars().first()

def upsert_affiliate_template(db, data):
    # data: AffiliateTemplateCreate (pydantic)
    tpl = get_affiliate_template(db, data.merchant, data.network)
    if tpl:
        tpl.template = data.template
        tpl.default_params = data.default_params
        tpl.enabled = data.enabled
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return tpl
    new_tpl = AffiliateTemplate(
        merchant=data.merchant,
        network=data.network,
        template=data.template,
        default_params=data.default_params,
        enabled=data.enabled
    )
    db.add(new_tpl)
    db.commit()
    db.refresh(new_tpl)
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
        obj.title = data.title
        obj.url = str(data.url)
        obj.affiliate_url = data.affiliate_url
        obj.image_url = data.image_url
        obj.price = data.price
        obj.currency = data.currency or "VND"
        obj.merchant = data.merchant
        obj.campaign_id = getattr(data, "campaign_id", None)
        # --- V2 flags ---
        obj.approval_status = getattr(data, "approval_status", obj.approval_status)
        obj.eligible_commission = getattr(data, "eligible_commission", obj.eligible_commission)
        obj.source_type = getattr(data, "source_type", obj.source_type)
        obj.affiliate_link_available = getattr(data, "affiliate_link_available", obj.affiliate_link_available)
        obj.product_id = getattr(data, "product_id", obj.product_id)
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

def list_offers(db: Session, merchant: str | None = None, skip: int = 0, limit: int = 50):
    q = db.query(models.ProductOffer)
    if merchant:
        q = q.filter(models.ProductOffer.merchant == merchant)
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

# ===== Campaign CRUD =====
def get_campaign_by_cid(db: Session, campaign_id: str):
    return db.query(models.Campaign).filter(models.Campaign.campaign_id == campaign_id).first()

def upsert_campaign(db: Session, data: "schemas.CampaignCreate"):
    obj = get_campaign_by_cid(db, data.campaign_id)
    if obj:
        # cập nhật các trường có giá trị
        payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
        for k, v in payload.items():
            setattr(obj, k, v)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
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
            setattr(obj, k, v)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    obj = models.Promotion(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

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
            setattr(obj, k, v)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    obj = models.CommissionPolicy(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj
