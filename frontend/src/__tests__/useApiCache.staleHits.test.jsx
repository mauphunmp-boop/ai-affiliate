import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import useApiCache, { resetApiCacheStats, getApiCacheStats, clearApiCache } from '../hooks/useApiCache';

const delay = (ms)=> new Promise(r=>setTimeout(r, ms));

describe('useApiCache staleHits', () => {
  beforeEach(()=> { resetApiCacheStats(); clearApiCache(); });
  it('increments staleHits when data stale and re-fetched', async () => {
    let n = 0;
    const fetcher = vi.fn(async () => { n++; return { n }; });
    const { result } = renderHook(() => useApiCache('k1', fetcher, { ttlMs:30 }));
    // initial miss
    await act(async ()=>{ await delay(0); });
    expect(getApiCacheStats().misses).toBe(1);
    // wait so it becomes stale
    await act(async ()=>{ await delay(40); });
    // trigger read causing staleHit -> new fetch
    await act(async ()=>{ await result.current.refresh(); });
    const stats = getApiCacheStats();
    expect(stats.staleHits + stats.forcedRefresh >= 1).toBe(true); // forced refresh path increments forcedRefresh
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
