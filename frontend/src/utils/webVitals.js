// Lightweight Web Vitals collector. Uses dynamic import so tree-shaking + optional.
// Batching + persistence strategy
// - Collect metrics (LCP/CLS/INP) once per navigation
// - Store in in-memory array + localStorage fallback if offline
// - Flush on: idle (2s), visibilitychange(hidden), beforeunload, when batch >=5

let _buffer = [];
let _flushTimer = null;
const STORAGE_KEY = 'web_vitals_buffer_v1';
let _session = null;

function loadPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) _buffer.push(...arr);
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {}
}

function persistBuffer() {
  try { if (_buffer.length) localStorage.setItem(STORAGE_KEY, JSON.stringify(_buffer)); } catch {}
}

async function flushNow(submitFn) {
  if (!_buffer.length) return;
  const batch = _buffer.splice(0, _buffer.length);
  try {
    await submitFn({ metrics: batch, client_ts: Date.now() });
  } catch {
    // network fail -> re-persist
    _buffer.unshift(...batch);
    persistBuffer();
  }
}

export function initWebVitals(reportFn, submitFn) {
  if (typeof window === 'undefined') return;
  if (!_session) _session = Math.random().toString(36).slice(2, 10);
  loadPersisted();
  import('web-vitals').then(mod => {
    const { onLCP, onCLS, onINP } = mod;
    const wrap = (metric) => {
      try { reportFn(metric); } catch {}
      const payload = {
        name: metric.name,
        value: metric.value,
        rating: metric.rating,
        delta: metric.delta,
        metric_id: metric.id,
        navigation_type: (performance.getEntriesByType('navigation')[0]?.type) || undefined,
        url: location.href,
        referrer: document.referrer || undefined,
        session_id: _session,
        ts: Date.now(),
        extra: metric.attribution ? { attribution: metric.attribution } : undefined,
      };
      _buffer.push(payload);
      if (_buffer.length >= 5) scheduleFlush(submitFn, 200);
      else scheduleFlush(submitFn, 1500);
    };
    onLCP(wrap); onCLS(wrap); onINP(wrap);
  }).catch(()=>{});

  function scheduleFlush(submitFn, delay) {
    if (_flushTimer) clearTimeout(_flushTimer);
    _flushTimer = setTimeout(() => flushNow(submitFn), delay);
  }

  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      persistBuffer();
      flushNow(submitFn);
    }
  });
  window.addEventListener('beforeunload', () => {
    persistBuffer();
  });
}
