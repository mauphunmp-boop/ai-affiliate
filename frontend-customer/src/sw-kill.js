self.addEventListener('install', (e) => {
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map(k => caches.delete(k)));
      const regs = await self.registration.unregister();
    } catch(e) {}
    // Claim clients and force a reload to pick up fresh HTML without stale SW
    try {
      await self.clients.claim();
      const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      clients.forEach(c => { try { c.navigate(c.url); } catch(_) {} });
    } catch(e) {}
  })());
});
self.addEventListener('fetch', (e) => {
  // Do nothing; pass-through to network
});
