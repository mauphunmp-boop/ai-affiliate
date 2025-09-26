# Ghi chú Migration nhẹ

Tài liệu này mô tả các bước migration *không dùng Alembic* đã được mã hoá thủ công trong hàm `apply_simple_migrations` (`backend/database.py`).

## 1. Mục tiêu
- Bổ sung cột còn thiếu khi nâng cấp schema (product_offers.*, affiliate_templates.platform, v.v.).
- Làm sạch dữ liệu placeholder (API_MISSING/NO_DATA) trong bảng `campaigns`.
- Loại bỏ constraint cũ không còn phù hợp với kiến trúc mới.

## 2. Constraint legacy đã gỡ
Trước đây bảng `affiliate_templates` có unique constraint theo `(merchant, network)` (`uq_merchant_network`). Kiến trúc mới dùng cặp `(network, platform)` (constraint `uq_network_platform`).

Hàm `apply_simple_migrations` sẽ:
1. Thêm cột `platform` nếu thiếu.
2. Cố gắng `DROP CONSTRAINT uq_merchant_network` trên Postgres nếu còn tồn tại.

SQLite: bỏ qua thao tác drop constraint (không hỗ trợ trực tiếp) nhưng không ảnh hưởng vì test/dev thường dùng DB mới.

## 3. Cách chạy
Chỉ cần khởi động lại service (uvicorn / docker compose). Ứng dụng tự gọi `apply_simple_migrations` khi import `backend/main.py`.

## 4. Kiểm tra sau migration
Trong Postgres:
```sql
SELECT conname
FROM pg_constraint c
JOIN pg_class t ON c.conrelid = t.oid
WHERE t.relname = 'affiliate_templates';
```
Kỳ vọng KHÔNG còn `uq_merchant_network`.

## 5. Rollback
Do migration dùng lệnh `ALTER TABLE` tối thiểu và xoá constraint cũ, rollback thủ công nếu cần:
```sql
ALTER TABLE affiliate_templates ADD CONSTRAINT uq_merchant_network UNIQUE (merchant, network);
```
Chỉ làm nếu quay lại logic merchant-first (không khuyến nghị).

## 6. Ghi chú an toàn
- Logic CRUD hiện có đường “upgrade” record legacy: nếu có bản ghi `(merchant=<platform>, platform IS NULL)` sẽ nâng cấp bằng cách gán `platform=<platform>` thay vì chèn mới.
- Việc gỡ constraint cũ giúp tránh `UniqueViolation` khi auto sinh template.

## 7. Khi nào cần Alembic?
Nếu schema thay đổi thường xuyên hoặc cần rollback phức tạp, hãy thêm Alembic. Với phạm vi nhỏ hiện tại (ít bảng, ít thay đổi), script nhẹ là đủ.

## 8. Checklist nhanh
- [ ] Service khởi động không lỗi.
- [ ] Endpoint `/aff/templates/auto-from-campaigns` không còn lỗi UniqueViolation.
- [ ] Constraint cũ biến mất (Postgres check).
- [ ] Templates cũ merchant-first được nâng cấp khi gọi CRUD.

Hoàn tất.
