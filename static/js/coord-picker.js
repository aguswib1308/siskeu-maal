/* Pemilih koordinat via peta (Leaflet) + GPS -- dipakai di form Donatur
   (admin & marketing). Perlu Leaflet CSS+JS sudah dimuat di halaman. */
const coordPickers = {};
const PETA_DEFAULT = [-7.812, 110.923]; // Wonogiri

function initCoordPicker(mapId, latId, lngId) {
  const el = document.getElementById(mapId);
  if (!el || coordPickers[mapId]) return coordPickers[mapId];
  const latInput = document.getElementById(latId);
  const lngInput = document.getElementById(lngId);
  const hasCoord = latInput.value && lngInput.value;
  const start = hasCoord ? [parseFloat(latInput.value), parseFloat(lngInput.value)] : PETA_DEFAULT;
  const map = L.map(mapId).setView(start, hasCoord ? 16 : 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  const marker = L.marker(start, { draggable: true }).addTo(map);
  function setCoord(lat, lng) {
    latInput.value = lat.toFixed(6);
    lngInput.value = lng.toFixed(6);
  }
  marker.on('dragend', () => { const p = marker.getLatLng(); setCoord(p.lat, p.lng); });
  map.on('click', (e) => { marker.setLatLng(e.latlng); setCoord(e.latlng.lat, e.latlng.lng); });
  const picker = { map, marker, setCoord };
  coordPickers[mapId] = picker;
  setTimeout(() => map.invalidateSize(), 150);
  return picker;
}

function destroyCoordPicker(mapId) {
  if (coordPickers[mapId]) {
    coordPickers[mapId].map.remove();
    delete coordPickers[mapId];
  }
}

function useMyLocation(btn, mapId) {
  const picker = coordPickers[mapId];
  if (!picker) return;
  if (!navigator.geolocation) { alert('Perangkat/browser ini tidak mendukung GPS.'); return; }
  const oldHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Mencari lokasi...';
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const { latitude, longitude } = pos.coords;
      picker.marker.setLatLng([latitude, longitude]);
      picker.map.setView([latitude, longitude], 17);
      picker.setCoord(latitude, longitude);
      btn.disabled = false; btn.innerHTML = oldHtml;
    },
    (err) => {
      alert('Gagal mengambil lokasi: ' + err.message + '\nPastikan GPS & izin lokasi browser aktif.');
      btn.disabled = false; btn.innerHTML = oldHtml;
    },
    { enableHighAccuracy: true, timeout: 15000 }
  );
}
