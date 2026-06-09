import sqlite3
import hashlib
import os

DB_PATH = os.path.join('data', 'keuangan.db')

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def migrate(conn):
    """Tambah kolom baru jika belum ada (safe migration)."""
    c = conn.cursor()

    trx = {r[1] for r in c.execute("PRAGMA table_info(transaksi)")}
    for col, defn in [
        ('coa_id',      'INTEGER REFERENCES chart_of_accounts(id)'),
        ('penerima_id', 'INTEGER REFERENCES penerima_manfaat(id)'),
        ('jenis_dana',  'TEXT'),
    ]:
        if col not in trx:
            c.execute(f"ALTER TABLE transaksi ADD COLUMN {col} {defn}")

    don = {r[1] for r in c.execute("PRAGMA table_info(donatur)")}
    for col, defn in [
        ('nik',          'TEXT'),
        ('aktif',        'INTEGER DEFAULT 1'),
        ('sumber_infaq', "TEXT DEFAULT 'tunai'"),
        ('area',         'TEXT'),
        ('lokasi_nama',  'TEXT'),
        ('lat',          'REAL'),
        ('lng',          'REAL'),
        ('aktif_infaq',  'INTEGER DEFAULT 1'),
    ]:
        if col not in don:
            c.execute(f"ALTER TABLE donatur ADD COLUMN {col} {defn}")

    conn.commit()

