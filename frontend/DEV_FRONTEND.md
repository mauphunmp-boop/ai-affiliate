## Hướng dẫn phát triển Frontend

### Mục tiêu kiến trúc
1. Tối ưu UX cho người dùng không chuyên (đơn giản, rõ ràng, ít thao tác thừa).
2. Responsive mặc định: bảng chuyển sang card trên màn hình hẹp.
3. Accessibility: focus quản lý qua `RouteFocusWrapper`, khai báo `aria-label` với IconButton, thông báo qua `Snackbar` tránh spam.
4. Hiệu năng: Lazy preload route chính qua `window.__routePreloaders`, tránh render dư khi loading (sử dụng SkeletonSection).

### Pattern chính
| Chủ đề | Mô tả nhanh |
|--------|-------------|
| Data Fetch + State | API wrappers trong `src/api` hoặc `src/api/*.js`; xử lý lỗi chuẩn hóa ở interceptor axios. |
| Bảng dữ liệu | Dùng `DataTable` tuỳ biến: filter nhanh, ẩn cột, pagination client, responsiveCards (card view dưới breakpoint). |
| Skeleton | `SkeletonSection` với 3 biến thể (`table`, `cards`, `detail`) để tái sử dụng. |
| Onboarding | `GettingStartedPanel` tự ẩn khi có đủ API Configs & Templates. |
| Notifications | `NotificationProvider` dedupe + collapse lỗi giống nhau < 2.5s. |
| Focus & A11y | Trang cần tiêu đề `h5` có `data-focus-initial` để auto focus. Drawer/Modal: đảm bảo nội dung chính trong tab order. |
| Caching & Prefetch | `useApiCache` (TTL nhẹ 30–60s) + prefetch extras khi hover icon để giảm độ trễ mở chi tiết. |

### Responsive bảng → cards
Khi dùng `DataTable`:
```jsx
<DataTable
  responsiveCards
  cardTitleKey="name"
  cardSubtitleKeys={['merchant','status']}
  responsiveHiddenBreakpoints={{ price:'sm', source_type:'sm' }}
  ...
/>
```
Logic: tự động phát hiện breakpoint (sm mặc định) để chuyển sang danh sách thẻ.

### Skeleton guideline
- Chỉ hiển thị skeleton khi `loading && data.length === 0` để tránh nhấp nháy.
- Dạng `detail` áp dụng cho drawer/modal nội dung chiều cao thay đổi.

### Notification rules
- Sử dụng `useNotify()` với kiểu: `notify('error', msg)` / `notify({ type:'success', message:'...' })`.
- Lỗi lặp lại trong ~2.5s bị bỏ qua (collapseNetworkErrorsMs) để tránh flood.
- Tránh hiển thị raw stack; chuẩn hóa thông qua `error.normalized.message` ở interceptor.

### A11y checklist nhanh
- IconButton luôn có `aria-label` nếu không có text.
- Nút toggle/ẩn/hiện phải mô tả trạng thái: dùng điều kiện để đổi label.
- Có vùng aria-live (trong `DataTable`) để thông báo thay đổi phân trang, filter.
- Drawer/Modal: cung cấp tiêu đề đầu tiên (Typography variant h6/h5) để người dùng screen reader định vị.

### Route preload
`main.jsx` định nghĩa `window.__routePreloaders`. Màn hình idle sẽ preload các route quan trọng:
```js
['OffersListPage','TemplatesPage', ...].forEach(k => window.__routePreloaders[k]?.());
```
Giảm độ trễ lần đầu mở trang.

### Cấu trúc thư mục chính
- `components/`: thành phần chia sẻ (DataTable, Dialogs, SkeletonSection...).
- `pages/`: mỗi route page + logic fetch cục bộ.
- `api/`: wrapper & domain modules (offers, affiliate, ingest...).
- `i18n/`: provider + messages (t keys). Chuẩn hoá text để dễ dịch.

### Thêm trang mới
1. Tạo file trong `pages/<Domain>/<NewPage>.jsx`.
2. Thêm lazy import & route ở `main.jsx`.
3. Thêm vào navigation (`layout/AppLayout.jsx`) nếu là trang chính.
4. Đặt tiêu đề có `data-focus-initial`.
5. Nếu cần bảng → dùng `DataTable` (config card mode nếu quan trọng trên mobile).

### Testing gợi ý
- Unit test với vitest trong `src/__tests__` hoặc `src/test/unit` (theo mẫu đã có).
- Ưu tiên test behavior quan trọng (filter, shortcuts, notification dedupe).

