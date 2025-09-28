// Global setup for vitest
import '@testing-library/jest-dom';

// Some tests refer to window or navigator assumptions
if (typeof window !== 'undefined') {
  // Ensure offline/online flags exist
  Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true });
  if (!window.matchMedia) {
    window.matchMedia = (query) => ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    });
  }
}

// Silence React Router warnings about missing "document" in some lazy tests
// (createBrowserRouter used in main.jsx for full app tests). Tests that need router should mock explicitly.

// If any component directly imports main.jsx (which builds a browser router), we can provide a guard

// You can extend further mocks here if needed later.

// --- Global lightweight mocks to reduce IO & speed tests ---
// Mock toàn bộ @mui/icons-material: mỗi icon -> component rỗng
vi.mock('@mui/icons-material', () => new Proxy({}, { get: () => () => null }));

// Mock axios & global fetch luôn để tránh XHR thật trong jsdom và giảm noise AggregateError
vi.mock('axios', () => {
  const makeStub = () => {
    const stub = {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      interceptors: {
        response: {
          use: vi.fn(),
          handlers: [],
        }
      },
      create: () => makeStub(),
    };
    return stub;
  };
  const root = makeStub();
  return { __esModule: true, default: root };
});
if (typeof globalThis.fetch === 'undefined') {
  globalThis.fetch = (...args) => Promise.resolve({ ok: true, json: async () => ({}), text: async () => '', status: 200, headers: new Map(), url: String(args[0]) });
} else {
  // wrap existing fetch to prevent external calls (naive: always resolve empty)
  globalThis.fetch = (...args) => Promise.resolve({ ok: true, json: async () => ({}), text: async () => '', status: 200, headers: new Map(), url: String(args[0]) });
}

// Stub XMLHttpRequest để tránh jsdom mở kết nối thật (gây AggregateError spam log)
class XHRStub {
  constructor() {
    this.readyState = 0;
    this.status = 200;
    this.responseText = '';
    this.onreadystatechange = null;
    this.onload = null;
    this.onerror = null;
    this._headers = {};
  }
  open(method, url) { this.method = method; this.url = url; this.readyState = 1; }
  setRequestHeader(k,v){ this._headers[k]=v; }
  send() {
    this.readyState = 4;
    if (typeof this.onreadystatechange === 'function') this.onreadystatechange();
    if (typeof this.onload === 'function') this.onload();
  }
  abort() {}
  addEventListener(type, cb){ if (type==='load') this.onload = cb; if (type==='error') this.onerror = cb; }
  removeEventListener(type){ if (type==='load') this.onload = null; if (type==='error') this.onerror = null; }
  get response(){ return this.responseText; }
}
globalThis.XMLHttpRequest = XHRStub;

// Guard cảnh báo test chậm (>1200ms). Không fail build, chỉ warn.
const SLOW_TEST_MS = parseInt(process.env.SLOW_TEST_MS || '1200', 10);
afterEach(async (ctx) => {
  const dur = ctx?.meta?.duration;
  if (typeof dur === 'number' && dur > SLOW_TEST_MS) {
  console.warn(`⚠️  [SLOW TEST] ${ctx.task.name} took ${dur}ms (> ${SLOW_TEST_MS}ms)`);
  }
});

// --- Global timer tracking để tránh treo process nếu còn handle ---
if (!globalThis.__TEST_TIMER_IDS__) {
  globalThis.__TEST_TIMER_IDS__ = { timeouts: new Set(), intervals: new Set() };
  const _setTimeout = globalThis.setTimeout;
  const _setInterval = globalThis.setInterval;
  const _clearTimeout = globalThis.clearTimeout;
  const _clearInterval = globalThis.clearInterval;
  globalThis.setTimeout = (...args) => {
    const id = _setTimeout(...args);
    globalThis.__TEST_TIMER_IDS__.timeouts.add(id);
    return id;
  };
  globalThis.setInterval = (...args) => {
    const id = _setInterval(...args);
    // Tránh giữ event loop sống sau khi test hoàn tất: unref nếu có.
    if (id && typeof id.unref === 'function') {
      id.unref();
    }
    globalThis.__TEST_TIMER_IDS__.intervals.add(id);
    return id;
  };
  globalThis.clearTimeout = (id) => { globalThis.__TEST_TIMER_IDS__.timeouts.delete(id); return _clearTimeout(id); };
  globalThis.clearInterval = (id) => { globalThis.__TEST_TIMER_IDS__.intervals.delete(id); return _clearInterval(id); };
  // Dọn timer sau mỗi test file để tránh tích luỹ
  afterEach(() => {
    for (const id of globalThis.__TEST_TIMER_IDS__.timeouts) _clearTimeout(id);
    for (const id of globalThis.__TEST_TIMER_IDS__.intervals) _clearInterval(id);
    globalThis.__TEST_TIMER_IDS__.timeouts.clear();
    globalThis.__TEST_TIMER_IDS__.intervals.clear();
  });
}

// Lightweight beforeExit diagnostics (không bật mặc định trừ khi TEST_DIAG=1)
if (process.env.TEST_DIAG === '1' && !globalThis.__TEST_BEFORE_EXIT__) {
  globalThis.__TEST_BEFORE_EXIT__ = true;
  process.on('beforeExit', () => {
    const handles = (process._getActiveHandles?.()||[]).map(h=>h?.constructor?.name||'Unknown');
    const reqs = (process._getActiveRequests?.()||[]).map(r=>r?.constructor?.name||'Unknown');
    console.log('[BEFORE_EXIT] handles=', handles, 'requests=', reqs, 'pendingTimeouts=', globalThis.__TEST_TIMER_IDS__?.timeouts.size);
  });
}

// --- Track window event listeners & auto cleanup (đặc biệt keydown) tránh giữ handle ---
if (typeof window !== 'undefined' && !window.__LISTENER_TRACKED__) {
  window.__LISTENER_TRACKED__ = true;
  const _add = window.addEventListener;
  const _remove = window.removeEventListener;
  window.__TEST_LISTENERS__ = [];
  window.addEventListener = function(type, listener, options){
    window.__TEST_LISTENERS__.push({ type, listener, options });
    return _add.call(this, type, listener, options);
  };
  window.removeEventListener = function(type, listener, options){
    window.__TEST_LISTENERS__ = window.__TEST_LISTENERS__.filter(l => !(l.type===type && l.listener===listener));
    return _remove.call(this, type, listener, options);
  };
  afterEach(() => {
    for (const { type, listener, options } of window.__TEST_LISTENERS__) {
      try { _remove.call(window, type, listener, options); } catch {}
    }
    window.__TEST_LISTENERS__ = [];
  });
}
