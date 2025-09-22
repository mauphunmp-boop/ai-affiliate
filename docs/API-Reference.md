# API Reference (Excel Schemas)

This Markdown complements `API Reference.pdf` in a text-friendly format for field names used in import/export Excel. It reflects the current backend implementation.

## Sheets Overview (v2)
- Products: Chỉ sản phẩm từ API (datafeeds/top_products), có cột `source_type` để phân biệt; dùng cho import/export.
- Campaigns: Danh sách chiến dịch đã duyệt (APPROVED/SUCCESSFUL), độc lập, không phụ thuộc sản phẩm.
- Commissions: Danh sách chính sách hoa hồng theo campaign, độc lập.
- Promotions: Danh sách khuyến mãi, độc lập; có cột `merchant` (join từ campaign khi có).

Lưu ý: Hàng đầu tiên của mỗi sheet là tiêu đề tiếng Việt (hiển thị). Backend khi import sẽ tự bỏ qua hàng này. Các cột bắt buộc sẽ có ký hiệu "(*)" trong tiêu đề TV.

---

## Sheet: Products
Technical columns (exact names):
- id (export-only)
- source
- source_id (*)
- source_type
- merchant (*)
- title (*)
- url (bắt buộc: url hoặc affiliate_url có ít nhất 1)
- affiliate_url (bắt buộc: url hoặc affiliate_url có ít nhất 1)
- image_url
- price
- currency (default VND nếu trống)
- campaign_id
- product_id
- affiliate_link_available
- domain
- sku
- discount
- discount_amount
- discount_rate
- status_discount
- updated_at (export-only)
- desc
- cate
- shop_name
- update_time_raw

Vietnamese header (display only):
- Mã ID
- Nguồn
- Mã nguồn (*)
- Loại nguồn
- Nhà bán (*)
- Tên sản phẩm (*)
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

Notes:
- `source_type` phân biệt nguồn ingest: datafeeds/top_products/promotions/manual/excel.
- `product_id`, `affiliate_link_available`, và `update_time_raw` được chuẩn hóa từ dữ liệu API.

---

## Sheet: Campaigns (independent)
Technical columns:
- campaign_id
- merchant
- campaign_name
- approval_type
- user_status (APPROVED/SUCCESSFUL)
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
- Mã chiến dịch
- Nhà bán
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

## Sheet: Commissions (independent)
Technical columns:
- campaign_id
- reward_type
- sales_ratio
- sales_price
- target_month

Vietnamese header:
- Mã chiến dịch
- Kiểu thưởng
- Tỷ lệ (%)
- Hoa hồng cố định
- Tháng áp dụng

Notes:
- Multiple policies are aggregated using `; `.
- If no data exists, `reward_type` may contain `API_EMPTY` or `API_MISSING` per log analysis.

---

## Sheet: Promotions (independent)
Technical columns:
- campaign_id
- merchant
- name
- content
- start_time
- end_time
- coupon
- link

Vietnamese header:
- Mã chiến dịch
- Nhà bán
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
- Endpoint: `POST /offers/import-excel` — đọc sheet `Products` (fallback sheet đầu tiên nếu không có).
- Hàng đầu là tiêu đề tiếng Việt, có dấu "(*)" tại cột bắt buộc; backend tự bỏ qua hàng này khi import.
- Cột bắt buộc: `source_id`, `merchant`, `title`, và ít nhất một trong `url` hoặc `affiliate_url`.
- Aliases khi import Products:
  - source_id: `source_id` | `product_id` | `id`
  - merchant: `merchant` | `campaign`
  - title: `title` | `name`
  - url: `url` | `landing_url`
  - affiliate_url: `affiliate_url` | `aff_link`
  - image_url: `image_url` | `image` | `thumbnail`
  - price: `price`
  - currency: `currency` (default `VND`)
- Policy flags khi import:
  - only_with_commission: chỉ import hàng có thông tin commission (khi bật)
  - check_urls: chỉ import hàng có link sống (khi bật)

---

## Change Log
- 2025-09-22: v2 — Chuyên biệt 4 sheet độc lập; Products thêm `source_type`, bỏ `extra_raw`; đánh dấu cột bắt buộc; thêm endpoint tải template.
- 2025-09-21: v1 — 4 sheet kèm join theo sản phẩm; thêm các trường datafeeds; mở rộng Campaigns fields.