def init():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nama TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','marketing')),
            no_hp TEXT,
            aktif INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT UNIQUE NOT NULL,
            nama TEXT NOT NULL,
            kelompok TEXT NOT NULL,
            jenis_dana TEXT,
            parent_kode TEXT,
            jenis_transaksi TEXT,
            aktif INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS donatur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            no_hp TEXT,
            nik TEXT,
            alamat TEXT,
            jenis TEXT DEFAULT 'perorangan',
            sumber_infaq TEXT DEFAULT 'tunai',
            area TEXT,
            lokasi_nama TEXT,
            lat REAL,
            lng REAL,
            aktif INTEGER DEFAULT 1,
            aktif_infaq INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS koleksi_bulanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donatur_id INTEGER NOT NULL REFERENCES donatur(id),
            bulan TEXT NOT NULL,
            status TEXT DEFAULT 'terjadwal' CHECK(status IN ('terjadwal','tidak_ada','terkumpul')),
            marketing_id INTEGER REFERENCES users(id),
            tanggal_koleksi TEXT,
            jumlah REAL,
            jumlah_kunjungan INTEGER DEFAULT 0,
            kunjungan_terakhir TEXT,
            marketing_kunjungi_terakhir INTEGER REFERENCES users(id),
            keterangan TEXT,
            transaksi_id INTEGER REFERENCES transaksi(id),
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(donatur_id, bulan)
        );

        CREATE TABLE IF NOT EXISTS penerima_manfaat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            nik TEXT,
            no_hp TEXT,
            alamat TEXT,
            asnaf TEXT,
            keterangan TEXT,
            aktif INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            jenis TEXT NOT NULL CHECK(jenis IN ('masuk','keluar')),
            jenis_dana TEXT,
            coa_id INTEGER REFERENCES chart_of_accounts(id),
            donatur_id INTEGER REFERENCES donatur(id),
            penerima_id INTEGER REFERENCES penerima_manfaat(id),
            jumlah REAL NOT NULL,
            keterangan TEXT,
            user_id INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS kategori (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            jenis TEXT NOT NULL,
            keterangan TEXT
        );
    ''')

    migrate(conn)

    # ── Default users ─────────────────────────────────────────────────────────
    c.execute("INSERT OR IGNORE INTO users (username,password,nama,role) VALUES (?,?,?,?)",
              ('admin', hash_pw('admin123'), 'Administrator', 'admin'))
    c.execute("INSERT OR IGNORE INTO users (username,password,nama,role) VALUES (?,?,?,?)",
              ('marketing1', hash_pw('marketing123'), 'Marketing 1', 'marketing'))

    # ── Chart of Accounts — PSAK 109 + PSAK 112 ───────────────────────────────
    coa = [
        # ── ASET ──────────────────────────────────────────────────────────────
        ('1',     'ASET',                            'aset',              None,               None,    None),
        ('1.1',   'Aset Lancar',                     'aset',              None,               '1',     None),
        ('1.1.1', 'Kas Dana Zakat',                  'aset',              'zakat',            '1.1',   None),
        ('1.1.2', 'Kas Dana Infak/Sedekah',          'aset',              'infak_sedekah',    '1.1',   None),
        ('1.1.3', 'Kas Dana Amil',                   'aset',              'amil',             '1.1',   None),
        ('1.1.4', 'Kas Dana Wakaf',                  'aset',              'wakaf',            '1.1',   None),
        ('1.1.5', 'Bank Dana Zakat',                 'aset',              'zakat',            '1.1',   None),
        ('1.1.6', 'Bank Dana Infak/Sedekah',         'aset',              'infak_sedekah',    '1.1',   None),
        ('1.1.7', 'Bank Dana Amil',                  'aset',              'amil',             '1.1',   None),
        ('1.1.8', 'Bank Dana Wakaf',                 'aset',              'wakaf',            '1.1',   None),
        ('1.2',   'Aset Tidak Lancar',               'aset',              None,               '1',     None),
        ('1.2.1', 'Aset Kelolaan - Tanah Wakaf',     'aset',              'wakaf',            '1.2',   None),
        ('1.2.2', 'Aset Kelolaan - Bangunan Wakaf',  'aset',              'wakaf',            '1.2',   None),
        # ── LIABILITAS ────────────────────────────────────────────────────────
        ('2',     'LIABILITAS',                      'liabilitas',        None,               None,    None),
        ('2.1',   'Liabilitas Jangka Pendek',        'liabilitas',        None,               '2',     None),
        ('2.1.1', 'Titipan / Hutang Dana Zakat',     'liabilitas',        'zakat',            '2.1',   None),
        ('2.1.2', 'Titipan / Hutang Dana Infak',     'liabilitas',        'infak_sedekah',    '2.1',   None),
        # ── SALDO DANA ────────────────────────────────────────────────────────
        ('3',     'SALDO DANA',                      'dana',              None,               None,    None),
        ('3.1',   'Saldo Dana Zakat',                'dana',              'zakat',            '3',     None),
        ('3.2',   'Saldo Dana Infak/Sedekah',        'dana',              'infak_sedekah',    '3',     None),
        ('3.3',   'Saldo Dana Amil',                 'dana',              'amil',             '3',     None),
        ('3.4',   'Saldo Dana Wakaf',                'dana',              'wakaf',            '3',     None),
        # ── PENERIMAAN ────────────────────────────────────────────────────────
        ('4',     'PENERIMAAN',                      'penerimaan',        None,               None,    None),
        ('4.1',   'Penerimaan Dana Zakat',           'penerimaan',        'zakat',            '4',     None),
        ('4.1.1', 'Zakat Maal',                      'penerimaan',        'zakat',            '4.1',   'masuk'),
        ('4.1.2', 'Zakat Fitrah',                    'penerimaan',        'zakat',            '4.1',   'masuk'),
        ('4.1.3', 'Zakat Penghasilan/Profesi',       'penerimaan',        'zakat',            '4.1',   'masuk'),
        ('4.1.4', 'Zakat Perniagaan',                'penerimaan',        'zakat',            '4.1',   'masuk'),
        ('4.1.5', 'Zakat Pertanian',                 'penerimaan',        'zakat',            '4.1',   'masuk'),
        ('4.2',   'Penerimaan Dana Infak/Sedekah',   'penerimaan',        'infak_sedekah',    '4',     None),
        ('4.2.1', 'Infak Terikat',                   'penerimaan',        'infak_sedekah',    '4.2',   'masuk'),
        ('4.2.2', 'Infak Tidak Terikat',             'penerimaan',        'infak_sedekah',    '4.2',   'masuk'),
        ('4.2.3', 'Sedekah',                         'penerimaan',        'infak_sedekah',    '4.2',   'masuk'),
        ('4.3',   'Penerimaan Dana Amil',            'penerimaan',        'amil',             '4',     None),
        ('4.3.1', 'Bagian Amil dari Zakat',          'penerimaan',        'amil',             '4.3',   'masuk'),
        ('4.3.2', 'Bagian Amil dari Infak/Sedekah',  'penerimaan',        'amil',             '4.3',   'masuk'),
        ('4.3.3', 'Penerimaan Lain Dana Amil',       'penerimaan',        'amil',             '4.3',   'masuk'),
        ('4.4',   'Penerimaan Dana Wakaf',           'penerimaan',        'wakaf',            '4',     None),
        ('4.4.1', 'Wakaf Uang',                      'penerimaan',        'wakaf',            '4.4',   'masuk'),
        ('4.4.2', 'Wakaf Barang / Benda',            'penerimaan',        'wakaf',            '4.4',   'masuk'),
        ('4.4.3', 'Hasil Pengelolaan Wakaf',         'penerimaan',        'wakaf',            '4.4',   'masuk'),
        # ── PENYALURAN & BEBAN ────────────────────────────────────────────────
        ('5',     'PENYALURAN & BEBAN',              'penyaluran_beban',  None,               None,    None),
        ('5.1',   'Penyaluran Dana Zakat',           'penyaluran_beban',  'zakat',            '5',     None),
        ('5.1.1', 'Fakir',                           'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.1.2', 'Miskin',                          'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.1.3', 'Amil',                            'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.1.4', 'Muallaf',                         'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.1.5', 'Riqab (Memerdekakan Hamba)',      'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.1.6', 'Gharim (Orang Berutang)',         'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.1.7', 'Fisabilillah',                    'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.1.8', 'Ibnu Sabil (Musafir)',            'penyaluran_beban',  'zakat',            '5.1',   'keluar'),
        ('5.2',   'Penyaluran Dana Infak/Sedekah',   'penyaluran_beban',  'infak_sedekah',    '5',     None),
        ('5.2.1', 'Program Pendidikan',              'penyaluran_beban',  'infak_sedekah',    '5.2',   'keluar'),
        ('5.2.2', 'Program Kesehatan',               'penyaluran_beban',  'infak_sedekah',    '5.2',   'keluar'),
        ('5.2.3', 'Program Ekonomi/Pemberdayaan',    'penyaluran_beban',  'infak_sedekah',    '5.2',   'keluar'),
        ('5.2.4', 'Program Sosial/Kemanusiaan',      'penyaluran_beban',  'infak_sedekah',    '5.2',   'keluar'),
        ('5.2.5', 'Bantuan Bencana',                 'penyaluran_beban',  'infak_sedekah',    '5.2',   'keluar'),
        ('5.3',   'Beban Dana Amil',                 'penyaluran_beban',  'amil',             '5',     None),
        ('5.3.1', 'Gaji / Honor Amil',               'penyaluran_beban',  'amil',             '5.3',   'keluar'),
        ('5.3.2', 'Biaya Operasional Kantor',        'penyaluran_beban',  'amil',             '5.3',   'keluar'),
        ('5.3.3', 'Biaya Sosialisasi & Promosi',     'penyaluran_beban',  'amil',             '5.3',   'keluar'),
        ('5.3.4', 'Biaya Administrasi',              'penyaluran_beban',  'amil',             '5.3',   'keluar'),
        ('5.4',   'Penyaluran Dana Wakaf',           'penyaluran_beban',  'wakaf',            '5',     None),
        ('5.4.1', 'Pengembangan Wakaf Produktif',    'penyaluran_beban',  'wakaf',            '5.4',   'keluar'),
        ('5.4.2', 'Pemeliharaan Aset Wakaf',         'penyaluran_beban',  'wakaf',            '5.4',   'keluar'),
        ('5.4.3', 'Penyaluran Hasil Wakaf',          'penyaluran_beban',  'wakaf',            '5.4',   'keluar'),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) VALUES (?,?,?,?,?,?)",
        coa
    )

    # ── Produk Fundrising & Pentasharufan ─────────────────────────────────────
    from add_produk_coa import ENTRIES as produk_entries
    c.executemany(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) VALUES (?,?,?,?,?,?)",
        produk_entries
    )

    conn.commit()
    conn.close()
    print("Database berhasil diinisialisasi.")
    print("Login admin    : admin / admin123")
    print("Login marketing: marketing1 / marketing123")

if __name__ == '__main__':
    init()
