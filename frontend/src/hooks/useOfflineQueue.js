import React from 'react';

// Simple offline queue storing actions (method,url,payload,ts) in localStorage.
// On regain online, replays sequentially using provided executor (defaults to fetch/axios like signature).
export function useOfflineQueue(executor) {
  const exec = React.useMemo(()=> executor || (async (item) => {
    const res = await fetch(item.url, { method:item.method, headers:{ 'Content-Type':'application/json' }, body: item.payload? JSON.stringify(item.payload): undefined });
    if (!res.ok) throw new Error('HTTP '+res.status);
    return res;
  }), [executor]);
  const key = 'offlineQueue_v1';
  const [pending, setPending] = React.useState(()=> load());
  const [flushing, setFlushing] = React.useState(false);

  function load(){
    try { const raw = localStorage.getItem(key); if(!raw) return []; return JSON.parse(raw); } catch { return []; }
  }
  function save(list){ try { localStorage.setItem(key, JSON.stringify(list)); } catch { /* noop */ }
  }
  const enqueue = React.useCallback((method, url, payload) => {
    const item = { id:Date.now()+':'+Math.random().toString(36).slice(2), method, url, payload, ts: Date.now() };
    setPending(list => { const next = [...list, item]; save(next); return next; });
  }, []);

  const flush = React.useCallback(async () => {
    if (!navigator.onLine) return;
    if (!pending.length) return;
    setFlushing(true);
    let success = 0; const remain = [...pending];
    while (remain.length) {
      const item = remain[0];
      try { await exec(item); success++; remain.shift(); }
      catch { break; } // stop on first failure to avoid spin
    }
    setPending(remain); save(remain);
    setFlushing(false);
    return { success, remaining: remain.length };
  }, [pending, exec]);

  React.useEffect(() => {
    const online = () => { flush(); };
    window.addEventListener('online', online);
    return () => window.removeEventListener('online', online);
  }, [flush]);

  return { enqueue, flush, pending, flushing };
}
