# API Reference (Excel Schemas)

Tài liệu này mô tả cấu trúc file Excel dùng cho import/export và một số endpoint liên quan. Nội dung phản ánh đúng code hiện tại trong backend.

## Sheets Overview (v2)
- Products: Chỉ sản phẩm từ API (datafeeds/top_products, promotions, manual, excel), có cột `source_type` để phân biệt; dùng cho import/export.
- Campaigns: Danh sách chiến dịch đã duyệt (APPROVED/SUCCESSFUL), độc lập, không phụ thuộc sản phẩm.
- Commissions: Danh sách chính sách hoa hồng theo campaign, độc lập.
- Promotions: Danh sách khuyến mãi, độc lập; có cột `merchant` (join từ campaign khi có).

Quan trọng — 2 hàng header bắt buộc cho MỌI sheet:
- Hàng 1: tiêu đề kỹ thuật (tên cột chuẩn, ví dụ: `source_id`, `campaign_id`, ...). Đây là header thực sự của bảng.
- Hàng 2: tiêu đề tiếng Việt (hiển thị). Backend khi import sẽ xác thực có hàng này và tự bỏ qua dòng này.
- Các cột bắt buộc sẽ có ký hiệu "(*)" ở tiêu đề tiếng Việt (hàng 2).

---

## Sheet: Products
Technical columns (exact names):
- id (export-only)
- source
- source_id
- source_type
- merchant (*)
- title (*)
- url (bắt buộc: url hoặc affiliate_url có ít nhất 1)
- affiliate_url (bắt buộc: url hoặc affiliate_url có ít nhất 1)
- image_url
- price (*)
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
- Mã nguồn
- Loại nguồn
- Nhà bán (*)
- Tên sản phẩm (*)
- Link gốc
- Link tiếp thị
- Ảnh sản phẩm
- Giá (*)
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

Yêu cầu khi import (Products):
- Bắt buộc: `merchant`, `title`, `price` và ít nhất một trong `url` hoặc `affiliate_url`.
- Không bắt buộc: `source_id`. Nếu thiếu, hệ thống sẽ tự sinh theo quy tắc bên dưới.

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

Yêu cầu khi import (Campaigns):
- Nếu thiếu `campaign_id`, hệ thống sẽ tự sinh mã theo quy tắc bên dưới.

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

Yêu cầu khi import (Commissions):
- Nếu thiếu `campaign_id`, hệ thống sẽ tự sinh mã theo quy tắc bên dưới (để upsert theo khóa tự nhiên). 

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

Yêu cầu khi import (Promotions):
- Nếu thiếu `campaign_id`, hệ thống sẽ tự sinh mã theo quy tắc bên dưới.

---

## Import Notes
- Endpoint: `POST /offers/import-excel` — đọc tối đa 4 sheet nếu có: `Products`, `Campaigns`, `Commissions`, `Promotions` (nếu không có `Products`, sẽ đọc sheet đầu tiên như fallback để tương thích).
- Bắt buộc 2 hàng header: hàng 1 là tên cột kỹ thuật; hàng 2 là tiêu đề tiếng Việt (backend xác thực và tự bỏ qua dòng này).
- Bắt buộc (Products): `merchant`, `title`, `price`, và tối thiểu một trong `url` hoặc `affiliate_url`.
- KHÔNG bắt buộc `source_id` cho Products; nếu thiếu, hệ thống tự sinh.

Aliases khi import Products:
- source_id: `source_id` | `product_id` | `id`
- merchant: `merchant` | `campaign`
- title: `title` | `name`
- url: `url` | `landing_url`
- affiliate_url: `affiliate_url` | `aff_link`
- image_url: `image_url` | `image` | `thumbnail`
- price: `price`
- currency: `currency` (default `VND`)

Upsert/replace theo khoá tự nhiên:
- Products: (source, source_id) với `source="excel"` khi import; nếu trùng thì ghi đè toàn bộ (bao gồm `extra`).
- Campaigns: `campaign_id`.
- Commissions: (campaign_id, reward_type, target_month).
- Promotions: (campaign_id, name, start_time, end_time).

