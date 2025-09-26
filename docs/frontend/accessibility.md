## Accessibility & UX Enhancements

### Focus & Navigation
- Global standardized focus ring via `*:focus-visible` (outline + offset, dark-mode color tweak).
- Skip link (`.skip-link`) visible on focus for quick jump to main content.
- Keyboard shortcuts (TemplatesPage):
  - Alt+A: Chọn tất cả các dòng đã lọc
  - Alt+I: Đảo chọn
  - Alt+C: Bỏ chọn

### Live Regions
- `aria-live="polite"` region trên TemplatesPage thông báo kết quả bulk (delete / enable / disable / chọn nhanh).

### Reduced Motion
- Honours `prefers-reduced-motion: reduce` bằng cách rút ngắn animation/transition.

### Table Usability
- DataTable auto-dense cho màn hình hẹp.
- Hidden columns responsive (sm / md / lg breakpoints) tránh tràn ngang.
- Reset state (lọc/sort/ẩn cột/selection) một thao tác.

### Internationalization (i18n)
- `I18nProvider` + hook `useT()` hỗ trợ đa ngôn ngữ bước đầu (vi/en) cho navigation & một số thành phần.
  - Có thể mở rộng: truyền namespace hoặc fallback chain.

### Future Work (Đề xuất)
- Thêm announce khi pagination thay đổi.
- Tự động di chuyển focus về heading chính sau điều hướng route (focus management).
- Thêm mô tả cột (aria-describedby) cho cột bị ẩn do breakpoint.
