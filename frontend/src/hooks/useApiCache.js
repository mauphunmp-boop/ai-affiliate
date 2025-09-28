import { useEffect, useRef, useState, useCallback } from 'react';

// In-memory cache: key -> { data, error, ts, promise, refreshing }
const __apiCache = new Map();

// Instrumentation counters
const __apiCacheStats = {
  hits: 0,          // served from cache (fresh)
  staleHits: 0,     // had data but stale; still triggered fetch
  misses: 0,        // no data, need fetch
  forcedRefresh: 0, // explicit refresh() or invalidate()
  errors: 0,
  inflight: 0,      // current number of active promises
  backgroundRefresh: 0 // số lần chạy refetch nền khi staleWhileRefetch
};

/**
 * useApiCache
 * @param {string} key unique cache key (should include params)
 * @param {() => Promise<any>} fetcher async function returning data (res.data ideally)
 * @param {object} opts { ttlMs=60000, enabled=true, refreshDeps=[], immediate=true, staleWhileRefetch=false }
 * Nếu staleWhileRefetch=true: Khi dữ liệu stale nhưng vẫn còn -> trả ngay data & chạy fetch nền (loading=false nhưng có field refreshing=true trong return).
 * Returns { data, error, loading, stale, refresh, invalidate, refreshing }
 */
export default function useApiCache(key, fetcher, opts={}) {
  const { ttlMs=60000, enabled=true, refreshDeps=[], immediate=true, staleWhileRefetch=false } = opts;
  const [, force] = useState(0);
  const mountedRef = useRef(true);
  useEffect(()=>{ return ()=>{ mountedRef.current = false; }; }, []);

  const entry = __apiCache.get(key) || { data:undefined, error:null, ts:0, promise:null, refreshing:false };
  const stale = Date.now() - entry.ts > ttlMs;

  // Nếu sẽ chạy background refresh (data stale + có data + chưa có promise) ta set cờ refreshing sớm để consumer thấy ngay.
  if (enabled && staleWhileRefetch && stale && entry.data !== undefined && !entry.promise && !entry.refreshing) {
    entry.refreshing = true;
    entry._refreshingFlagged = true;
    __apiCache.set(key, entry);
    // Trigger re-render ngay để consumer thấy refreshing=true ở cùng frame rerender
    // (Không tạo vòng lặp vì _refreshingFlagged ngăn đặt lại)
    force(v=>v+1);
  }

  const runFetch = useCallback((forceRefresh=false) => {
    if (!enabled) return;
    let e = __apiCache.get(key) || { data:undefined, error:null, ts:0, promise:null, refreshing:false };
    const isExpired = Date.now() - e.ts > ttlMs;
    if (!forceRefresh && e.promise) return e.promise; // reuse inflight
    if (!forceRefresh && !isExpired && e.data !== undefined) {
      return Promise.resolve(e.data); // fresh reuse; hit counted in separate effect
    }
    // Stale path: only count staleHits when we will serve stale data immediately (staleWhileRefetch true)
    const willServeStale = !forceRefresh && isExpired && e.data !== undefined;
    if (forceRefresh) {
      __apiCacheStats.forcedRefresh++;
    } else if (e.data === undefined) {
      __apiCacheStats.misses++;
    } else if (willServeStale && staleWhileRefetch) {
      __apiCacheStats.staleHits++;
    }
    const isBackground = willServeStale && staleWhileRefetch;
    if (isBackground) { __apiCacheStats.backgroundRefresh++; }
  e.refreshing = isBackground; // flag riêng cho background
    const p = Promise.resolve().then(()=> fetcher())
  .then(data => { if (!mountedRef.current) return data; e = { ...e, data, error:null, ts: Date.now(), promise:null, refreshing:false, _firstResolved:true, _skipNextHitCount: forceRefresh ? true : false }; __apiCache.set(key,e); __apiCacheStats.inflight--; force(v=>v+1); return data; })
      .catch(err => { if (!mountedRef.current) { __apiCacheStats.inflight--; throw err; } e = { ...e, error:err, promise:null, ts: Date.now(), refreshing:false }; __apiCache.set(key,e); __apiCacheStats.errors++; __apiCacheStats.inflight--; force(v=>v+1); throw err; });
    e.promise = p; __apiCache.set(key,e); if (!isBackground) { __apiCacheStats.inflight++; } else { __apiCacheStats.inflight++; }
    force(v=>v+1); return p;
  }, [key, fetcher, ttlMs, enabled, staleWhileRefetch]);

  // Auto run on mount if immediate
  useEffect(()=>{
    if (import.meta.env?.TEST) {
      // Trong môi trường TEST, tránh auto fetch để test có thể chủ động mock / giảm side-effects
      if (immediate && enabled) {
        // vẫn chạy fetch sync đầu tiên để có data, nhưng không schedule thêm
        runFetch();
      }
    } else if (immediate && enabled) {
      runFetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled, immediate, ttlMs, ...refreshDeps]);


  // Background refresh đồng bộ: khi staleWhileRefetch & stale có data -> trigger một lần (promise guard ngăn lặp)
  if (enabled && staleWhileRefetch && stale && entry.data !== undefined && !entry.promise) {
    runFetch(false);
  }

  // Synchronous fresh-hit counting: if cache entry is fresh & settled and we have seen it before (re-render) count once per timestamp
  if (enabled) {
    const e2 = __apiCache.get(key);
    if (e2 && e2.data !== undefined && !e2.promise) {
      const fresh = Date.now() - e2.ts <= ttlMs;
      if (fresh) {
        if (e2._firstResolved) {
          // mark consumed, no hit yet
          delete e2._firstResolved;
        } else if (e2._skipNextHitCount) {
          delete e2._skipNextHitCount;
        } else if (!e2._countedTs) {
          __apiCacheStats.hits++;
          e2._countedTs = e2.ts;
        } else if (e2._countedTs !== e2.ts) {
          __apiCacheStats.hits++;
          e2._countedTs = e2.ts;
        }
      }
    }
  }

  const refresh = useCallback(()=> runFetch(true), [runFetch]);
  const invalidate = useCallback(()=> { const e = __apiCache.get(key); if (e) { e.ts = 0; } runFetch(true); }, [key, runFetch]);

  const current = __apiCache.get(key) || entry;
  const loading = !!current.promise && !current.refreshing; // background refresh không set loading=true
  const refreshing = !!current.promise && current.refreshing;

  return { data: current.data, error: current.error, loading, stale, refresh, invalidate, refreshing, _cache: __apiCache };
}

export function clearApiCache(prefix) {
  if (!prefix) { __apiCache.clear(); return; }
  [...__apiCache.keys()].forEach(k => { if (k.startsWith(prefix)) __apiCache.delete(k); });
}

export function getApiCacheStats() { return { ...__apiCacheStats }; }
export function resetApiCacheStats() { Object.keys(__apiCacheStats).forEach(k => __apiCacheStats[k] = 0); }
