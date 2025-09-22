# AI Affiliate Advisor

Monorepo: FastAPI (backend) + React/Vite (frontend) + Postgres.

## Quy ước Excel (bắt buộc)

Tất cả file Excel của dự án (export/import) đều phải có 2 hàng tiêu đề ở mỗi sheet:

- Hàng 1: tên cột kỹ thuật (tên gốc, ví dụ: `id`, `source_id`, `merchant`, `url`, ...). Đây là header thực (df.columns).
- Hàng 2: tên cột tiếng Việt (human-readable, ví dụ: `Mã ID`, `Mã nguồn`, `Nhà bán`, `Link gốc`, ...).



## Chạy nhanh (Docker)

- Backend API: http://localhost:8000/docs
- Frontend: http://localhost:5173

## Dev không Docker

- Backend: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Frontend: `npm run dev -- --host`




## Ingest API (consolidated)

Các endpoint ingest đã được tinh gọn theo hướng provider-agnostic. Hiện hỗ trợ provider `accesstrade` (mặc định nếu không truyền).

- POST `/ingest/campaigns/sync` — Đồng bộ campaigns
- POST `/ingest/promotions` — Ingest promotions
- POST `/ingest/top-products` — Ingest top products
- POST `/ingest/datafeeds/all` — Ingest toàn bộ datafeeds (tự phân trang)
- POST `/ingest/products` — Ingest sản phẩm thủ công (ví dụ datafeeds theo merchant)

Payload mẫu:

```
POST /ingest/products
{
	"provider": "accesstrade",
	"path": "/v1/datafeeds",
	"params": {"merchant": "tikivn", "page": "1", "limit": "50"}
}
```

Lưu ý: Các route cũ `/ingest/v2/*` và `/ingest/accesstrade/*` vẫn tồn tại để tương thích ngược nhưng đã ẩn khỏi OpenAPI, vui lòng chuyển sang dùng các route phía trên.



