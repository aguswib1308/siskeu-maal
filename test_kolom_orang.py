"""Uji kolom "Donatur" & "Penerima Manfaat" pada Laporan Sumber & Penggunaan Dana
dan Laporan Arus Kas.

Yang dijaga:
  1. n_donatur = jumlah ORANG (donatur yang berdonasi 2x dihitung sekali),
     transaksi tanpa donatur (anonim/kotak infaq) tetap dihitung 1 per transaksi.
  2. Kedua halaman laporan tetap render (arity kolom tabel benar) dan memuat
     judul kolom baru + angkanya.

Jalankan:  python test_kolom_orang.py
Memakai database sementara, tidak menyentuh data/keuangan.db.
"""
import os
import sqlite3
import tempfile

_tmpdir = tempfile.mkdtemp(prefix='maal_kolom_')
TEST_DB = os.path.join(_tmpdir, 'test_kolom.db')

import init_db                                          # noqa: E402
init_db.DB_PATH = TEST_DB
init_db.init()

import app as maal                                      # noqa: E402
maal.DB_PATH = TEST_DB
maal.app.config.update(TESTING=True, SECRET_KEY='uji')

BULAN = '2026-07'
conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
coa_masuk = conn.execute(
    "SELECT id FROM chart_of_accounts WHERE jenis_transaksi='masuk' AND kelompok='penerimaan' "
    "AND jenis_dana IS NOT NULL AND aktif=1 ORDER BY kode LIMIT 1").fetchone()[0]
coa_keluar = conn.execute(
    "SELECT id FROM chart_of_accounts WHERE jenis_transaksi='keluar' "
    "AND jenis_dana IS NOT NULL AND aktif=1 ORDER BY kode LIMIT 1").fetchone()[0]
jd_masuk = conn.execute("SELECT jenis_dana FROM chart_of_accounts WHERE id=?",
                        (coa_masuk,)).fetchone()[0]
jd_keluar = conn.execute("SELECT jenis_dana FROM chart_of_accounts WHERE id=?",
                         (coa_keluar,)).fetchone()[0]
conn.executemany("INSERT INTO donatur (id,nama,aktif) VALUES (?,?,1)",
                 [(1, 'Donatur Satu'), (2, 'Donatur Dua')])
# Donatur 1 menyetor DUA kali di bulan sama -> tetap 1 orang.
# Dua transaksi tanpa donatur_id (kotak infaq) -> 2 "penyetor" terpisah.
conn.executemany(
    "INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,donatur_id,jumlah) VALUES (?,'masuk',?,?,?,?)",
    [(BULAN + '-02', jd_masuk, coa_masuk, 1, 100_000),
     (BULAN + '-09', jd_masuk, coa_masuk, 1, 150_000),
     (BULAN + '-10', jd_masuk, coa_masuk, 2, 200_000),
     (BULAN + '-11', jd_masuk, coa_masuk, None, 50_000),
     (BULAN + '-12', jd_masuk, coa_masuk, None, 25_000)])
conn.execute(
    "INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,jumlah,nama_kegiatan,jumlah_mustahik) "
    "VALUES (?,'keluar',?,?,300000,'Santunan Uji',12)", (BULAN + '-20', jd_keluar, coa_keluar))
# Penyaluran tanpa jumlah mustahik -> sel kolom harus berisi em dash, bukan
# teks mentah "&mdash;" (Jinja meng-escape entitas HTML di dalam ekspresi).
coa_keluar2 = conn.execute(
    "SELECT id FROM chart_of_accounts WHERE jenis_transaksi='keluar' AND jenis_dana=? "
    "AND id<>? AND aktif=1 ORDER BY kode LIMIT 1", (jd_keluar, coa_keluar)).fetchone()[0]
conn.execute(
    "INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,jumlah,nama_kegiatan) "
    "VALUES (?,'keluar',?,?,100000,'Tanpa Mustahik')", (BULAN + '-21', jd_keluar, coa_keluar2))
conn.commit()

# ── 1. Hitungan orang ────────────────────────────────────────────────────────
data = maal._dana_summary(conn, BULAN)
d = data[jd_masuk]
assert d['total_donatur'] == 4, d['total_donatur']        # 2 orang + 2 transaksi anonim
assert d['total_masuk'] == 525_000, d['total_masuk']
assert data[jd_keluar]['total_mustahik'] == 12, data[jd_keluar]['total_mustahik']
conn.close()

# ── 2. Kedua halaman laporan render dengan kolom baru ───────────────────────
c = maal.app.test_client()
with c.session_transaction() as s:
    s['user_id'], s['role'], s['nama'] = 1, 'admin', 'Administrator'

for url in ('/admin/laporan/dana?bulan=' + BULAN,
            '/admin/laporan/arus-kas?bulan=' + BULAN):
    r = c.get(url)
    assert r.status_code == 200, (url, r.status_code)
    html = r.get_data(as_text=True)
    assert 'Donatur' in html, url
    assert 'Penerima Manfaat' in html, url
    assert '>4<' in html or '>4 ' in html, url            # jumlah donatur tampil
    assert '>12<' in html or '>12 ' in html, url          # jumlah penerima manfaat tampil
    # Sel kosong = em dash sungguhan, bukan "&mdash;" yang ter-escape jadi teks
    assert '—' in html, url
    assert 'mdash' not in html, url

# LSPD: penerimaan & penyaluran harus BERDAMPINGAN -- dua kolom grid per panel
# dana, bukan satu tabel bertumpuk. Juga pastikan tidak ada </div> nyasar yang
# menutup pembungkus .p-4 lebih awal.
html = c.get('/admin/laporan/dana?bulan=' + BULAN).get_data(as_text=True)
n_panel = html.count('report-panel d-')
assert n_panel >= 1, n_panel
n_kolom = html.count('class="col-lg-6 report-duo-col"')
assert n_kolom == 2 * n_panel, (n_kolom, n_panel)

# Baris "Jumlah Penerimaan" & "Jumlah Penyaluran" sejajar: syaratnya kedua
# tabel dalam satu panel punya jumlah baris tbody yang sama (sisi lebih pendek
# diganjal baris kosong). Data uji sengaja timpang: 1 akun masuk, 2 akun keluar.
import re                                                  # noqa: E402
tbody = [b.count('<tr') for b in re.findall(r'<tbody>(.*?)</tbody>', html, re.S)]
assert len(tbody) == 2 * n_panel, tbody
for kiri, kanan in zip(tbody[0::2], tbody[1::2]):
    assert kiri == kanan, (kiri, kanan)
assert html.count('report-filler') >= 1, html.count('report-filler')
assert html.count('<div') == html.count('</div>'), (html.count('<div'), html.count('</div>'))

print('SEMUA UJI LOLOS')
