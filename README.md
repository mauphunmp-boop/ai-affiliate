# AI Affiliate Advisor

[Tiếng Việt (README.vi.md)](./README.vi.md)

Monorepo: FastAPI (backend) + React/Vite (frontend) + Postgres.

## Quy ước Excel (bắt buộc)

Tất cả file Excel của dự án (export/import) đều phải có 2 hàng tiêu đề ở mỗi sheet:

- Hàng 1: tên cột kỹ thuật (tên gốc, ví dụ: `id`, `source_id`, `merchant`, `url`, ...). Đây là header thực (df.columns).
- Hàng 2: tên cột tiếng Việt (human-readable, ví dụ: `Mã ID`, `Mã nguồn`, `Nhà bán`, `Link gốc`, ...).



## Chạy nhanh (Docker)

- Backend API: http://localhost:8000/docs
# AI Affiliate Advisor

Monorepo: FastAPI (backend) + React/Vite (frontend) + Postgres. Hệ thống ingest hợp nhất theo provider (hiện hỗ trợ Accesstrade) và quy trình Excel v2.

## Chạy nhanh (Docker)

- Backend API: http://localhost:8000/docs
- Frontend: http://localhost:5173

## Dev không Docker

- Backend: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Frontend: `npm run dev -- --host`

## Ingest API hợp nhất

Các endpoint provider-agnostic (mặc định provider=accesstrade):

- POST `/ingest/campaigns/sync` — Đồng bộ campaigns
- POST `/ingest/promotions` — Ingest promotions (có thể tạo offer tối thiểu từ khuyến mãi)
- POST `/ingest/top-products` — Ingest top products
- POST `/ingest/datafeeds/all` — Ingest toàn bộ datafeeds (tự phân trang)
- POST `/ingest/products` — Ingest sản phẩm thủ công (điểm vào chung)

Payload mẫu:

```
POST /ingest/products
{
	"provider": "accesstrade",
	"path": "/v1/datafeeds",
	"params": {"merchant": "tikivn", "page": "1", "limit": "50"}
}
```

Lưu ý: Các route cũ đã bị loại bỏ trên OpenAPI; vui lòng dùng các route hợp nhất phía trên.

## Excel v2 (Export/Import)

Chuẩn Excel áp dụng cho cả export và import, gồm 4 sheet độc lập:

- Products: chứa cột `source_type` và không còn cột `extra_raw`. Hỗ trợ các nguồn: `datafeeds`, `top_products`, `promotions`, `manual`, `excel`.
- Campaigns: chỉ liệt kê các campaign có `user_registration_status` ∈ {APPROVED, SUCCESSFUL}.
- Commissions: dữ liệu chính sách hoa hồng độc lập.
- Promotions: khuyến mãi độc lập, có thêm cột `merchant` (map từ campaign nếu có).

Quy ước tiêu đề 2 hàng cho mỗi sheet:
- Hàng 1: tên cột kỹ thuật (vd: `id`, `source_id`, `merchant`, `url`, ...). Đây là header thực (df.columns).
- Hàng 2: tên cột tiếng Việt (human-readable). Ít nhất 1/3 số cột hiện diện phải khớp với bản dịch; nếu không import sẽ bị từ chối (400).

Endpoint liên quan Excel:
- GET `/offers/export-excel` — Xuất 4 sheet như trên; luôn có 2 hàng tiêu đề.
- GET `/offers/export-template` — Tải file template trống đúng cấu trúc (4 sheet, 2 hàng tiêu đề, đánh dấu (*) ở các cột bắt buộc của Products).
- POST `/offers/import-excel` — Import sheet `Products` từ file Excel theo định dạng 2 hàng tiêu đề. Bắt buộc: `merchant`, `title`, `price`, và tối thiểu một trong `url` hoặc `affiliate_url`. Trường `source_id` nếu để trống sẽ được tự sinh (ưu tiên hash từ URL; nếu không có URL thì hash từ `title+merchant`). Nếu thiếu `affiliate_url` nhưng có `url` và đã cấu hình template deeplink cho `merchant`, hệ thống sẽ tự chuyển `url` → `affiliate_url`.

Import xử lý NaN/ô trống an toàn (coerce sang None), tự set `source_type=excel`, tự sinh `source_id` khi trống, tự chuyển `url` → `affiliate_url` khi có template, và có thống kê `skipped_required` + chi tiết lỗi thiếu trường bắt buộc.

## Kiểm thử

- Bộ test pytest đã bao gồm:
	- Ingest hợp nhất (campaigns, promotions, top-products, datafeeds)
	- Kiểm tra offers/check
	- Excel export structure và import validations

Chạy test:

```bash
pytest -q
```

## Smoke khi chưa có Postgres

Một số smoke test hoặc gọi thử endpoint có thể fail khi Postgres chưa chạy vì app tạo bảng ngay khi import. Khi cần chạy nhanh không kèm Postgres, hãy override kết nối sang SQLite trong tiến trình test:

```python
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# import app sau khi set biến môi trường
```

Trong pytest, các fixture đã cấu hình sẵn SQLite in-memory + StaticPool, đảm bảo test chạy độc lập.

## Operations

- Disk usage alerts (optional)
	- Helper script `scripts/disk_check.sh` warns when `/` or `/data` exceed thresholds.
	- Run manually: `scripts/disk_check.sh 85 90` (defaults to 85% and 90%).
	- Cron example (every 30 minutes):
		- Edit crontab: `crontab -e`
		- Add line:
			`*/30 * * * * /home/phu/projects/ai-affiliate/scripts/disk_check.sh 85 90 | logger -t ai-affiliate-disk`
		- Check syslog for entries tagged `ai-affiliate-disk`.



