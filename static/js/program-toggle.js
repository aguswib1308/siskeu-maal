// Tampilkan/sembunyikan dropdown Program sesuai Kategori (zakat/infaq_terikat/wakaf)
// dipakai formulir Tambah & Edit Donatur (marketing) -- konsisten dgn admin/master/donatur.html
function toggleProgram(prefix) {
  var sel = document.getElementById(prefix + 'Sumber');
  if (!sel) return;
  var sumber = sel.value;
  var wrap = document.getElementById(prefix + 'ProgramWrap');
  if (!wrap) return;
  var show = ['zakat', 'infaq_terikat', 'wakaf'].includes(sumber);
  wrap.style.display = show ? '' : 'none';
  var progSel = wrap.querySelector('select');
  if (progSel) {
    var map = {zakat: 'opt-zakat', infaq_terikat: 'opt-infaq_terikat', wakaf: 'opt-wakaf'};
    progSel.querySelectorAll('optgroup').forEach(function(g) {
      g.style.display = g.classList.contains(map[sumber]) ? '' : 'none';
    });
    if (!show) progSel.value = '';
  }
}
