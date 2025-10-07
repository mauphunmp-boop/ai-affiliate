Ingest refresh scheduler (mutex)

Mục tiêu
- Làm mới dữ liệu ingest theo chu kỳ nhưng nhẹ nhàng, không ảnh hưởng tư vấn sản phẩm.
- Tránh chạy chồng chéo nhờ khoá mutex lưu trong api_configs (name=ingest_policy).

Endpoints
- GET /scheduler/ingest/lock/status: xem tình trạng khoá.
- POST /scheduler/ingest/lock/release?force=true: buộc tháo khoá (cần X-Admin-Key nếu đặt).
- POST /scheduler/ingest/refresh: chạy orchestrator với các bước:
  1) campaigns sync (nhanh)
  2) promotions
  3) datafeeds (giới hạn trang)
  4) top-products (tuỳ chọn)

Logging/Observability
- Mỗi lần chạy orchestrator sẽ ghi vào `logs/ingest_refresh.jsonl` hai sự kiện `start` và `finish` (owner, ts, elapsed, imported...).
- Link-check rotate sau mỗi lần chạy sẽ lưu `linkcheck_last_ts` trong `ingest_policy.model` để tiện theo dõi.

Body mặc định
{
  "max_minutes": 8,
  "limit_per_page": 100,
  "max_pages": 3,
  "throttle_ms": 50,
  "page_concurrency": 4,
  "include_top_products": false
}

Lock
- Khoá lưu trong ingest_policy.model dưới các key: ingest_refresh_lock_owner, _ts, _ttl.
- TTL mặc định = max_minutes*60 + 60. Hết TTL coi như khoá hết hạn.

Cron
- Sử dụng script scripts/cron/run_ingest_refresh.sh (có jitter 0-90s) gọi endpoint.
- Đặt biến ADMIN_API_KEY nếu server yêu cầu.

Compose
- Thêm service sidecar hoặc dùng host cron trỏ tới endpoint public nội bộ.