### Dark / Light mode
Material UI theme toggle qua provider (ColorModeProvider). Khi thêm màu nền custom, dùng `bgcolor:'primary.main'` & `color:'primary.contrastText'` để tự động đổi.

### Hiệu năng nhỏ
- Tránh `.map` nặng trong render nếu có thể memo (sử dụng `React.useMemo`).
- Khi danh sách > 500 items xem xét virtualization sau (hiện chưa cần giai đoạn early dev).

### Caching & Prefetch (v0.2 → mở rộng v0.3)
Mục tiêu: Giảm round-trip lặp lại cho dữ liệu tương đối ổn định trong cửa sổ ngắn (danh sách offers, campaigns, summary) và làm mượt cảm giác mở drawer chi tiết.

#### Hook `useApiCache` (cập nhật v0.7: stale-while-refetch tuỳ chọn)
Chữ ký:
```
const { data, error, loading, stale, refresh, invalidate, refreshing } = useApiCache(
  key,                 // string duy nhất bao gồm tham số filter/sort
  () => fetcher(),     // hàm async trả về dữ liệu (đã unwrap res.data)
  { ttlMs=60000, enabled=true, refreshDeps=[], immediate=true, staleWhileRefetch=false }
);
```
Trạng thái:
- `loading`: đang có promise fetch chạy.
- `stale`: true khi `Date.now() - ts > ttlMs` (không auto refetch cho tới khi component mount/refreshDeps thay đổi hoặc gọi `refresh()`).
- `refresh()`: cưỡng bức fetch, bỏ qua TTL.
- `invalidate()`: đặt `ts=0` rồi fetch lại ngay.

Implementation: Map in-memory (`key -> { data, error, ts, promise, refreshing }`). Không dùng context để tránh rerender toàn cục; mỗi hook instance subscribe gián tiếp qua `force` state.

Nếu `staleWhileRefetch=true` và cache stale nhưng có `data`:
- Trả ngay `data` cũ (UX nhanh) với `{ loading:false, refreshing:true }`.
- Khởi động fetch nền, khi xong sẽ cập nhật `data` và `refreshing` trở về false.
Counters instrumentation tăng `backgroundRefresh`.

#### Quy ước đặt cache key
```
// Ví dụ offers list với filter:
const key = `offers:list:${page}-${pageSize}-${status||'all'}-${search||''}`;
```
Nguyên tắc: Thay thế giá trị falsy bằng hằng ổn định (`all`, `''`, `0`). Tránh object JSON.stringify trực tiếp nếu có thể (chi phí + order issues).

#### TTL khuyến nghị
| Loại dữ liệu | TTL đề xuất | Lý do |
|--------------|------------|-------|
| Campaigns summary | 60000 ms | Biến động chậm, đủ tươi cho dashboard. |
| Danh sách campaigns/offers | 30000 ms | Người dùng thường thao tác lọc trong cụm thời gian ngắn. |
| Extras (policies/promotions) | Prefetch không cache dài | Thường mở ngay sau hover; cache tạm trong một phiên truy cập. |

Không đặt TTL > 5 phút ở giai đoạn early (dễ gây nhầm dữ liệu cũ). Nếu cần dữ liệu realtime → bỏ caching hoặc TTL ngắn (5–10s) tùy domain.

#### Prefetch pattern (hover)
```jsx
<IconButton
  aria-label="Xem chi tiết"
  onMouseEnter={() => getOfferExtras(id)} // fire & forget; kết quả được reuse khi user mở drawer
  onFocus={() => getOfferExtras(id)}      // hỗ trợ keyboard nav
>
  <InfoOutlined />
</IconButton>
```
Yêu cầu: Prefetch chỉ nên idempotent & nhỏ. Không prefetch danh sách lớn / xuất Excel.

#### Khi nào KHÔNG dùng `useApiCache`
- Mutation ngay sau đó cần đọc lại (dùng invalidate hoặc fetch trực tiếp thay vì dựa dữ liệu cũ).
- Dữ liệu phụ thuộc auth scope thay đổi liên tục (role switching) → thêm prefix key chứa `userId|role`.
- Streaming / progressive update.

#### Invalidate chiến lược
Sau các mutation (ví dụ cập nhật offer):
```js
invalidateOffersList(); // custom wrapper: clearApiCache('offers:list:');
```
Ta có helper `clearApiCache(prefix)` để xóa hàng loạt. Nên gom các key cùng prefix theo domain (`offers:list:`, `campaigns:list:`).

