(function() {
  'use strict';

  var DB_NAME = 'bm-marketing';
  var DB_VERSION = 1;
  var db = null;

  function openDB() {
    return new Promise(function(resolve, reject) {
      if (db) return resolve(db);
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function(e) {
        var d = e.target.result;
        if (!d.objectStoreNames.contains('sync_queue'))
          d.createObjectStore('sync_queue', { keyPath: 'id', autoIncrement: true });
        if (!d.objectStoreNames.contains('koleksi_cache'))
          d.createObjectStore('koleksi_cache', { keyPath: 'id' });
        if (!d.objectStoreNames.contains('dashboard_cache'))
          d.createObjectStore('dashboard_cache', { keyPath: 'key' });
        if (!d.objectStoreNames.contains('coa_cache'))
          d.createObjectStore('coa_cache', { keyPath: 'id' });
        if (!d.objectStoreNames.contains('donatur_cache'))
          d.createObjectStore('donatur_cache', { keyPath: 'id' });
        if (!d.objectStoreNames.contains('penerima_cache'))
          d.createObjectStore('penerima_cache', { keyPath: 'id' });
      };
      req.onsuccess = function(e) { db = e.target.result; resolve(db); };
      req.onerror = function() { reject(req.error); };
    });
  }

  // ── Generic store operations ──────────────────────────
  function putItem(storeName, item) {
    return openDB().then(function(d) {
      return new Promise(function(resolve, reject) {
        var tx = d.transaction(storeName, 'readwrite');
        tx.objectStore(storeName).put(item);
        tx.oncomplete = function() { resolve(); };
        tx.onerror = function() { reject(tx.error); };
      });
    });
  }

  function getItem(storeName, key) {
    return openDB().then(function(d) {
      return new Promise(function(resolve, reject) {
        var tx = d.transaction(storeName, 'readonly');
        var req = tx.objectStore(storeName).get(key);
        req.onsuccess = function() { resolve(req.result); };
        req.onerror = function() { reject(req.error); };
      });
    });
  }

  function getAllItems(storeName) {
    return openDB().then(function(d) {
      return new Promise(function(resolve, reject) {
        var tx = d.transaction(storeName, 'readonly');
        var req = tx.objectStore(storeName).getAll();
        req.onsuccess = function() { resolve(req.result); };
        req.onerror = function() { reject(req.error); };
      });
    });
  }

  function deleteItem(storeName, key) {
    return openDB().then(function(d) {
      return new Promise(function(resolve, reject) {
        var tx = d.transaction(storeName, 'readwrite');
        tx.objectStore(storeName).delete(key);
        tx.oncomplete = function() { resolve(); };
        tx.onerror = function() { reject(tx.error); };
      });
    });
  }

  function clearStore(storeName) {
    return openDB().then(function(d) {
      return new Promise(function(resolve, reject) {
        var tx = d.transaction(storeName, 'readwrite');
        tx.objectStore(storeName).clear();
        tx.oncomplete = function() { resolve(); };
        tx.onerror = function() { reject(tx.error); };
      });
    });
  }

  function putBulk(storeName, items) {
    return openDB().then(function(d) {
      return new Promise(function(resolve, reject) {
        var tx = d.transaction(storeName, 'readwrite');
        var store = tx.objectStore(storeName);
        store.clear();
        items.forEach(function(item) { store.put(item); });
        tx.oncomplete = function() { resolve(); };
        tx.onerror = function() { reject(tx.error); };
      });
    });
  }

  // ── Sync Queue ────────────────────────────────────────
  function addToSyncQueue(item) {
    item.timestamp = new Date().toISOString();
    item.status = 'pending';
    return putItem('sync_queue', item).then(function() {
      updateSyncBadge();
      if ('serviceWorker' in navigator && 'SyncManager' in window) {
        return navigator.serviceWorker.ready.then(function(reg) {
          return reg.sync.register('sync-queue');
        });
      }
    });
  }

  function getSyncQueue() {
    return getAllItems('sync_queue');
  }

  function removeSyncItem(id) {
    return deleteItem('sync_queue', id).then(function() {
      updateSyncBadge();
    });
  }

  function getSyncCount() {
    return openDB().then(function(d) {
      return new Promise(function(resolve, reject) {
        var tx = d.transaction('sync_queue', 'readonly');
        var req = tx.objectStore('sync_queue').count();
        req.onsuccess = function() { resolve(req.result); };
        req.onerror = function() { reject(req.error); };
      });
    });
  }

  // ── Sync badge UI ─────────────────────────────────────
  function updateSyncBadge() {
    getSyncCount().then(function(count) {
      var badges = document.querySelectorAll('.sync-badge');
      badges.forEach(function(badge) {
        if (count > 0) {
          badge.textContent = count;
          badge.classList.add('show');
        } else {
          badge.classList.remove('show');
        }
      });
    });
  }

  // ── Cache refresh helpers ─────────────────────────────
  function refreshDashboardCache() {
    return fetch('/api/marketing/dashboard', { credentials: 'same-origin' })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        data.key = 'current';
        return putItem('dashboard_cache', data);
      });
  }

  function refreshKoleksiCache(bulan) {
    var url = '/api/marketing/koleksi';
    if (bulan) url += '?bulan=' + bulan;
    return fetch(url, { credentials: 'same-origin' })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        return putBulk('koleksi_cache', data.koleksi);
      });
  }

  function refreshReferenceData() {
    return Promise.all([
      fetch('/api/marketing/coa', { credentials: 'same-origin' })
        .then(function(r) { return r.json(); })
        .then(function(data) { return putBulk('coa_cache', data.coa); }),
      fetch('/api/marketing/donatur', { credentials: 'same-origin' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          return Promise.all([
            putBulk('donatur_cache', data.donatur),
            putBulk('penerima_cache', data.penerima)
          ]);
        })
    ]);
  }

  // ── Flush sync queue (online-first) ───────────────────
  var flushInFlight = null;

  function flushSyncQueue() {
    // Cegah flush ganda paralel (event 'online' + 'load' + pesan SW bisa
    // datang bersamaan → item yang sama terkirim dua kali)
    if (flushInFlight) return flushInFlight;
    flushInFlight = doFlushSyncQueue().finally(function() { flushInFlight = null; });
    return flushInFlight;
  }

  function doFlushSyncQueue() {
    return getSyncQueue().then(function(items) {
      if (items.length === 0) return Promise.resolve({ synced: 0, errors: [] });

      var syncItems = items.map(function(item) {
        return { id: item.id, type: item.type, koleksi_id: item.koleksi_id, body: item.body };
      });

      return fetch('/api/marketing/sync', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: syncItems })
      })
      .then(function(r) {
        if (r.status === 401) {
          showToast('Sesi habis. Silakan login ulang.', 'warning');
          return { synced: 0, errors: ['unauthorized'] };
        }
        return r.json();
      })
      .then(function(result) {
        var removePromises = [];
        if (result.results) {
          result.results.forEach(function(r) {
            if (r.status === 'ok' || (r.response && r.response.status === 'conflict')) {
              removePromises.push(removeSyncItem(r.id));
            }
            if (r.response && r.response.status === 'conflict') {
              showToast(r.response.message, 'warning');
            }
          });
        }
        return Promise.all(removePromises).then(function() {
          if (result.synced > 0) {
            showToast(result.synced + ' item berhasil disinkronkan', 'success');
          }
          return result;
        });
      });
    });
  }

  // ── Toast notification ────────────────────────────────
  function showToast(message, type) {
    type = type || 'info';
    var colors = { success: '#1e8449', warning: '#f39c12', danger: '#e74c3c', info: '#2e86c1' };
    var toast = document.createElement('div');
    toast.style.cssText =
      'position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:9999;' +
      'background:' + (colors[type] || colors.info) + ';color:#fff;padding:10px 18px;' +
      'border-radius:10px;font-size:.85rem;font-weight:500;box-shadow:0 4px 12px rgba(0,0,0,.2);' +
      'max-width:90%;text-align:center;opacity:0;transition:opacity .3s';
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(function() { toast.style.opacity = '1'; });
    setTimeout(function() {
      toast.style.opacity = '0';
      setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
  }

  // ── Online/offline sync triggers ──────────────────────
  window.addEventListener('online', function() {
    console.log('[Offline] Back online — flushing sync queue');
    flushSyncQueue().then(function() {
      refreshDashboardCache();
      refreshKoleksiCache();
    });
  });

  // On page load: update badge + try flush if online
  window.addEventListener('load', function() {
    updateSyncBadge();
    if (navigator.onLine) {
      flushSyncQueue();
      refreshDashboardCache();
      refreshKoleksiCache();
      refreshReferenceData();
    }
  });

  // ── Expose API ────────────────────────────────────────
  window.OfflineStore = {
    addToSyncQueue: addToSyncQueue,
    getSyncQueue: getSyncQueue,
    getSyncCount: getSyncCount,
    flushSyncQueue: flushSyncQueue,
    updateSyncBadge: updateSyncBadge,
    refreshDashboardCache: refreshDashboardCache,
    refreshKoleksiCache: refreshKoleksiCache,
    refreshReferenceData: refreshReferenceData,
    getItem: getItem,
    getAllItems: getAllItems,
    putItem: putItem,
    putBulk: putBulk,
    getDashboard: function() { return getItem('dashboard_cache', 'current'); },
    getKoleksiList: function() { return getAllItems('koleksi_cache'); },
    getCOA: function() { return getAllItems('coa_cache'); },
    getDonatur: function() { return getAllItems('donatur_cache'); },
    getPenerima: function() { return getAllItems('penerima_cache'); },
    showToast: showToast
  };
})();
