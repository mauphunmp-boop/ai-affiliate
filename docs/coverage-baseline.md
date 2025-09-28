# Coverage Baseline

Ngày tạo: 2025-09-28
Trạng thái: INITIAL PLACEHOLDER (chưa chèn số liệu – cần chạy `npm --prefix frontend test --silent --coverage` sau khi dọn act() warnings)

## Hướng dẫn cập nhật
1. Chạy toàn bộ test với coverage.
2. Mở file `frontend/coverage/coverage-summary.json`.
3. Lấy các giá trị: statements, branches, functions, lines (pct).
4. Điền vào bảng dưới.
5. Commit lại.

## Số liệu (điền sau)
| Metric      | %   | Covered | Total | Skipped |
|-------------|-----|---------|-------|---------|
| Statements  | TBD |         |       |         |
| Branches    | TBD |         |       |         |
| Functions   | TBD |         |       |         |
| Lines       | TBD |         |       |         |

## Ghi chú
- Baseline này được tạo sau khi đã loại bỏ các cảnh báo act() chính (LinksManager, NotificationProvider queue, Dashboard).
- Sau khi điền số liệu: thiết lập threshold tối thiểu trong `vitest.config.js` thấp hơn hoặc bằng các giá trị này để tránh fail lần đầu.
- Nâng dần threshold sau mỗi cải thiện.

## Quy ước
- Không chỉnh sửa số liệu baseline trừ khi tái tạo baseline có lý do rõ ràng (ví dụ: refactor lớn bỏ nhiều mã chết).
- Nếu cần tái tạo: tạo mục "History" bên dưới.

## Lịch sử
- 2025-09-28: Khởi tạo placeholder.
