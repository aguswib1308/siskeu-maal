"""
Migrasi: Tambah semua Produk Fundrising & Pentasharufan ke Chart of Accounts.
Jalankan sekali: python add_produk_coa.py
Aman dijalankan berulang (INSERT OR IGNORE).
"""
import sqlite3, os

DB_PATH = os.path.join('data', 'keuangan.db')

# (kode, nama, kelompok, jenis_dana, parent_kode, jenis_transaksi)
ENTRIES = [

    # ═══════════════════════════════════════════════════════════════════════
    # PENERIMAAN – ZAKAT
    # ═══════════════════════════════════════════════════════════════════════
    ('4.1.6', 'Fidyah [F]',
        'penerimaan', 'zakat', '4.1', 'masuk'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENERIMAAN – INFAK TERIKAT  (sub 4.2.1)
    # ═══════════════════════════════════════════════════════════════════════
    ('4.2.1.01', 'Infaq Terikat Pendidikan [OTA]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.02', 'Infaq Terikat Dhuafa [IDHU]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.03', 'Infaq Terikat Bencana [IKEM]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.04', 'Infaq Bencana Wonogiri [BW]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.05', 'Infaq Terikat Palestina [DI]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.06', 'Infaq Terikat Yatim [CY]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.07', 'Infaq Terikat Sunat Sehat Gratis [SSG]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.08', 'Infaq Terikat Mobil Operasional [MOP]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.09', "Infaq Terikat Tebar Qur'an [IQRA]",
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.10', 'Infaq Terikat Listrik Masjid [IL]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.11', 'Program Pemberdayaan [DAYA]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.12', 'Infaq Sembako Awal Tahun [SAT]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.13', 'Infaq Terikat Dakwah [ID]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.14', 'Infaq Terikat Ambulance [AM]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.15', 'Bantuan Air Bersih [AB]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.16', "Infaq Terikat PTQ Al Mu'jiz [PTQ]",
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.17', 'Tebar Qurban [TQUR]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),
    ('4.2.1.18', 'Honorarium Mubaligh [HM]',
        'penerimaan', 'infak_sedekah', '4.2.1', 'masuk'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENERIMAAN – INFAK TIDAK TERIKAT  (sub 4.2.2)
    # ═══════════════════════════════════════════════════════════════════════
    ('4.2.2.01', 'Infak Tidak Terikat Kotak Infaq [KI]',
        'penerimaan', 'infak_sedekah', '4.2.2', 'masuk'),
    ('4.2.2.02', 'Infak Tidak Terikat Kencleng [KC]',
        'penerimaan', 'infak_sedekah', '4.2.2', 'masuk'),
    ('4.2.2.03', 'Infak Tidak Terikat Tunai [I]',
        'penerimaan', 'infak_sedekah', '4.2.2', 'masuk'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENYALURAN – PENDIDIKAN  (sub 5.2.1)
    # ═══════════════════════════════════════════════════════════════════════
    ('5.2.1.01', 'Beasiswa Pendidikan',
        'penyaluran_beban', 'infak_sedekah', '5.2.1', 'keluar'),
    ('5.2.1.02', 'Orang Tua Asuh [OTA]',
        'penyaluran_beban', 'infak_sedekah', '5.2.1', 'keluar'),
    ("5.2.1.03", "Beasiswa PTQ Al Mu'jiz [PTQ]",
        'penyaluran_beban', 'infak_sedekah', '5.2.1', 'keluar'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENYALURAN – KESEHATAN  (sub 5.2.2)
    # ═══════════════════════════════════════════════════════════════════════
    ('5.2.2.01', 'Sunat Sehat Gratis [SSG]',
        'penyaluran_beban', 'infak_sedekah', '5.2.2', 'keluar'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENYALURAN – EKONOMI/PEMBERDAYAAN  (sub 5.2.3)
    # ═══════════════════════════════════════════════════════════════════════
    ('5.2.3.01', 'Pemberdayaan [DAYA]',
        'penyaluran_beban', 'infak_sedekah', '5.2.3', 'keluar'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENYALURAN – SOSIAL/KEMANUSIAAN  (sub 5.2.4)
    # ═══════════════════════════════════════════════════════════════════════
    ('5.2.4.01', 'Sembako Dhuafa',
        'penyaluran_beban', 'infak_sedekah', '5.2.4', 'keluar'),
    ('5.2.4.02', 'Cinta Yatim [CY]',
        'penyaluran_beban', 'infak_sedekah', '5.2.4', 'keluar'),
    ('5.2.4.03', 'Operasional Ambulance [AM]',
        'penyaluran_beban', 'infak_sedekah', '5.2.4', 'keluar'),
    ('5.2.4.04', 'Bantuan Air Bersih [AB]',
        'penyaluran_beban', 'infak_sedekah', '5.2.4', 'keluar'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENYALURAN – BANTUAN BENCANA  (sub 5.2.5)
    # ═══════════════════════════════════════════════════════════════════════
    ('5.2.5.01', 'Bencana Wonogiri [BW]',
        'penyaluran_beban', 'infak_sedekah', '5.2.5', 'keluar'),
    ('5.2.5.02', 'Palestina [DI]',
        'penyaluran_beban', 'infak_sedekah', '5.2.5', 'keluar'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENYALURAN – DAKWAH/ADVOKASI  (sub baru 5.2.6)
    # ═══════════════════════════════════════════════════════════════════════
    ('5.2.6',    'Program Dakwah/Advokasi',
        'penyaluran_beban', 'infak_sedekah', '5.2',   None),
    ('5.2.6.01', 'Listrik Masjid Gratis [IL]',
        'penyaluran_beban', 'infak_sedekah', '5.2.6', 'keluar'),
    ('5.2.6.02', 'Kafalah Guru TPQ [KD]',
        'penyaluran_beban', 'infak_sedekah', '5.2.6', 'keluar'),
    ('5.2.6.03', 'Honorarium Mubaligh [HM]',
        'penyaluran_beban', 'infak_sedekah', '5.2.6', 'keluar'),
    ('5.2.6.04', 'Safari Masjid MKU [SM]',
        'penyaluran_beban', 'infak_sedekah', '5.2.6', 'keluar'),
    ('5.2.6.05', 'Operasional Amil [OP]',
        'penyaluran_beban', 'amil',          '5.2.6', 'keluar'),

    # ═══════════════════════════════════════════════════════════════════════
    # PENYALURAN – QURBAN  (sub baru 5.2.7)
    # ═══════════════════════════════════════════════════════════════════════
    ('5.2.7',    'Program Qurban',
        'penyaluran_beban', 'infak_sedekah', '5.2',   None),
    ('5.2.7.01', 'Tebar Qurban [TQUR]',
        'penyaluran_beban', 'infak_sedekah', '5.2.7', 'keluar'),
]

def run():
    if not os.path.exists(DB_PATH):
        print('ERROR: database tidak ditemukan, jalankan init_db.py terlebih dahulu.')
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ins = skip = 0
    for entry in ENTRIES:
        r = c.execute(
            "INSERT OR IGNORE INTO chart_of_accounts "
            "(kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) VALUES (?,?,?,?,?,?)",
            entry
        )
        if r.rowcount:
            ins += 1
        else:
            skip += 1
    conn.commit()
    conn.close()
    print(f'Selesai: {ins} entri baru ditambahkan, {skip} sudah ada (dilewati).')
    print(f'Total definisi produk: {len(ENTRIES)}')

if __name__ == '__main__':
    run()
