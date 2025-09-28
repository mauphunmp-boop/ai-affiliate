import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Lưu ý: Trước đây ta có cấu hình test trùng lặp giữa vite.config.js và vitest.config.js.
// Vitest sẽ ưu tiên vitest.config.js nên các setupFiles bổ sung (setupPolyfills, setupTests)
// không được nạp -> thiếu wrapper dọn timer & có thể để hở handle khiến tiến trình treo sau khi pass.
// Đã hợp nhất toàn bộ setupFiles vào đây để đảm bảo thứ tự: polyfills sớm -> tracking/Mocks -> tiện ích render.
// Có thể đơn giản hoá bằng cách xoá block test trong vite.config.js; giữ ở đó cũng không hại
// (nhưng vitest sẽ dùng file này). Khi nâng cấp vitest v3 chỉ cần cập nhật coverage plugin.

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // Thứ tự quan trọng: polyfills (suppress noise / diag) -> tracking timers & global mocks -> helpers render.
    setupFiles: [
      './src/test/setupPolyfills.js',
      './src/test/setupTests.js',
      './src/test/setup.jsx'
    ],
    globals: true,
    // Giới hạn thread để tránh lỗi file descriptor trên Windows & giúp test ổn định.
    maxThreads: 4,
    minThreads: 1,
    isolate: true,
    // Bật coverage để lấy baseline. Thresholds sẽ thêm ở bước sau (todo riêng) để tránh fail sớm.
    coverage: {
      provider: 'v8',
  reporter: ['text','lcov','json-summary'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/test/**','src/**/*.d.ts'],
      // Chưa đặt thresholds ở baseline; sẽ cấu hình trong bước thiết lập ngưỡng.
      reportsDirectory: './coverage'
    }
  }
});
