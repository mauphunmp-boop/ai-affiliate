import { useLayoutEffect, useRef } from 'react';

/**
 * useRoutePerf
 * Đo thời gian từ lúc component mount tới paint/effect đầu tiên.
 * @param {string} name Tên logical của route/page
 * @param {(metric:{name:string,duration:number,start:number,end:number})=>void} [onMeasure]
 */
export function useRoutePerf(name, onMeasure) {
  const startRef = useRef(typeof performance !== 'undefined' ? performance.now() : Date.now());

  const processMetric = () => {
    const end = typeof performance !== 'undefined' ? performance.now() : Date.now();
    const start = startRef.current;
    const duration = end - start;
    const metric = { name, duration, start, end };
    try {
      performance.mark?.(`${name}-end`);
      performance.measure?.(name, { start: start, end: end });
  } catch { /* noop */ }
    try {
      if (typeof window !== 'undefined') {
        if (!window.__routePerfMetrics) window.__routePerfMetrics = [];
        window.__routePerfMetrics.push({ ...metric, ts: Date.now() });
        if (window.__routePerfMetrics.length > 200) window.__routePerfMetrics.splice(0, window.__routePerfMetrics.length - 200);
        window.dispatchEvent(new CustomEvent('route-perf-update'));
      }
  } catch { /* noop */ }
    if (typeof onMeasure === 'function') {
      onMeasure(metric);
    }
    if (process.env.NODE_ENV !== 'production') {
      console.debug('[RoutePerf]', name, duration.toFixed(1)+'ms');
    }
  };

  // Chỉ đo một lần khi mount: cố ý không thêm processMetric vào deps để tránh đo lại khi prop name thay đổi nhẹ.
  // An toàn vì processMetric không nắm giữ state biến động ngoài startRef/name.
  // processMetric cố ý không đưa vào deps để chỉ đo 1 lần khi mount.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { processMetric(); }, []);
}
