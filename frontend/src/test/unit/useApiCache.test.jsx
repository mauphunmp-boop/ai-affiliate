import { renderHook, act, waitFor } from '@testing-library/react';
import useApiCache, { clearApiCache } from '../../hooks/useApiCache.js';

function wait(ms){ return new Promise(r=>setTimeout(r, ms)); }

describe('useApiCache basic TTL behavior', () => {
  afterEach(()=> clearApiCache());

  test('caches within TTL and refetches after invalidate', async () => {
    let calls = 0;
    const fetcher = () => { calls++; return Promise.resolve('data-'+calls); };
    const { result } = renderHook(() => useApiCache('k1', fetcher, { ttlMs: 1000 }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe('data-1');
    // second call within TTL should not increment
    await act(async () => { await result.current.refresh(); });
    expect(result.current.data).toBe('data-2'); // explicit refresh forces fetch
    // An implicit call without refresh should reuse
    const { result: result2 } = renderHook(() => useApiCache('k1', fetcher, { ttlMs: 1000 }));
    await waitFor(() => expect(result2.current.loading).toBe(false));
    expect(calls).toBe(2);
    expect(result2.current.data).toBe('data-2');
  });

  test('stale after TTL triggers new fetch', async () => {
    let calls = 0;
    const fetcher = () => { calls++; return Promise.resolve('v'+calls); };
    const { result } = renderHook(() => useApiCache('k2', fetcher, { ttlMs: 40 }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe('v1');
    await wait(60);
    await act(async () => { await result.current.refresh(); });
    expect(result.current.data).toBe('v2');
    expect(calls).toBe(2);
  });
});
