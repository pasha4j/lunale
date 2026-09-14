/* Service worker for the /homework/ app.
   Grades must be fresh, so pages are network-first with a cached fallback;
   icons and webfonts are cache-first. Bump CACHE to evict everything. */
const CACHE = 'lunale-homework-v2';
const SHELL = ['./', './manifest.webmanifest', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL))
      .catch(() => {})            // a cold cache must never block activation
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function fresh(req, key) {
  return fetch(req).then((res) => {
    if (res && res.ok) {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(key || req, copy));
    }
    return res;
  });
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // The page itself: always try the network, so a launch shows today's data.
  // Every ?student=… variant is the same document, so cache it under './'.
  if (req.mode === 'navigate') {
    e.respondWith(fresh(req, './').catch(() => caches.match('./')));
    return;
  }

  // Icons, manifest, and Google Fonts: cache-first, refreshed in the background.
  if (url.origin === location.origin ||
      url.hostname === 'fonts.googleapis.com' ||
      url.hostname === 'fonts.gstatic.com') {
    e.respondWith(
      caches.match(req).then((hit) => hit || fresh(req).catch(() => hit))
    );
  }
});
