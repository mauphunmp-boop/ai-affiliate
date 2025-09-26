## Performance / Web Vitals Strategy

### Route Preloading
- Hover/focus preloads lazy routes (xem `AppLayout.jsx` sử dụng global `window.__routePreloaders`).
- Idle prefetch registry trong `main.jsx` (không cản render chính).

### Web Vitals Collection
- `utils/webVitals.js` dùng dynamic import `web-vitals` và callback `initWebVitals(reportFn)`.
- Mặc định an toàn khi module không có (catch silent).
- Có thể gửi metric lên backend (định nghĩa endpoint ví dụ: POST `/metrics/vitals`).

### Rendering Optimizations
- DataTable memo hóa pipeline filter + sort (`useMemo`).
- Lazy route splits giảm initial bundle cho các trang ít truy cập.
- JSON parser riêng cung cấp thông tin lỗi mà không render lại nặng.

### Next Opportunities
- Virtualize hàng nếu > 1000 (react-virtualized / @tanstack/react-virtual).
- Server-side pagination khi dataset lớn.
- Prefetch API song song với preload route (cache layer).