#### Lộ trình nâng cấp tương lai
- Có thể chuyển sang `@tanstack/react-query` khi yêu cầu staleWhileRefetch, background refetch hoặc pagination phức tạp hơn. Giữ interface gần với query (data/error/loading/refresh) để giảm chi phí migration.

#### Anti-pattern tránh
- Gộp nhiều loại dữ liệu khác nhau cùng một key → khó invalidate chính xác.
- Key dựa trên `JSON.stringify(filters)` mà thứ tự thuộc tính không cố định.
- Gọi `refresh()` bên trong render path → vòng lặp.

### Kế hoạch tiếp nối (future)
- Test e2e (Playwright) cho flows chính: Convert link, Tạo template, Mở chi tiết Offer.
- Migration từng bước sang react-query nếu nhu cầu pagination server hoặc background refetch tăng.
- Thêm instrumentation đo cache hit ratio (simple counter) để tinh chỉnh TTL.

### Error Handling (mới v0.3)
#### Phân loại lỗi
- Network unreachable / offline: phát hiện qua `navigator.onLine === false` hoặc lỗi fetch/axios `ECONNABORTED`, hiển thị banner Offline (`OfflineBanner`).
- API error (có response): đi qua interceptor -> `error.normalized` (status, message). Notification hiển thị dạng ngắn gọn.
- Unexpected (JS runtime): ErrorBoundary hiển thị fallback thân thiện + nút reload khu vực.

#### ErrorBoundary
- Bao ngoài `RouterProvider` để chặn crash layout.
- Dev mode hiển thị stack (ẩn production).
- Có nút "Thử tải lại khu vực" (reset state boundary) & "Tải lại trang" (full reload) để recovery nhanh.

### Cache Instrumentation (v0.3 → mở rộng v0.4)
`useApiCache` bổ sung counters nội bộ: `hits`, `staleHits`, `misses`, `forcedRefresh`, `errors`, `inflight`, `backgroundRefresh` (v0.7).
API:
```
import { getApiCacheStats, resetApiCacheStats, clearApiCache } from '.../hooks/useApiCache';
```
Dev panel `CacheStatsPanel` (chỉ mount khi development) để quan sát realtime & clear prefix.

#### Dev Panel
- Tự động cập nhật mỗi 2s (poll nhẹ).
- Có reset counters & clear theo prefix giúp đo vi mô từng domain.
- Chỉ nên commit code mount panel kèm điều kiện `process.env.NODE_ENV !== 'production'`.

#### Offline Lifecycle (v0.4)
- Hook `useOnlineStatus({ debounceMs=400 })` debounce sự kiện online/offline tránh nhấp nháy khi mạng chập chờn.
- `OfflineBanner` reset dismissed state khi trở lại online để nếu mất kết nối lần nữa vẫn hiển thị.
- Có thể dùng hook này ở component khác để disable nút hành động khi offline.

Use-cases metrics:
- Tinh chỉnh TTL: nếu `misses` cao so với `hits` -> TTL có thể ngắn quá.
- Nếu `staleHits` cao hơn `hits` nhiều -> cân nhắc background refetch.
- `errors` bất thường -> kiểm tra backend hoặc race conditions.

### Performance Baseline (v0.6)
Mục tiêu: Có số đo định lượng trước khi tối ưu (tránh tối ưu mù). Gồm hai phần: phân tích bundle và đo thời gian mount trang.

#### Phân tích bundle
- Script: `npm run analyze` (thiết lập biến môi trường `ANALYZE=1`).
- Kết quả: file `dist/bundle-report.html` (treemap) + sourcemaps bật.
- Cách đọc: Ô lớn nhất = gói/ chunk lớn nhất. Tập trung loại bỏ/ tách các dependency phụ không critical (vd: formatters lớn, thư viện date đa locale) trước.
- Nguyên tắc cải tiến:
  1. Trì hoãn (lazy import) các panel/dev-only (CacheStatsPanel) ở production nếu cần.
  2. Tránh import từ entry root của thư viện nếu có subpath nhẹ hơn (`lodash/*`, `date-fns/*`).
  3. Tránh double bundle do phiên bản trùng nhau (kiểm tra khi thêm lib mới).

#### Đo thời gian render route
Hook `useRoutePerf(name, onMeasure?)`:
```
useRoutePerf('OffersListPage');
```
Đo thời gian từ lúc component bắt đầu mount tới effect đầu tiên (gần tương đương First Meaningful Paint của trang nội bộ nếu skeleton tối giản).

