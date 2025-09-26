## Frontend Testing Guide

### Tech
- Vitest (jsdom environment)
- @testing-library/react + user-event
- Coverage reporters: text, lcov (`vitest.config.js`)

### Running Tests
Chạy toàn bộ (ví dụ trong thư mục `frontend`):
`npm test`

### Adding a Test
1. Tạo file dưới `src/test/unit/YourComponent.test.jsx`
2. Import component + wrap cần thiết (NotificationProvider, ColorModeProvider nếu theme liên quan)
3. Dùng `screen.getBy...` và `userEvent` mô phỏng tương tác

### Mock HTTP
Ví dụ mock module:
```
vi.mock('../api/offers', () => ({ listOffers: vi.fn().mockResolvedValue({ data: [] }) }));
```

### Patterns Hiện Có
- Debounce: đợi `setTimeout` (>= thời lượng + buffer 50ms)
- Auto-detect platform: nhập URL và `waitFor` giá trị select
- Notification queue: kiểm tra chuỗi hiển thị message
- DataTable: sort → filter → assert rows DOM

### Gợi Ý Nâng Cao
- Kiểm tra pagination: tạo 60 rows, pageSize=25, click "Sau" → số row hiển thị đúng
- Column hide: mở menu column, uncheck cột, assert cell biến mất
- Dark mode toggle: click toggle, kiểm tra `document.body` màu nền (hoặc theme.palette.mode qua context mock)
- ErrorBoundary: component test ném lỗi → render fallback
- OfflineBanner: mock `navigator.onLine = false` + dispatch event

### Coverage Mục Tiêu
- Ngắn hạn: ≥55% lines
- Trung hạn: ≥70% (bổ sung tests pagination, column hide, error boundary)

### Tips
- Tránh snapshot lớn khó bảo trì; ưu tiên assert hành vi
- Tách helper `renderWithProviders` để giảm lặp wrapper
