# API Reference (Excel Schemas)

This Markdown complements `API Reference.pdf` in a text-friendly format for field names used in import/export Excel. It reflects the current backend implementation.

## Sheets Overview
- Products: Datafeed/Offers normalized fields per product.
- Campaigns: Synchronized campaign information (per product/campaign join).
- Commissions: Commission policies aggregated by campaign (per product row).
- Promotions: Promotions aggregated by campaign (per product row).

> Note: The first row in each sheet is a Vietnamese human-readable header. The backend import automatically detects and skips this header row.

---

## Sheet: Products
Technical columns (exact names):
- id
- source
- source_id
- merchant
- title
- url
- affiliate_url
- image_url
- price
- currency
- campaign_id
- product_id
- affiliate_link_available
- domain
- sku
- discount
- discount_amount
- discount_rate
- status_discount
- updated_at
- desc
- cate
- shop_name
- update_time_raw
- extra_raw

Vietnamese header (display only):
- Mã ID
- Nguồn
- Mã nguồn
- Nhà bán
- Tên sản phẩm
- Link gốc
- Link tiếp thị
- Ảnh sản phẩm
- Giá
- Tiền tệ
- Chiến dịch
- Mã sản phẩm nguồn
- Có affiliate?
- Tên miền
- SKU
- Giá KM
- Mức giảm
- Tỷ lệ giảm (%)
- Có khuyến mãi?
- Ngày cập nhật
- Mô tả chi tiết
- Danh mục
- Tên cửa hàng
- Thời gian cập nhật từ nguồn
- Extra gốc

Notes:
- `product_id`, `affiliate_link_available`, and `update_time_raw` derive from API normalization in `accesstrade_service.map_at_product_to_offer`.
- `extra_raw` contains JSON string with additional raw attributes.

---

## Sheet: Campaigns
Technical columns:
- product_id
- merchant
- campaign_id
- campaign_name
- approval_type
- user_status
- status
- start_time
- end_time
- category
- conversion_policy
- cookie_duration
- cookie_policy
- description
- scope
- sub_category
- type
- campaign_url

Vietnamese header:
- ID sản phẩm
- Nhà bán
- Mã chiến dịch
- Tên chiến dịch
- Approval
- Trạng thái của tôi
- Tình trạng
- Bắt đầu
- Kết thúc
- Danh mục chính
- Chính sách chuyển đổi
- Hiệu lực cookie (giây)
- Chính sách cookie
- Mô tả
- Phạm vi
- Danh mục phụ
- Loại
- URL chiến dịch

Notes:
- `user_status` may be NOT_REGISTERED/PENDING/APPROVED or API_EMPTY/API_MISSING depending on logs.

---

## Sheet: Commissions
Technical columns:
- product_id
- sales_ratio
- sales_price
- reward_type
- target_month

Vietnamese header:
- ID sản phẩm
- Tỷ lệ (%)
- Hoa hồng cố định
- Kiểu thưởng
- Tháng áp dụng

Notes:
- Multiple policies are aggregated using `; `.
- If no data exists, `reward_type` may contain `API_EMPTY` or `API_MISSING` per log analysis.

---

## Sheet: Promotions
Technical columns:
- product_id
- promotion_name
- promotion_content
- promotion_start_time
- promotion_end_time
- promotion_coupon
- promotion_link

Vietnamese header:
- ID sản phẩm
- Tên khuyến mãi
- Nội dung
- Bắt đầu KM
- Kết thúc KM
- Mã giảm
- Link khuyến mãi

Notes:
- Multiple promotions aggregated using `; `.
- If no data exists, `promotion_name` may be `API_EMPTY` or `API_MISSING` depending on merchant log.

---

## Import Notes
- Upload endpoint: `POST /offers/import-excel` reads `Products` sheet (fallback to the first sheet if missing).
- If the first row is the Vietnamese header, the backend automatically skips it.
- Accepted aliases while importing `Products`:
  - source_id: `source_id` | `product_id` | `id`
  - merchant: `merchant` | `campaign`
  - title: `title` | `name`
  - url: `url` | `landing_url`
  - affiliate_url: `affiliate_url` | `aff_link`
  - image_url: `image_url` | `image` | `thumbnail`
  - price: `price`
  - currency: `currency` (default `VND`)
- Policy flags for import (from DB, via `/policy-flags` APIs if present):
  - only_with_commission: when true, only import rows that have commission info.
  - check_urls: when true, only import rows whose `url` is alive.

---

## Change Log
- 2025-09-21: Introduced 4-sheet export format with Vietnamese header row and import compatibility.
- 2025-09-21: Added datafeeds fields to Products (domain, sku, discount, discount_amount, discount_rate, status_discount) and expanded Campaigns fields per API docs.
