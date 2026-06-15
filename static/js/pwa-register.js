(function() {
  'use strict';

  // ── Service Worker Registration ──────────────────────
  if ('serviceWorker' in navigator && location.pathname.indexOf('/marketing') === 0) {
    window.addEventListener('load', function() {
      navigator.serviceWorker.register('/marketing/sw.js', { scope: '/marketing/' })
        .then(function(reg) {
          console.log('[PWA] SW registered, scope:', reg.scope);
          reg.addEventListener('updatefound', function() {
            var worker = reg.installing;
            worker.addEventListener('statechange', function() {
              if (worker.state === 'activated') {
                console.log('[PWA] New SW activated');
              }
            });
          });
        })
        .catch(function(err) {
          console.error('[PWA] SW registration failed:', err);
        });
    });
  }

  // ── Install Prompt ───────────────────────────────────
  var deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function(e) {
    e.preventDefault();
    deferredPrompt = e;
    var banner = document.getElementById('install-banner');
    if (banner) banner.classList.add('show');
  });

  window.addEventListener('appinstalled', function() {
    deferredPrompt = null;
    var banner = document.getElementById('install-banner');
    if (banner) banner.classList.remove('show');
    console.log('[PWA] App installed');
  });

  window.installApp = function() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(function(result) {
      console.log('[PWA] Install choice:', result.outcome);
      deferredPrompt = null;
      var banner = document.getElementById('install-banner');
      if (banner) banner.classList.remove('show');
    });
  };

  window.dismissInstall = function() {
    var banner = document.getElementById('install-banner');
    if (banner) banner.classList.remove('show');
  };

  // ── Online/Offline Detection ─────────────────────────
  function updateOnlineStatus() {
    document.body.classList.toggle('is-offline', !navigator.onLine);
  }
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);
  updateOnlineStatus();

  // ── Push Notification Subscription ─────────────────
  function subscribePush() {
    if (!('PushManager' in window) || !('serviceWorker' in navigator)) return;

    fetch('/api/push/vapid-key', { credentials: 'same-origin' })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.publicKey) return;
        return navigator.serviceWorker.ready.then(function(reg) {
          return reg.pushManager.getSubscription().then(function(existing) {
            if (existing) return existing;
            var key = urlBase64ToUint8Array(data.publicKey);
            return reg.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: key
            });
          });
        });
      })
      .then(function(sub) {
        if (!sub) return;
        return fetch('/api/push/subscribe', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subscription: sub.toJSON() })
        });
      })
      .catch(function(err) {
        console.log('[PWA] Push subscription skipped:', err.message || err);
      });
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(base64);
    var arr = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  // Auto-subscribe after page load (only on marketing routes)
  if (location.pathname.indexOf('/marketing') === 0) {
    window.addEventListener('load', function() {
      if (Notification.permission === 'granted') {
        subscribePush();
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(function(p) {
          if (p === 'granted') subscribePush();
        });
      }
    });
  }

  // ── Background Sync message handler ────────────────
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function(e) {
      if (e.data && e.data.type === 'flush-sync-queue' && window.OfflineStore) {
        window.OfflineStore.flushSyncQueue();
      }
    });
  }
})();
