// Early polyfills & noise filters – chạy trước mọi setup khác
// Mục tiêu: tránh bất kỳ import nào kích hoạt XHR thật trước khi chúng ta stub.

// Stub XMLHttpRequest càng sớm càng tốt để ngăn jsdom tạo kết nối gây AggregateError log.
class EarlyXHRStub {
  constructor() {
    this.readyState = 0; this.status = 200; this.responseText = ''; this.response = ''; this.onreadystatechange = null; this.onload = null; this.onerror = null;
  }
  open(m,u){ this.method=m; this.url=u; this.readyState = 1; }
  setRequestHeader(){}
  send(){ this.readyState = 4; if (typeof this.onreadystatechange==='function') this.onreadystatechange(); if (typeof this.onload==='function') this.onload(); }
  abort(){}
  addEventListener(t,cb){ if(t==='load') this.onload=cb; if(t==='error') this.onerror=cb; }
  removeEventListener(t){ if(t==='load') this.onload=null; if(t==='error') this.onerror=null; }
}
if (typeof globalThis.XMLHttpRequest === 'undefined') {
  globalThis.XMLHttpRequest = EarlyXHRStub;
}

// Giữ reference gốc để không nuốt lỗi assertion thật.
const origConsoleError = console.error;
const NOISE_PATTERNS = [
  /AggregateError/i,
  /XMLHttpRequest/i,
  /network.*failed/i,
  /Kaboom/, // lỗi cố ý trong ErrorBoundary test
  /The above error occurred in the <Boom> component/i,
];
console.error = (...args) => {
  if (process.env.NO_SUPPRESS_CONSOLE === '1') {
    return origConsoleError(...args);
  }
  const msg = args[0] && String(args[0]);
  if (msg && NOISE_PATTERNS.some(r=>r.test(msg))) {
    return; // suppress noise
  }
  origConsoleError(...args);
};

// Flag môi trường test để code có thể gate side-effects cực sớm.
if (!import.meta.env.TEST) {
  // Vite sẽ inject, nhưng đảm bảo biến tồn tại để main.jsx có thể đọc.
  import.meta.env.TEST = true; // safe in Vitest environment
}

// --- DIAG instrumentation (kích hoạt khi đặt env VITEST_DIAG=1) ---
// Chỉ bật khi đặt TEST_DIAG=1 để tránh ảnh hưởng exit code mặc định.
if (process.env.TEST_DIAG === '1') {
  const log = (...a) => console.log('[DIAG]', ...a);
  // --- Timer tracer: ghi lại stack khi tạo timeout/interval để tìm nguồn leak ---
  if (!globalThis.__TIMER_TRACER__) {
    globalThis.__TIMER_TRACER__ = { timeouts:new Map(), intervals:new Map() };
    const _st = globalThis.setTimeout;
    const _si = globalThis.setInterval;
    const _ct = globalThis.clearTimeout;
    const _ci = globalThis.clearInterval;
    const capture = () => new Error().stack?.split('\n').slice(2,9).join('\n');
    globalThis.setTimeout = function(fn, delay, ...rest){
      // Ghi lại stack tại thời điểm tạo timeout
      const stack = capture();
      let wrapped = fn;
      if (typeof fn === 'function') {
        wrapped = (...a) => {
          try { return fn(...a); }
          finally { globalThis.__TIMER_TRACER__.timeouts.delete(id); }
        };
      }
      let id = _st(wrapped, delay, ...rest);
      globalThis.__TIMER_TRACER__.timeouts.set(id, stack);
      return id;
    };
    globalThis.setInterval = function(fn, delay, ...rest){
      const stack = capture();
      const id = _si(fn, delay, ...rest);
      globalThis.__TIMER_TRACER__.intervals.set(id, stack);
      return id;
    };
  globalThis.clearTimeout = function(id){ if(id!=null) globalThis.__TIMER_TRACER__.timeouts.delete(id); return _ct(id); };
    globalThis.clearInterval = function(id){ globalThis.__TIMER_TRACER__.intervals.delete(id); return _ci(id); };
  }
  process.on('unhandledRejection', r => {
    console.error('[UNHANDLED_REJECTION]', r);
  });
  process.on('uncaughtException', e => {
    console.error('[UNCAUGHT_EXCEPTION]', e);
  });
  const dump = () => {
    try {
      const handles = (process._getActiveHandles?.() || []).map(h => h && h.constructor ? h.constructor.name : 'Unknown');
      const reqs = (process._getActiveRequests?.() || []).map(r => r && r.constructor ? r.constructor.name : 'Unknown');
      log('Active Handles', handles);
      log('Active Requests', reqs);
      // Xuất timer tracer (chỉ hiển thị nếu còn >0)
      const leakingTimeouts = Array.from(globalThis.__TIMER_TRACER__.timeouts.values());
      const leakingIntervals = Array.from(globalThis.__TIMER_TRACER__.intervals.values());
      if (leakingTimeouts.length || leakingIntervals.length) {
        console.log('[DIAG_TIMERS] timeouts=', leakingTimeouts.length, 'intervals=', leakingIntervals.length);
        if (leakingTimeouts.length) console.log('[DIAG_TIMERS] sample timeout stack:\n', leakingTimeouts[0]);
        if (leakingIntervals.length) console.log('[DIAG_TIMERS] sample interval stack:\n', leakingIntervals[0]);
      }
    } catch (e) {
      log('dump error', e);
    }
  };
  // Luôn dùng cơ chế timeout lặp unref để tránh giữ event loop mở.
  let __diagTimeoutId;
  const loop = () => {
    dump();
    if (!globalThis.__STOP_DIAG__) {
      __diagTimeoutId = setTimeout(loop, 5000);
      __diagTimeoutId.unref?.();
    }
  };
  __diagTimeoutId = setTimeout(loop, 2000);
  __diagTimeoutId.unref?.();
  const stopDiag = (phase) => {
    globalThis.__STOP_DIAG__ = true;
    if (__diagTimeoutId) { clearTimeout(__diagTimeoutId); }
    log(`diag stopped (${phase})`);
  };
  process.on('beforeExit', () => { log('beforeExit dump'); dump(); stopDiag('beforeExit'); });
  process.on('exit', (code) => { stopDiag('exit:'+code); });
}
