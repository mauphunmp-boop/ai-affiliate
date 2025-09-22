# AI Affiliate Advisor

[Tiếng Việt (README.vi.md)](./README.vi.md)

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

### Chạy unit tests backend (tuỳ chọn)

- Cài `pytest` (nếu chưa có) và chạy:

```bash
pip install pytest
pytest
```

Tests tối thiểu kiểm tra sự tồn tại các ingest endpoint hợp nhất, xác nhận preset TikTok Shop đã bị gỡ, và payload filter của `/ingest/datafeeds/all` được chấp nhận.




## Ingest API (consolidated)

### Nhanh: Script smoke test (tùy chọn)

Để kiểm tra nhanh OpenAPI và gọi thử một số luồng ingest cơ bản:

```bash
# Chạy khi docker-compose đang chạy (web:8000)
bash scripts/smoke.sh

# Tùy chọn: ingest nhẹ 1 trang để có data (nếu DB trống)
RUN_INGEST=1 bash scripts/smoke.sh

# Tuỳ chọn: lọc theo merchant/campaign-id (nếu script hỗ trợ)
MERCHANT=tikivn RUN_INGEST=1 bash scripts/smoke.sh
```

Script sẽ:
- Kiểm tra các endpoint ingest hợp nhất hiển thị trên OpenAPI
- Kiểm tra nhanh danh sách sản phẩm và gọi `/offers/check/{id}`
- (Nếu bật RUN_INGEST) chạy ingest datafeeds 1 trang để có dữ liệu mẫu

Lưu ý: Các endpoint legacy đã được xoá khỏi mã nguồn trong phiên bản hiện tại. Hãy dùng các endpoint hợp nhất:
- POST `/ingest/campaigns/sync`
- POST `/ingest/promotions`
- POST `/ingest/top-products`
- POST `/ingest/datafeeds/all`
- POST `/ingest/products`

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



