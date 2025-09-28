// Lightweight process shim so code that references process.env won't throw in browser/runtime tests.
// Vite will statically replace import.meta.env.* so prefer that pattern; this shim just prevents defensive checks from failing.
if (typeof globalThis.process === 'undefined') {
  try {
    globalThis.process = { env: { NODE_ENV: import.meta.env.MODE || 'development' } };
  } catch {
    // noop
  }
}

export {}; // ensure module scope