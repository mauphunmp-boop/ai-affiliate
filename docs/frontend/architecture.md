## Frontend Architecture Overview

### Core Stack
- React 19 + React Router v7 (createBrowserRouter) + Suspense lazy loading
- MUI 7 (custom theme with light/dark mode via `ColorModeProvider`)
- Axios instance with normalized error interceptor (`api.js`)
- State persistence: custom hook `usePersistedState`
- Notifications: queued `NotificationProvider` (dedupe, variants)

### Layout & Theming
- `AppLayout` cung cấp AppBar + Drawer tĩnh, Dark Mode toggle và OnboardingTip
- Theme được build trong `theme.js` (palette, shape, typography, component overrides)

### Data Rendering
- `DataTable` cung cấp: filter nhanh, sort client, ẩn/hiện cột, pagination, refresh, empty component slot, lựa chọn hàng (multi-select) và callback `onState` để hỗ trợ bulk actions (delete, enable/disable, invert selection) + CSV export
- Row identity ưu tiên `row.id` -> `row.key` -> JSON fallback
- Bộ lọc Enabled (All/ON/OFF) thực hiện ở cấp page trước khi truyền `rows` vào DataTable (TemplatesPage)

### Reusable Components
- `CopyButton`: copy với trạng thái tạm + aria-live
- `ConfirmDialog`: xác nhận hành động phá huỷ
- `OnboardingTip`: hướng dẫn khi mới vào app
- `GlossaryTerm`: tooltip giải thích thuật ngữ (shortlink, template...)
- `EmptyState`: standardized empty UI (đang dùng qua slot DataTable)
-- `TemplateWizard`: flow 2 bước tạo nhanh template (platform + template + default params) giúp người không chuyên dễ bắt đầu
- Live region (aria-live polite) trên TemplatesPage thông báo kết quả bulk actions hỗ trợ người dùng screen reader

### Error & Offline Handling
- `ErrorBoundary`: bao ngoài `RouterProvider`, hiển thị stack dev-mode
- `OfflineBanner`: cảnh báo mất kết nối (window online/offline events)

### Pages (Chính)
- ShortlinksPage: quản lý shortlinks với bộ lọc persisted
- ConvertTool: auto-detect platform + tham số tracking động
- TemplatesPage: CRUD + auto-generate templates
- OffersListPage: xem danh sách offers (filter/pagination client)
- AI Assistant: lịch sử chat localStorage

### Persistence Keys (tiêu biểu)
- `shortlinks_q`, `shortlinks_min`, `shortlinks_order`
- `offers_merchant`, `offers_category`, `offers_skip`, `offers_limit`
- `convert_url`, `convert_platform`, `convert_params`
- `ai_chat_history_v1`
- `pref_dark_mode`, `onboarding_v1_dismissed`

### Testing Strategy
- Vitest + React Testing Library under `src/test`
- Unit/feature tests cho: debounce filter, auto-detect platform, notification queue, DataTable sort/filter, OnboardingTip, CopyButton

### Extension Points / Next Steps
- Server-side pagination integration (replace client slice)
- Bulk actions đã gồm: delete, enable, disable, invert selection (TemplatesPage). Có thể mở rộng thêm tagging sau.
- i18n layer (wrap GlossaryTerm / notifications)
- Capture client logs + error boundary reports gửi backend
