import { renderHook, act } from '@testing-library/react';
import React from 'react';
import useApiCache, { resetApiCacheStats, getApiCacheStats, clearApiCache } from '../hooks/useApiCache.js';

// Helper sleep
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

describe('useApiCache staleWhileRefetch', () => {
  beforeEach(() => { clearApiCache(); resetApiCacheStats(); });

  it('trả về data stale ngay lập tức và chạy background refresh', async () => {
    let fetchCount = 0;
    const fetcher = async () => { fetchCount++; return { value: fetchCount }; };

    // Bước 1: mount đầu lấy dữ liệu
    const { result, rerender } = renderHook(({ k, ttl }) => useApiCache(k, fetcher, { ttlMs: ttl, staleWhileRefetch: true }), { initialProps:{ k:'k1', ttl:30 } });
    // Chờ fetch đầu
    while (result.current.loading) { await act(()=>sleep(5)); }
    expect(result.current.data.value).toBe(1);

    // Đợi TTL hết hạn
    await act(()=>sleep(40));

    // Bước 2: Rerender (simulate consumer đọc lại) -> nên trả data cũ ngay, không loading, nhưng bắt đầu background
    rerender({ k:'k1', ttl:30 });
    const before = fetchCount;
    expect(result.current.data.value).toBe(1); // stale served
    expect(result.current.loading).toBe(false); // không loading foreground
    // Có promise background -> refreshing true
    expect(result.current.refreshing).toBe(true);

    // Chờ background hoàn tất
    await act(()=>sleep(10));
    // Có thể cần loop nhẹ nếu promise chưa xong
    let guard = 0;
    while (result.current.refreshing && guard < 50) { guard++; await act(()=>sleep(10)); }

    expect(fetchCount).toBeGreaterThan(before);
    expect(result.current.data.value).toBe(2);

    const stats = getApiCacheStats();
    expect(stats.backgroundRefresh).toBe(1);
    expect(stats.staleHits).toBe(1); // lần thứ hai cũ + stale
  });
});