Auto-generate ID (khi thiếu): tổng độ dài 14 ký tự, dạng `ex` + tiền tố sheet + dãy số:
- Products → source_id: tiền tố `p` → `expXXXXXXXXXXXX` (đảm bảo không trùng trong DB đối với source='excel').
- Campaigns → campaign_id: tiền tố `ca` → `excaXXXXXXXXXX` (tránh trùng trong batch/file).
- Commissions → (thiếu campaign_id trong sheet Commissions): tiền tố `cm` → `excmXXXXXXXXX`.
- Promotions → (thiếu campaign_id trong sheet Promotions): tiền tố `pr` → `exprXXXXXXXXX`.

Chính sách khi import (cấu hình qua policy):
- only_with_commission: chỉ ghi Products khi có đủ dấu hiệu commission (flag hoặc dữ liệu commission). Mặc định tắt.
- check_urls: chỉ ghi Products khi link sống. Mặc định tắt.

Kết quả trả về (ví dụ):
```
{
  "ok": true,
  "imported": 12,           // Products
  "campaigns": 3,
  "commissions": 5,
  "promotions": 4,
  "skipped_required": 1,
  "errors": [ { "row": 5, "missing": ["price"] } ]
}
```

Mẹo: Dùng endpoint `GET /offers/export-template` để tải file mẫu đúng định dạng (đã có sẵn 2 hàng header, đánh dấu (*) ở Products).

## Export Notes
- Endpoint: `GET /offers/export-excel` — xuất 4 sheet độc lập (Products/Campaigns/Commissions/Promotions). Không còn tham số `desc_mode`.
- Endpoint: `GET /offers/export-template` — tải template rỗng 4 sheet với 2 hàng header đúng chuẩn.

## Endpoint: POST /ingest/commissions
Nhập danh sách chính sách hoa hồng (commission policies) cho các campaign đã chọn. Hỗ trợ lọc theo campaign cụ thể, theo merchant, hoặc toàn bộ campaign đã APPROVED đang chạy.

- Path: `POST /ingest/commissions`
- Provider hiện hỗ trợ: `accesstrade` (mặc định)
- Tham số (body JSON):
  - provider: string, optional (mặc định `accesstrade`)
  - campaign_ids: string[], optional — danh sách campaign muốn lấy chính sách
  - merchant: string, optional — lọc theo merchant khi không truyền `campaign_ids`
  - max_campaigns: number, optional — giới hạn số campaign quét
  - verbose: boolean, optional — ghi log chi tiết

Ví dụ body:

- Theo campaign cụ thể:
```
{ "provider": "accesstrade", "campaign_ids": ["CAMP3"] }
```

- Theo merchant:
```
{ "provider": "accesstrade", "merchant": "tikivn" }
```

- Tất cả campaign APPROVED đang chạy:
```
{ "provider": "accesstrade" }
```

Phản hồi mẫu:
```
{ "ok": true, "campaigns": 10, "policies_imported": 85 }
```

---

## Change Log
- 2025-09-24: v2.1 — Chuẩn hóa 2 hàng header (kỹ thuật + TV) cho import; Products yêu cầu `price` và KHÔNG bắt buộc `source_id` (tự sinh nếu thiếu). Bổ sung import cho 4 sheet; quy tắc auto-gen mã 14 ký tự `ex+p|ca|cm|pr...`; cập nhật endpoint `POST /ingest/commissions`; export-excel bỏ `desc_mode`.
- 2025-09-22: v2 — Chuyên biệt 4 sheet độc lập; Products thêm `source_type`, bỏ `extra_raw`; đánh dấu cột bắt buộc; thêm endpoint tải template.
- 2025-09-21: v1 — 4 sheet kèm join theo sản phẩm; thêm các trường datafeeds; mở rộng Campaigns fields.
