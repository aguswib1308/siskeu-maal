/* ── Theme toggle (light / dark) ──────────────────────────
   Preferensi tersimpan di localStorage. Default mengikuti
   preferensi sistem. Pemasangan awal atribut data-bs-theme
   dilakukan oleh skrip inline di <head> agar tidak berkedip. */

function currentTheme() {
  return document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
}

function applyThemeIcon(theme) {
  document.querySelectorAll('[data-theme-icon]').forEach(function (el) {
    el.className = (theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars');
  });
  document.querySelectorAll('[data-theme-label]').forEach(function (el) {
    el.textContent = (theme === 'dark' ? 'Mode terang' : 'Mode gelap');
  });
}

function toggleTheme() {
  var next = currentTheme() === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-bs-theme', next);
  try { localStorage.setItem('theme', next); } catch (e) {}
  applyThemeIcon(next);
}

document.addEventListener('DOMContentLoaded', function () {
  applyThemeIcon(currentTheme());
});

// Ikuti perubahan preferensi sistem selama pengguna belum memilih manual
try {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    if (localStorage.getItem('theme')) return;
    var t = e.matches ? 'dark' : 'light';
    document.documentElement.setAttribute('data-bs-theme', t);
    applyThemeIcon(t);
  });
} catch (e) {}
