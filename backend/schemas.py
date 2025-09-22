from pydantic import BaseModel, HttpUrl, constr, field_validator
from pydantic import ConfigDict
from datetime import datetime
from typing import Optional, Dict

# ----- Base Schema -----
class AffiliateLinkBase(BaseModel):
    name: constr(min_length=2, max_length=255)  # Tên từ 2–255 ký tự
    url: HttpUrl                                # URL chính (validate chuẩn)
    affiliate_url: HttpUrl                      # URL tiếp thị

    # Ép kiểu HttpUrl thành str khi xuất/serialize
    @field_validator("url", "affiliate_url", mode="before")
    def convert_url_to_str(cls, v):
        return str(v)

    model_config = ConfigDict(from_attributes=True)  # Cho phép map từ SQLAlchemy model


# ----- Create Schema -----
class AffiliateLinkCreate(AffiliateLinkBase):
    pass


# ----- Update Schema -----
class AffiliateLinkUpdate(AffiliateLinkBase):
    pass


# ----- Output Schema -----
class AffiliateLinkOut(AffiliateLinkBase):
    id: int


class APIConfigBase(BaseModel):
    name: str
    base_url: str
    api_key: str
    model: str | None = None

class APIConfigCreate(APIConfigBase):
    pass

class APIConfigOut(APIConfigBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class AffiliateTemplateBase(BaseModel):
    merchant: str
    network: str
    template: str
    default_params: Optional[Dict[str, str]] = None
    enabled: bool = True

class AffiliateTemplateCreate(AffiliateTemplateBase):
    pass

class AffiliateTemplateOut(AffiliateTemplateBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- THÊM MỚI: schemas cho ProductOffer ---
class ProductOfferBase(BaseModel):
    source: str = "accesstrade"
    source_id: str | None = None
    merchant: str
    title: str
    url: HttpUrl
    affiliate_url: str | None = None
    image_url: str | None = None
    price: float | None = None
    currency: str | None = "VND"
    campaign_id: str | None = None   # campaign chứa sản phẩm

    # --- NEW (V2) ---
    approval_status: str | None = None
    eligible_commission: bool | None = False
    source_type: str | None = None
    affiliate_link_available: bool | None = False
    product_id: str | None = None

    extra: str | None = None

class ProductOfferCreate(ProductOfferBase):
    pass

class ProductOfferUpdate(BaseModel):
    # tất cả optional để có thể update từng phần
    source: str | None = None
    source_id: str | None = None
    merchant: str | None = None
    title: str | None = None
    url: HttpUrl | None = None
    affiliate_url: str | None = None
    image_url: str | None = None
    price: float | None = None
    currency: str | None = None
    campaign_id: str | None = None

    # --- NEW (V2) ---
    approval_status: str | None = None
    eligible_commission: bool | None = None
    source_type: str | None = None
    affiliate_link_available: bool | None = None
    product_id: str | None = None

    extra: str | None = None

class ProductOfferOut(ProductOfferBase):
    id: int
    updated_at: datetime | None = None

    # Hiển thị trực tiếp (bóc từ extra trong endpoint)
    desc: str | None = None
    cate: str | None = None
    shop_name: str | None = None
    update_time_raw: str | None = None

    model_config = ConfigDict(from_attributes=True)

# --- NEW: schema cho PriceHistory ---
class PriceHistoryBase(BaseModel):
    offer_id: int
    price: float | None = None
    currency: str | None = "VND"
    recorded_at: datetime | None = None

class PriceHistoryCreate(PriceHistoryBase):
    pass

class PriceHistoryOut(PriceHistoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- NEW: schema cho Campaign ---
class CampaignBase(BaseModel):
    campaign_id: str
    merchant: str | None = None
    name: str | None = None
    status: str | None = None
    approval: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    user_registration_status: str | None = None

class CampaignCreate(CampaignBase):
    pass

class CampaignUpdate(CampaignBase):
    pass

class CampaignOut(CampaignBase):
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

# --- NEW: schema cho CommissionPolicy ---
class CommissionPolicyBase(BaseModel):
    campaign_id: str
    reward_type: str | None = None
    sales_ratio: float | None = None
    sales_price: float | None = None
    target_month: str | None = None

class CommissionPolicyCreate(CommissionPolicyBase):
    pass

class CommissionPolicyUpdate(CommissionPolicyBase):
    pass

class CommissionPolicyOut(CommissionPolicyBase):
    id: int
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# --- NEW: schema cho Promotion ---
class PromotionBase(BaseModel):
    campaign_id: str
    name: str | None = None
    content: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    coupon: str | None = None
    link: str | None = None

class PromotionCreate(PromotionBase):
    pass

class PromotionUpdate(PromotionBase):
    pass

class PromotionOut(PromotionBase):
    id: int
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)