Trả về qua callback (tùy chọn):
```
useRoutePerf('CampaignsDashboard', (m) => window.__perfMetrics?.push(m));
```
Metric: `{ name, duration, start, end }` (ms). Trong dev, log `[RoutePerf] name 12.3ms`.

Guideline đặt tên: Dạng PascalCase trùng tên file page chính (`OffersListPage`, `CampaignsDashboard`). Nếu page có biến thể lớn (ví dụ mode khác nhau) có thể thêm hậu tố `:Variant`.

Theo dõi thủ công: Mở DevTools Performance -> Timings sẽ thấy `measure` cùng tên nếu browser hỗ trợ `performance.measure`.

#### Ngưỡng tham khảo sơ bộ (chưa tối ưu)
- < 30ms: tốt (đơn giản / cache hit).
- 30–80ms: chấp nhận được.
- 80–150ms: xem xét tối ưu (memo hóa danh sách, giảm tính toán đồng bộ).
- > 150ms: ưu tiên kiểm tra (nhiều map lọc, JSON lớn đồng bộ, thiếu lazy import nặng).

#### Roadmap tối ưu tiếp theo (sau baseline)
1. Phân tách code-splitting cho các drawer/detail nặng nếu bundle chung quá lớn.
2. Memo hóa cột bảng nếu re-render gây tốn kém với dataset lớn (>1k rows).
3. Prefetch route ở idle tiếp tục (đã có); cân nhắc dynamic prefetch dựa vào tần suất người dùng.
4. Background refetch dữ liệu stale (stale-while-revalidate) nếu phát hiện tỷ lệ `staleHits` cao.

Không triển khai ngay (tránh premature optimization) – đợi đủ số đo lặp lại giữa các commit.

### Code Splitting Drawers & Dev Tools (v0.8)
Mục tiêu: Giảm initial bundle cho các route chính bằng cách tách các Drawer chi tiết ít dùng và panel dev.

#### Nguyên tắc
- Thành phần hiển thị theo sự kiện (mở Drawer) → lazy import.
- Giữ fetch logic ở page hoặc chuyển vào Drawer tùy mức chia sẻ (OfferDetailDrawer tự fetch; CampaignExtrasDrawer nhận props `extras`).
- Dev-only panel (CacheStatsPanel) chỉ load khi người dùng explicit toggle.

#### Pattern OfferDetailDrawer
```
const OfferDetailDrawerLazy = React.lazy(()=>import('../../components/OfferDetailDrawer.jsx'));
<React.Suspense fallback={null}>
  <OfferDetailDrawerLazy open={drawerOpen} onClose={...} offer={selectedOffer} />
</React.Suspense>
```
Drawer tự fetch extras khi `open && offer` –隔 logic không ảnh hưởng page list render.

#### Pattern CampaignExtrasDrawer
Page giữ fetch (cần notify / control) và truyền `extras, loading` xuống drawer lazy. Giảm coupling.

#### Dev Panel Toggle (định hướng)
Thay vì import thẳng `CacheStatsPanel`, dùng dynamic import khi người dùng bấm nút “Dev Tools” (tránh rò rỉ code panel vào bundle prod nếu tree-shake không đủ mạnh).

#### Khi không nên tách tiếp
- Component < 2–3KB gz và xuất hiện trên hầu hết các route → tách gây overhead request.
- Drawer mở gần như 100% use-case (thì nên giữ chung hoặc prefetch sớm).

#### Kiểm chứng
Chạy `npm run analyze` trước & sau để so sánh kích thước chunk chính (`index`/`vendor`). Kỳ vọng: giảm kích thước phần chứa logic chi tiết offer/campaign.

### PWA, Offline Queue, Dashboard, Wizard, Perf Visualization (v0.9)
Các cải tiến mục tiêu nâng trải nghiệm người dùng không chuyên + observability:

1. Dashboard tổng quan (`/dashboard` – route mặc định)
  - KPIs nhanh: số lượng offers, campaigns, templates, shortlinks.
  - Quick navigation buttons.
  - Caching TTL ngắn (20–30s) đảm bảo số liệu đủ tươi.
2. Glossary auto-highlight
  - `autoHighlight(text)` quét và wrap thuật ngữ (shortlink, template, merchant, campaign, commission, conversion...).
  - Giảm giải thích thủ công, giúp onboarding tự nhiên ngay trong nội dung.
