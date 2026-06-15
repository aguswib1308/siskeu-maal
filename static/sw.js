var CACHE_NAME = 'bm-shell-v2';
var SHELL_ASSETS = [
  '/static/css/marketing.css',
  '/static/js/pwa-register.js',
  '/static/js/offline-store.js',
  '/static/icons/icon-192x192.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// ── Install: cache shell assets ─────────────────────────
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(SHELL_ASSETS);
    })
  );
  self.skipWaiting();
});

// ── Activate: clean old caches ──────────────────────────
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// ── Fetch: strategy per route ───────────────────────────
self.addEventListener('fetch', function(e) {
  var url = e.request.url;
  var path = new URL(url).pathname;

  // Never cache auth pages
  if (path === '/' || path === '/logout') return;

  // Cache-first: shell assets + CDN
  var isShellAsset = SHELL_ASSETS.some(function(asset) {
    return url.indexOf(asset) !== -1;
  });
  if (isShellAsset || path.indexOf('/static/') === 0) {
    e.respondWith(
      caches.match(e.request).then(function(cached) {
        if (cached) return cached;
        return fetch(e.request).then(function(resp) {
          if (resp.ok) {
            var clone = resp.clone();
            caches.open(CACHE_NAME).then(function(cache) { cache.put(e.request, clone); });
          }
          return resp;
        });
      })
    );
    return;
  }

  // Network-first: marketing HTML pages
  if (path.indexOf('/marketing') === 0 && e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).then(function(resp) {
        if (resp.ok) {
          var clone = resp.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(e.request, clone); });
        }
        return resp;
      }).catch(function() {
        return caches.match(e.request).then(function(cached) {
          return cached || caches.match('/marketing');
        });
      })
    );
    return;
  }

  // Network-first: API GET — cache response for offline
  if (path.indexOf('/api/marketing/') === 0 && e.request.method === 'GET') {
    e.respondWith(
      fetch(e.request).then(function(resp) {
        if (resp.ok) {
          var clone = resp.clone();
          caches.open(CACHE_NAME).then(function(cache) { cache.put(e.request, clone); });
        }
        return resp;
      }).catch(function() {
        return caches.match(e.request);
      })
    );
    return;
  }
});

// ── Background Sync: flush offline queue ────────────────
self.addEventListener('sync', function(e) {
  if (e.tag === 'sync-queue') {
    e.waitUntil(
      self.clients.matchAll().then(function(clients) {
        if (clients.length > 0) {
          clients[0].postMessage({ type: 'flush-sync-queue' });
        }
      })
    );
  }
});

// ── Push Notification ───────────────────────────────────
self.addEventListener('push', function(e) {
  var data = { title: 'Baitul Maal', body: 'Ada notifikasi baru', url: '/marketing' };
  try { data = Object.assign(data, e.data.json()); } catch (err) {}
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/static/icons/icon-192x192.png',
      badge: '/static/icons/icon-192x192.png',
      data: { url: data.url || '/marketing' },
      vibrate: [200, 100, 200]
    })
  );
});

self.addEventListener('notificationclick', function(e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || '/marketing';
  e.waitUntil(
    self.clients.matchAll({ type: 'window' }).then(function(clients) {
      for (var i = 0; i < clients.length; i++) {
        if (clients[i].url.indexOf('/marketing') !== -1 && 'focus' in clients[i]) {
          clients[i].navigate(url);
          return clients[i].focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
