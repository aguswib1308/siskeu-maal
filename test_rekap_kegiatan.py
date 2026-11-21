"""Uji mandiri untuk dua perubahan:
  1. Rekap Donasi per Donatur — pencarian nama + pilihan urutan.
  2. Info Kegiatan Penyaluran — backfill transaksi keluar yang sudah tercatat.

Jalankan:  python test_rekap_kegiatan.py
Memakai database sementara, tidak menyentuh data/keuangan.db.
"""
import os
import sqlite3
import tempfile

# DB sementara harus sudah siap SEBELUM app.py diimpor (DB_PATH dibaca saat impor).
_tmpdir = tempfile.mkdtemp(prefix='maal_test_')
TEST_DB = os.path.join(_tmpdir, 'test_rekap.db')
os.environ['MAAL_DB_PATH'] = TEST_DB


def siapkan_db(path):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE donatur (
            id INTEGER PRIMARY KEY, nama TEXT, sumber_infaq TEXT, aktif INTEGER DEFAULT 1);
        CREATE TABLE chart_of_accounts (
            id INTEGER PRIMARY KEY, kode TEXT, nama TEXT, jenis_dana TEXT);
        CREATE TABLE transaksi (
            id INTEGER PRIMARY KEY, tanggal TEXT, jenis TEXT, jenis_dana TEXT,
            coa_id INTEGER, donatur_id INTEGER, penerima_id INTEGER, jumlah INTEGER,
            keterangan TEXT, user_id INTEGER, created_at TEXT, jurnal_id INTEGER,
            client_uuid TEXT, nama_kegiatan TEXT, lokasi TEXT, jumlah_mustahik INTEGER);
    """)
    conn.executemany(
        "INSERT INTO donatur (id, nama, sumber_infaq, aktif) VALUES (?,?,?,?)", [
            (1, 'Ahmad Dahlan',  'kotak_infaq', 1),
            (2, 'Budi Santoso',  'tunai',       1),
            (3, 'Citra Dewi',    None,          0),   # sumber_infaq NULL + nonaktif
            (4, 'Diskon 100%',   'tunai',       1),   # nama ber-wildcard LIKE
        ])
    conn.execute("INSERT INTO chart_of_accounts (id,kode,nama,jenis_dana) VALUES (1,'4.1','Infaq','infak_tidak_terikat')")
    conn.execute("INSERT INTO chart_of_accounts (id,kode,nama,jenis_dana) VALUES (2,'5.1','Santunan','infak_terikat')")

    # Ahmad: 3 bulan, total 600rb. Budi: 1 bulan, 1jt. Citra: 2 bulan, 300rb. Diskon: 1 bulan, 50rb.
    masuk = [
        ('2026-01-10', 1, 200_000), ('2026-02-10', 1, 200_000), ('2026-03-10', 1, 200_000),
        ('2026-01-15', 2, 1_000_000),
        ('2026-01-20', 3, 150_000), ('2026-05-20', 3, 150_000),
        ('2026-04-01', 4, 50_000),
        ('2025-01-10', 1, 999_000),   # tahun lain — harus terabaikan
    ]
    conn.executemany(
        "INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,donatur_id,jumlah) "
        "VALUES (?,'masuk','infak_tidak_terikat',1,?,?)", masuk)

    # Dua transaksi penyaluran: satu sudah ada info kegiatan, satu belum.
    conn.execute(
        "INSERT INTO transaksi (id,tanggal,jenis,jenis_dana,coa_id,jumlah,keterangan,"
        "nama_kegiatan,lokasi,jumlah_mustahik) VALUES "
        "(500,'2026-03-05','keluar','infak_terikat',2,750000,'Santunan Dhuafa (30 mustahik)',"
        "'Santunan Ramadhan','Masjid Al-Ikhlas',30)")
    conn.execute(
        "INSERT INTO transaksi (id,tanggal,jenis,jenis_dana,coa_id,jumlah,keterangan) VALUES "
        "(501,'2026-03-06','keluar','infak_terikat',2,500000,'Santunan Dhuafa (20 mustahik)')")
    conn.commit()
    conn.close()


siapkan_db(TEST_DB)

import app as maal                                     # noqa: E402
maal.DB_PATH = TEST_DB                                 # app.py membaca DB_PATH saat get_db()
maal.app.config.update(TESTING=True, SECRET_KEY='uji')


def db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn


def nama_urut(sort, q=None):
    conn = db()
    tabel, _, _ = maal._rekap_donasi_donatur(conn, '2026', q, sort)
    conn.close()
    return [e['nama'] for e in tabel]


def klien_admin():
    c = maal.app.test_client()
    with c.session_transaction() as s:
        s['user_id'], s['role'] = 1, 'admin'
    return c


# ── 1. Rekap donasi: urutan ──────────────────────────────────────────────────
assert nama_urut('total') == ['Budi Santoso', 'Ahmad Dahlan', 'Citra Dewi', 'Diskon 100%'], \
    nama_urut('total')
assert nama_urut('total_asc') == ['Diskon 100%', 'Citra Dewi', 'Ahmad Dahlan', 'Budi Santoso'], \
    nama_urut('total_asc')
assert nama_urut('nama') == ['Ahmad Dahlan', 'Budi Santoso', 'Citra Dewi', 'Diskon 100%'], \
    nama_urut('nama')
assert nama_urut('nama_desc') == ['Diskon 100%', 'Citra Dewi', 'Budi Santoso', 'Ahmad Dahlan'], \
    nama_urut('nama_desc')
# Ahmad 3 bulan > Citra 2 bulan > Budi & Diskon 1 bulan (tie dipecah total terbesar)
assert nama_urut('bulan_aktif') == ['Ahmad Dahlan', 'Citra Dewi', 'Budi Santoso', 'Diskon 100%'], \
    nama_urut('bulan_aktif')
# Rata-rata: Budi 1jt, Ahmad 200rb, Citra 150rb, Diskon 50rb
assert nama_urut('rata2') == ['Budi Santoso', 'Ahmad Dahlan', 'Citra Dewi', 'Diskon 100%'], \
    nama_urut('rata2')
# sort tak dikenal jatuh ke default, bukan error
assert nama_urut('ngawur') == nama_urut('total')

# ── 2. Rekap donasi: pencarian ───────────────────────────────────────────────
assert nama_urut('total', 'budi') == ['Budi Santoso']           # tidak peduli huruf besar/kecil
assert nama_urut('total', 'SANTOSO') == ['Budi Santoso']        # cocok di tengah nama
assert nama_urut('total', 'xyz') == []
# Wildcard LIKE yang diketik user dicari apa adanya, bukan jadi "cocok semua"
assert nama_urut('total', '%') == ['Diskon 100%'], nama_urut('total', '%')
assert nama_urut('total', '_') == [], nama_urut('total', '_')

# Total ikut tersaring supaya baris & footer konsisten
conn = db()
tabel, per_bulan, grand = maal._rekap_donasi_donatur(conn, '2026', 'budi', 'total')
conn.close()
assert grand == 1_000_000, grand
assert per_bulan['01'] == 1_000_000 and per_bulan['02'] == 0, dict(per_bulan)

# Tanpa filter: seluruh penerimaan 2026 (bukan 2025)
conn = db()
_, _, grand_semua = maal._rekap_donasi_donatur(conn, '2026')
conn.close()
assert grand_semua == 600_000 + 1_000_000 + 300_000 + 50_000, grand_semua

# ── 3. Info kegiatan: backfill transaksi yang sudah tercatat ─────────────────
c = klien_admin()

# Transaksi 501 belum ada info kegiatan -> tidak muncul di laporan kegiatan
conn = db()
assert conn.execute("SELECT nama_kegiatan FROM transaksi WHERE id=501").fetchone()[0] is None
conn.close()

r = c.post('/admin/transaksi/501/mustahik', data={
    'nama_kegiatan': 'Santunan Yatim', 'lokasi': 'Balai Desa Sendang', 'jumlah_mustahik': '20'})
assert r.status_code == 302, r.status_code
conn = db()
row = conn.execute("SELECT nama_kegiatan,lokasi,jumlah_mustahik FROM transaksi WHERE id=501").fetchone()
conn.close()
assert tuple(row) == ('Santunan Yatim', 'Balai Desa Sendang', 20), tuple(row)

# Form ringkas "jumlah mustahik" saja TIDAK boleh menghapus nama kegiatan & lokasi
c.post('/admin/transaksi/500/mustahik', data={'jumlah_mustahik': '35'})
conn = db()
row = conn.execute("SELECT nama_kegiatan,lokasi,jumlah_mustahik FROM transaksi WHERE id=500").fetchone()
conn.close()
assert tuple(row) == ('Santunan Ramadhan', 'Masjid Al-Ikhlas', 35), tuple(row)

# Mengosongkan nama kegiatan dengan sengaja -> jadi NULL (keluar dari laporan)
c.post('/admin/transaksi/500/mustahik', data={'nama_kegiatan': '  ', 'lokasi': ''})
conn = db()
row = conn.execute("SELECT nama_kegiatan,lokasi,jumlah_mustahik FROM transaksi WHERE id=500").fetchone()
conn.close()
assert tuple(row) == (None, None, 35), tuple(row)

# Jumlah mustahik bukan angka -> ditolak, data lama tidak berubah
c.post('/admin/transaksi/501/mustahik', data={'jumlah_mustahik': 'abc'})
conn = db()
assert conn.execute("SELECT jumlah_mustahik FROM transaksi WHERE id=501").fetchone()[0] == 20
conn.close()

# Transaksi masuk tidak boleh disentuh endpoint ini
id_masuk = None
conn = db()
id_masuk = conn.execute("SELECT id FROM transaksi WHERE jenis='masuk' LIMIT 1").fetchone()[0]
conn.close()
c.post(f'/admin/transaksi/{id_masuk}/mustahik', data={'nama_kegiatan': 'Seharusnya gagal'})
conn = db()
assert conn.execute("SELECT nama_kegiatan FROM transaksi WHERE id=?", (id_masuk,)).fetchone()[0] is None
conn.close()

# Tanpa login tidak boleh mengubah apa pun
anon = maal.app.test_client()
r = anon.post('/admin/transaksi/501/mustahik', data={'nama_kegiatan': 'Tanpa izin'})
assert r.status_code in (301, 302), r.status_code
conn = db()
assert conn.execute("SELECT nama_kegiatan FROM transaksi WHERE id=501").fetchone()[0] == 'Santunan Yatim'
conn.close()

# ── 4. Laporan kegiatan penyaluran memang menyaring nama_kegiatan ────────────
conn = db()
baris = conn.execute("""
    SELECT t.id FROM transaksi t JOIN chart_of_accounts c ON t.coa_id=c.id
    WHERE t.jenis='keluar' AND t.nama_kegiatan IS NOT NULL
      AND strftime('%Y-%m', t.tanggal)='2026-03'
""").fetchall()
conn.close()
assert [r[0] for r in baris] == [501], [r[0] for r in baris]

print('SEMUA UJI LOLOS')
