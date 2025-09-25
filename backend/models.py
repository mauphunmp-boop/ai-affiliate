from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, UTC

class AffiliateLink(Base):
    __tablename__ = "affiliate_links"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    url = Column(Text, nullable=False)
    affiliate_url = Column(Text, nullable=False)


class APIConfig(Base):
    __tablename__ = "api_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)   # deepseek, openai, gemini...
    base_url = Column(Text, nullable=False)
    api_key = Column(Text, nullable=False)
    model = Column(String, nullable=True)

# [THÊM MỚI — đặt ngay sau class APIConfig]
from sqlalchemy import JSON, UniqueConstraint

class AffiliateTemplate(Base):
    __tablename__ = "affiliate_templates"
    id = Column(Integer, primary_key=True, index=True)
    merchant = Column(String, nullable=True)       # LEGACY: không còn sử dụng, giữ để không phải migrate dữ liệu cũ
    network = Column(String, nullable=False)       # ví dụ: "accesstrade", "adpia"...
    platform = Column(String, nullable=True)       # ví dụ: "shopee", "lazada", "tiki"
    template = Column(String, nullable=False)      # ví dụ: "https://go.example/deep_link?url={target}&sub1={sub1}"
    default_params = Column(JSON, nullable=True)   # ví dụ: {"sub1": "my_subid_default"}
    enabled = Column(Boolean, default=True)

    __table_args__ = (
        # Ràng buộc duy nhất theo (network, platform). Lưu ý: NULL trong platform có thể không unique tuỳ DB.
        UniqueConstraint("network", "platform", name="uq_network_platform"),
    )
# --- THÊM MỚI: bảng product_offers ---
class ProductOffer(Base):
    __tablename__ = "product_offers"
    id = Column(Integer, primary_key=True, index=True)

    # định danh nguồn
    source = Column(String, default="accesstrade", index=True)
    source_id = Column(String, index=True)          # id/sku từ nguồn
    merchant = Column(String, index=True)           # shopee/lazada/tiki/...

    title = Column(String, nullable=False)
    url = Column(String, nullable=False)            # link gốc sản phẩm
    affiliate_url = Column(String, nullable=True)   # nếu feed đã có sẵn
    image_url = Column(String, nullable=True)

    price = Column(Float, nullable=True)
    currency = Column(String, default="VND")
    campaign_id = Column(String, index=True)   # campaign chứa sản phẩm

    # --- NEW (V2): các trường phục vụ kiến trúc hybrid 3 lớp ---
    approval_status = Column(String, index=True, nullable=True)         # successful/pending/unregistered
    eligible_commission = Column(Boolean, default=False)                # true nếu approval=successful & campaign running
    source_type = Column(String, nullable=True)                         # datafeed | promotions | top_products | manual
    affiliate_link_available = Column(Boolean, default=False)           # có aff_link/deeplink hợp lệ
    product_id = Column(String, index=True, nullable=True)              # id sản phẩm theo nguồn (nếu có)

    extra = Column(Text, nullable=True)             # string JSON tuỳ ý
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

# --- NEW: bảng price_history (lưu lịch sử giá) ---
class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, ForeignKey("product_offers.id"), index=True, nullable=False)
    price = Column(Float, nullable=True)
    currency = Column(String, default="VND")
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

# --- NEW: bảng campaigns (thông tin chiến dịch) ---
class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String, unique=True, index=True, nullable=False)
    merchant = Column(String, index=True, nullable=True)
    name = Column(String, nullable=True)
    status = Column(String, index=True, nullable=True)          # running/paused/ended/...
    approval = Column(String, nullable=True)                    # auto/manual/...
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)

    # trạng thái đăng ký/duyệt của PUBLISHER (bạn)
    user_registration_status = Column(String, index=True, nullable=True)  # NOT_REGISTERED/PENDING/APPROVED

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

# --- NEW: bảng commission_policies (chính sách hoa hồng theo campaign) ---
class CommissionPolicy(Base):
    __tablename__ = "commission_policies"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String, index=True)       # liên kết theo khóa campaign_id
    reward_type = Column(String, nullable=True)    # CPS/CPA/CPI...
    sales_ratio = Column(Float, nullable=True)     # % hoa hồng (nếu có)
    sales_price = Column(Float, nullable=True)     # hoa hồng cố định (nếu có)
    target_month = Column(String, nullable=True)   # điều kiện theo tháng (nếu có)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

# --- NEW: bảng promotions (khuyến mãi theo campaign) ---
class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String, index=True)       # liên kết theo khóa campaign_id
    name = Column(String, nullable=True)           # tên khuyến mãi
    content = Column(Text, nullable=True)          # mô tả ngắn
    start_time = Column(DateTime, nullable=True)   # thời gian áp dụng
    end_time = Column(DateTime, nullable=True)
    coupon = Column(String, nullable=True)         # mã giảm giá (nếu có)
    link = Column(String, nullable=True)           # link KM (nếu có)

    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