3. Ingest Wizard (scaffold `/ingest/wizard`)
  - 3 bước: source → mapping → confirm (stub). Sẵn sàng mở rộng backend job ingest.
4. Metrics Perf Dashboard (`/metrics/perf`)
  - Lưu buffer route perf (hook `useRoutePerf` đẩy vào `window.__routePerfMetrics`).
  - Biểu đồ cột mini + p95/avg filter theo tên route.
5. Offline Action Queue
  - Hook `useOfflineQueue` lưu POST (có thể mở rộng cho PUT/DELETE) vào localStorage khi offline, tự flush khi online.
  - Tránh mất thao tác người dùng.
6. PWA cơ bản
  - `manifest.json` + `sw.js` cache app shell và fallback offline (trả về `index.html`).
  - Giúp load lại nhanh hơn, có thể mở rộng precache domain assets sau.
7. Accessibility baseline automated
  - `jest-axe` test smoke trang Dashboard (giảm nguy cơ regression a11y). Có thể mở rộng sang các page nhiều tương tác.
8. Perf route real-time visualization
  - Tối ưu quá trình cải tiến dựa trên dữ liệu thay vì cảm tính.
9. Confirm Action API
  - `useConfirmAction` standard hook → áp dụng dần cho các thao tác destructive để thống nhất UI/UX.

Hướng nâng cấp tiếp (v1+):
- Persist offline queue giữa nhiều tab (BroadcastChannel) & conflict resolution.
- Partial hydration hoặc streaming SSR (nếu cần scale mạnh SEO/perf).
- Graph phân bố Web Vitals nâng cao (stacked timeline) & correlating route perf.
- Progressive enhancement: hiển thị snapshot KPIs ngay từ SW cache trong lần mở lại.

Phiên bản tài liệu: v0.9.

### Changelog
| Phiên bản | Thay đổi chính |
|-----------|----------------|
| v0.9 | Dashboard, Glossary auto-highlight, Ingest Wizard scaffold, Perf Dashboard, Offline Queue, PWA manifest + SW, a11y test baseline, Confirm hook. |
| v0.8 | Tách lazy OfferDetailDrawer & CampaignExtrasDrawer, chuẩn bị toggle dynamic cho CacheStatsPanel, tài liệu Code Splitting. |
| v0.5 | Quốc tế hoá thông điệp hệ thống (ErrorBoundary, OfflineBanner, NotFound), thêm test i18n cơ bản, naming convention i18n. |
| v0.6 | Bundle analyzer (script analyze), hook `useRoutePerf` + instrumentation OffersListPage & CampaignsDashboard, tài liệu Performance Baseline. |
| v0.7 | Thêm tuỳ chọn `staleWhileRefetch` cho `useApiCache` + counter `backgroundRefresh`, test SWR, tài liệu cập nhật. |
| v0.4 | Dev panel mount condition, hook `useOnlineStatus` debounce, cải tiến OfflineBanner. |
| v0.3 | Cache instrumentation (stats API + panel), trang 404, mở rộng tài liệu error handling. |
| v0.2 | Thêm `useApiCache`, prefetch hover extras, tài liệu Caching & Prefetch, cập nhật pattern bảng. |
| v0.1 | Khung cơ bản: responsive DataTable, SkeletonSection, Notification dedupe, Onboarding panel, route preload. |

### i18n Naming Convention (v0.5)
- Tiền tố nhóm: `common_`, `error_boundary_`, `offline_`, `not_found_`, `ai_`, `logs_`, `excel_`, domain khác giữ nguyên (`offers_`, `campaigns_`).
- Dạng key: snake_case, ngắn gọn, phản ánh ngữ nghĩa (vd: `common_no_data`, `offline_message`).
- Tránh nhúng dấu câu không cần thiết vào key (message mới thêm biểu tượng nếu cần).
- Placeholder dùng `{name}` — giữ nguyên trong cả vi/en.
- Khi thêm key mới: thêm cả `vi` và `en`; nếu chưa có dịch, để tạm bản tiếng Anh ở en và bản Việt ở vi (không để trống để tránh fallback unpredictable).

### Test i18n
- Mỗi nhóm page chỉ cần 1 test smoke chuyển đổi locale (`i18n.basic.test.jsx`).
- Khi thêm component quan trọng mới có text người dùng thấy, cân nhắc thêm vào test nếu text ảnh hưởng logic (ví dụ: empty state hiển thị/ẩn dựa trên text).

Phiên bản tài liệu: v0.9 (early dev). Cập nhật khi thêm pattern mới.
