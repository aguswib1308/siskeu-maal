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
        ('jurnal_id',   'INTEGER REFERENCES jurnal(id)'),
        ('client_uuid', 'TEXT'),
    ]:
        if col not in trx:
            c.execute(f"ALTER TABLE transaksi ADD COLUMN {col} {defn}")

    # Idempotensi anti double-submit: client_uuid unik (NULL boleh banyak)
    jr = {r[1] for r in c.execute("PRAGMA table_info(jurnal)")}
    if jr and 'client_uuid' not in jr:
        c.execute("ALTER TABLE jurnal ADD COLUMN client_uuid TEXT")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_transaksi_client_uuid "
              "ON transaksi(client_uuid) WHERE client_uuid IS NOT NULL")
    if jr:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jurnal_client_uuid "
                  "ON jurnal(client_uuid) WHERE client_uuid IS NOT NULL")

    # DB lama dibuat sebelum COA punya kolom hierarki/jenis → tambah bila belum ada
    coa_cols = {r[1] for r in c.execute("PRAGMA table_info(chart_of_accounts)")}
    for col, defn in [
        ('jenis_dana',      'TEXT'),
        ('parent_kode',     'TEXT'),
        ('jenis_transaksi', 'TEXT'),
        ('aktif',           'INTEGER DEFAULT 1'),
    ]:
        if col not in coa_cols:
            c.execute(f"ALTER TABLE chart_of_accounts ADD COLUMN {col} {defn}")

    usr = {r[1] for r in c.execute("PRAGMA table_info(users)")}
    for col, defn in [
        ('no_hp', 'TEXT'),
    ]:
        if col not in usr:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")

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
        ('program_id',   'INTEGER REFERENCES chart_of_accounts(id)'),
        ('desa',         'TEXT'),
        ('kecamatan',    'TEXT'),
    ]:
        if col not in don:
            c.execute(f"ALTER TABLE donatur ADD COLUMN {col} {defn}")

    # GPS check-in columns on koleksi_bulanan
    kb = {r[1] for r in c.execute("PRAGMA table_info(koleksi_bulanan)")}
    for col, defn in [
        ('lat_kunjungan', 'REAL'),
        ('lng_kunjungan', 'REAL'),
    ]:
        if col not in kb:
            c.execute(f"ALTER TABLE koleksi_bulanan ADD COLUMN {col} {defn}")

    # Push notification subscriptions
    c.execute('''CREATE TABLE IF NOT EXISTS push_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        subscription_json TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(user_id, subscription_json)
    )''')

    # Target bulanan marketing
    c.execute('''CREATE TABLE IF NOT EXISTS target_bulanan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bulan TEXT NOT NULL,
        user_id INTEGER REFERENCES users(id),
        jenis TEXT NOT NULL CHECK(jenis IN ('fundraising','pentasharufan')),
        target_nominal INTEGER NOT NULL DEFAULT 0,
        target_kegiatan INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(bulan, user_id, jenis)
    )''')

    # Saldo awal manual per jenis dana (saldo sebelum transaksi pertama di sistem)
    c.execute('''CREATE TABLE IF NOT EXISTS saldo_awal (
        jenis_dana TEXT PRIMARY KEY,
        jumlah REAL NOT NULL DEFAULT 0,
        keterangan TEXT,
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

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

    c.execute('''CREATE TABLE IF NOT EXISTS instansi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL DEFAULT 'BAITUL MAAL BMT',
        nama_lembaga TEXT DEFAULT '',
        alamat TEXT DEFAULT '',
        telepon TEXT DEFAULT '',
        email TEXT DEFAULT '',
        website TEXT DEFAULT '',
        ketua TEXT DEFAULT '',
        bendahara TEXT DEFAULT '',
        sekretaris TEXT DEFAULT '',
        no_izin TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    c.execute("INSERT OR IGNORE INTO instansi (id, nama) VALUES (1, 'BAITUL MAAL BMT')")

    c.execute('''CREATE TABLE IF NOT EXISTS jurnal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal TEXT NOT NULL,
        no_bukti TEXT,
        keterangan TEXT,
        debit_coa_id INTEGER REFERENCES chart_of_accounts(id),
        kredit_coa_id INTEGER REFERENCES chart_of_accounts(id),
        jumlah REAL NOT NULL,
        user_id INTEGER REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS area (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT UNIQUE NOT NULL,
        aktif INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    AREA_SEED = ['Mundu','Banjardowo','Ngerco','Barengan','Giriwono','Wonokarto',
                 'Krisak','Kedungringin','Kajen','Donoharjo','Gerdu','Bauresan',
                 'Cubluk','Pasar','Pokoh','Bulusulur','Klemut','Sendangsari',
                 'Timang','Manjung','Sonoharjo','Kedungsono','Nambangan',
                 'Keblokan','Jomboran','Sumberjo','Jurug','Brumbung']
    c.executemany("INSERT OR IGNORE INTO area (nama) VALUES (?)",
                  [(a,) for a in AREA_SEED])

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

    # Backfill utk DB lama: baris COA yang sudah ada sebelum kolom
    # parent_kode/jenis_transaksi ditambah masih NULL → isi dari seed
    # (COALESCE = tidak menimpa nilai yang sudah ada)
    c.executemany(
        "UPDATE chart_of_accounts SET parent_kode=COALESCE(parent_kode,?), "
        "jenis_transaksi=COALESCE(jenis_transaksi,?), "
        "jenis_dana=COALESCE(jenis_dana,?) WHERE kode=?",
        [(pk, jt, jd, kode) for (kode, _, _, jd, pk, jt) in coa + list(produk_entries)]
    )

    # ── Migrasi: pisah Infak Terikat vs Tidak Terikat (dulu satu 'infak_sedekah') ──
    # 4.2.1[.xx] = Infak Terikat; sisanya (4.2.2[.xx], 4.2.3 Sedekah, semua 5.2.x
    # penyaluran) dianggap Tidak Terikat karena belum ada pembeda di data lama.
    c.execute("""UPDATE chart_of_accounts SET jenis_dana='infak_terikat'
                 WHERE jenis_dana='infak_sedekah' AND (kode='4.2.1' OR kode LIKE '4.2.1.%')""")
    c.execute("""UPDATE chart_of_accounts SET jenis_dana='infak_tidak_terikat'
                 WHERE jenis_dana='infak_sedekah' AND kode != '4.2'""")
    c.execute("""UPDATE chart_of_accounts SET jenis_dana=NULL
                 WHERE kode='4.2' AND jenis_dana='infak_sedekah'""")
    c.execute("""UPDATE chart_of_accounts SET nama='Penyaluran Dana Infak/Sedekah Tidak Terikat'
                 WHERE kode='5.2'""")

    # Akun penyaluran baru utk Infak Terikat, paralel dgn 5.2 (Tidak Terikat)
    infak_terikat_penyaluran = [
        ('5.5',   'Penyaluran Dana Infak Terikat',
            'penyaluran_beban', 'infak_terikat', '5',   None),
        ('5.5.1', 'Program Pendidikan (Terikat)',
            'penyaluran_beban', 'infak_terikat', '5.5', 'keluar'),
        ('5.5.2', 'Program Kesehatan (Terikat)',
            'penyaluran_beban', 'infak_terikat', '5.5', 'keluar'),
        ('5.5.3', 'Program Ekonomi/Pemberdayaan (Terikat)',
            'penyaluran_beban', 'infak_terikat', '5.5', 'keluar'),
        ('5.5.4', 'Program Sosial/Kemanusiaan (Terikat)',
            'penyaluran_beban', 'infak_terikat', '5.5', 'keluar'),
        ('5.5.5', 'Bantuan Bencana (Terikat)',
            'penyaluran_beban', 'infak_terikat', '5.5', 'keluar'),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) VALUES (?,?,?,?,?,?)",
        infak_terikat_penyaluran
    )

    # transaksi.jenis_dana adalah salinan (snapshot) dari coa.jenis_dana saat dicatat —
    # sinkronkan ulang transaksi lama yang masih berlabel 'infak_sedekah' dari akun COA-nya
    c.execute("""
        UPDATE transaksi
        SET jenis_dana = (SELECT jenis_dana FROM chart_of_accounts WHERE id = transaksi.coa_id)
        WHERE jenis_dana = 'infak_sedekah' AND coa_id IS NOT NULL
    """)

    # Akun penyaluran baru "Program Dakwah [ID]", paralel dgn akun 5.2.6.xx lain
    # (utk rekap pengeluaran per program yg belum punya akun spesifik)
    c.execute(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) "
        "VALUES ('5.2.6.06','Program Dakwah [ID]','penyaluran_beban','infak_tidak_terikat','5.2.6','keluar')"
    )
    # Akun penerimaan baru "Infaq Program Tahfidz [ITAH]", paralel dgn produk 4.2.1.xx lain
    c.execute(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) "
        "VALUES ('4.2.1.19','Infaq Program Tahfidz [ITAH]','penerimaan','infak_terikat','4.2.1','masuk')"
    )
    # Tandai kode [SD] pada akun Sembako Dhuafa yg sudah ada (dipakai jg utk santunan dhuafa umum)
    c.execute("UPDATE chart_of_accounts SET nama='Sembako Dhuafa [SD]' WHERE kode='5.2.4.01'")

    # Perbaiki jenis_dana akun penyaluran yg py pasangan penerimaan berkode sama (mis. [CY]) —
    # saat pemisahan terikat/tidak-terikat awal, semua akun 5.2.x lama didefault ke tidak-terikat
    # krn belum ada bukti pasangan. Sekarang akun2 ini terbukti terikat (penerimaannya di 4.2.1.x).
    kode_pasangan_terikat = ['5.2.1.02', '5.2.1.03', '5.2.2.01', '5.2.3.01', '5.2.4.02',
                              '5.2.4.03', '5.2.4.04', '5.2.5.01', '5.2.5.02', '5.2.6.01',
                              '5.2.6.03', '5.2.6.06', '5.2.7.01']
    for kode in kode_pasangan_terikat:
        c.execute("UPDATE chart_of_accounts SET jenis_dana='infak_terikat' WHERE kode=?", (kode,))
    placeholders = ','.join('?' * len(kode_pasangan_terikat))
    c.execute(f"""
        UPDATE transaksi SET jenis_dana='infak_terikat'
        WHERE coa_id IN (SELECT id FROM chart_of_accounts WHERE kode IN ({placeholders}))
    """, kode_pasangan_terikat)

    # Akun penyaluran baru "Santunan Dhuafa (Terikat) [IDHU]" — program dhuafa yg didanai
    # dari Infaq Terikat Dhuafa, terpisah dari Sembako Dhuafa [SD] (dana tidak terikat)
    c.execute(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) "
        "VALUES ('5.2.4.05','Santunan Dhuafa (Terikat) [IDHU]','penyaluran_beban','infak_terikat','5.2.4','keluar')"
    )
    # Akun "Hibah ke Dana Lain" — transfer dari Infak Tidak Terikat ke Amil/program terikat
    # yg penerimaannya sendiri belum cukup menutup penyalurannya bulan itu
    c.execute(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) "
        "VALUES ('5.2.8','Hibah ke Dana Lain (Amil/Terikat)','penyaluran_beban','infak_tidak_terikat','5.2','keluar')"
    )

    # Tandai kode [OP] pada akun penerimaan Amil (4.3.3) supaya otomatis berpasangan
    # dgn "Operasional Amil [OP]" (5.2.6.05) di laporan Saldo per Program — keduanya
    # memang lawan penerimaan/pengeluaran dana Amil yg sama.
    c.execute("UPDATE chart_of_accounts SET nama='Penerimaan Lain Dana Amil [OP]' WHERE kode='4.3.3'")

    # ── Pindahkan akun penyaluran yg jenis_dana-nya sudah infak_terikat (krn py
    # pasangan penerimaan terikat) supaya juga SECARA STRUKTUR (kode & parent_kode)
    # berada di bawah grup [5.5] Penyaluran Dana Infak Terikat — sebelumnya kode-nya
    # masih menempel di [5.2] Tidak Terikat shg tdk ketemu saat cari menu transaksi
    # utk program spt Tebar Qurban, OTA, dst di grup Terikat.
    # 5.5.1-5.5.5 semula akun langsung (leaf) kosong tak pernah dipakai -> jadikan
    # grup induk (spt 5.2.1-5.2.5), tambah grup baru 5.5.6 Dakwah & 5.5.7 Qurban.
    c.executemany(
        "UPDATE chart_of_accounts SET jenis_transaksi=NULL WHERE kode=? AND jenis_transaksi='keluar'",
        [('5.5.1',), ('5.5.2',), ('5.5.3',), ('5.5.4',), ('5.5.5',)]
    )
    c.executemany(
        "INSERT OR IGNORE INTO chart_of_accounts (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) VALUES (?,?,?,?,?,?)",
        [
            ('5.5.6', 'Program Dakwah/Advokasi (Terikat)', 'penyaluran_beban', 'infak_terikat', '5.5', None),
            ('5.5.7', 'Program Qurban (Terikat)',            'penyaluran_beban', 'infak_terikat', '5.5', None),
        ]
    )
    # (kode_lama, kode_baru, parent_baru)
    pindah_ke_terikat = [
        ('5.2.1.02', '5.5.1.01', '5.5.1'),  # Orang Tua Asuh [OTA]
        ('5.2.1.03', '5.5.1.02', '5.5.1'),  # Beasiswa PTQ Al Mu'jiz [PTQ]
        ('5.2.2.01', '5.5.2.01', '5.5.2'),  # Sunat Sehat Gratis [SSG]
        ('5.2.3.01', '5.5.3.01', '5.5.3'),  # Pemberdayaan [DAYA]
        ('5.2.4.02', '5.5.4.01', '5.5.4'),  # Cinta Yatim [CY]
        ('5.2.4.03', '5.5.4.02', '5.5.4'),  # Operasional Ambulance [AM]
        ('5.2.4.04', '5.5.4.03', '5.5.4'),  # Bantuan Air Bersih [AB]
        ('5.2.5.01', '5.5.5.01', '5.5.5'),  # Bencana Wonogiri [BW]
        ('5.2.5.02', '5.5.5.02', '5.5.5'),  # Palestina [DI]
        ('5.2.6.01', '5.5.6.01', '5.5.6'),  # Listrik Masjid Gratis [IL]
        ('5.2.6.03', '5.5.6.02', '5.5.6'),  # Honorarium Mubaligh [HM]
        ('5.2.6.06', '5.5.6.03', '5.5.6'),  # Program Dakwah [ID]
        ('5.2.7.01', '5.5.7.01', '5.5.7'),  # Tebar Qurban [TQUR]
    ]
    for kode_lama, kode_baru, parent_baru in pindah_ke_terikat:
        sudah_ada = c.execute("SELECT 1 FROM chart_of_accounts WHERE kode=?", (kode_baru,)).fetchone()
        if sudah_ada:
            # Migrasi kode ini sudah pernah jalan. Seed INSERT OR IGNORE di atas (keyed
            # by kode lama yg kini bebas) bisa membangkitkan lagi baris kode_lama sbg
            # duplikat kosong -- buang drpd nabrak UNIQUE constraint saat rename ulang.
            c.execute(
                "DELETE FROM chart_of_accounts WHERE kode=? "
                "AND id NOT IN (SELECT DISTINCT coa_id FROM transaksi WHERE coa_id IS NOT NULL)",
                (kode_lama,)
            )
            continue
        c.execute("UPDATE chart_of_accounts SET kode=?, parent_kode=? WHERE kode=?",
                   (kode_baru, parent_baru, kode_lama))

    # Grup induk lama yg semua anaknya sudah pindah ke [5.5] jadi kosong (yatim) —
    # nonaktifkan spy tdk muncul lagi di Master Data > Chart of Accounts (bkn dihapus,
    # kode-nya dipertahankan sbg jejak histori).
    c.executemany(
        "UPDATE chart_of_accounts SET aktif=0 WHERE kode=? AND NOT EXISTS "
        "(SELECT 1 FROM chart_of_accounts x WHERE x.parent_kode=chart_of_accounts.kode AND x.aktif=1)",
        [('5.2.2',), ('5.2.3',), ('5.2.5',), ('5.2.7',)]
    )

    conn.commit()
    conn.close()
    print("Database berhasil diinisialisasi.")
    print("Login admin    : admin / admin123")
    print("Login marketing: marketing1 / marketing123")

if __name__ == '__main__':
    init()
