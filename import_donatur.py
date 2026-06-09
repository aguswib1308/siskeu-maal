"""
Import donatur dari spreadsheet (donatur_list.tsv).
Kolom: Nama | Alamat | NoHP | Kode

Kode mapping:
  KC  -> kencleng
  KI  -> kotak_infaq
  others -> tunai

Logika:
  - Jika nama+sumber_infaq sudah ada di DB:
      update no_hp/alamat/area jika field tersebut masih kosong
  - Jika belum ada: insert baru
  - Koordinat dari KML TIDAK ditimpa

Jalankan: python import_donatur.py
"""
import sqlite3
import os
import csv

DB_PATH  = os.path.join('data', 'keuangan.db')
# Coba data_donatur.txt dulu, fallback ke donatur_list.tsv
TSV_PATH = 'data_donatur.txt' if os.path.exists('data_donatur.txt') else 'donatur_list.tsv'

KODE_SUMBER = {
    'KC': 'kencleng',
    'KI': 'kotak_infaq',
}

def extract_area(alamat):
    if not alamat:
        return None
    parts = [p.strip() for p in alamat.split(',')]
    last = parts[-1].strip()
    # buang angka RT/RW di awal
    tokens = last.split()
    clean = []
    for t in tokens:
        if not any(c.isdigit() for c in t) and len(t) > 2:
            clean.append(t)
    result = ' '.join(clean).strip() if clean else last
    return result if result else None

def clean_phone(hp):
    if not hp:
        return None
    hp = hp.strip().lstrip("'").strip()
    if not hp or hp == '-':
        return None
    # normalise: hapus spasi dalam nomor
    hp = hp.replace(' ', '')
    return hp if len(hp) >= 8 else None

def run():
    if not os.path.exists(TSV_PATH):
        print(f"ERROR: {TSV_PATH} tidak ditemukan.")
        return
    if not os.path.exists(DB_PATH):
        print("ERROR: database belum ada, jalankan init_db.py terlebih dahulu.")
        return

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    inserted = updated = skipped = empty = 0

    with open(TSV_PATH, encoding='utf-8', errors='replace') as f:
        # Deteksi apakah ada header row
        first = f.readline()
        f.seek(0)
        has_header = first.strip().lower().startswith('nama')
        if has_header:
            reader = csv.DictReader(f, delimiter='\t')
        else:
            reader = csv.DictReader(f, delimiter='\t',
                                    fieldnames=['Nama','Alamat','NoHP','Kode'])
        for row in reader:
            nama   = (row.get('Nama') or '').strip()
            alamat = (row.get('Alamat') or '').strip()
            hp     = clean_phone(row.get('NoHP') or '')
            kode   = (row.get('Kode') or '').strip().upper()

            if not nama:
                empty += 1
                continue

            sumber = KODE_SUMBER.get(kode, 'tunai')
            area   = extract_area(alamat)

            existing = c.execute(
                "SELECT id, no_hp, alamat, area FROM donatur WHERE nama=? AND sumber_infaq=?",
                (nama, sumber)
            ).fetchone()

            if existing:
                did, ex_hp, ex_alamat, ex_area = existing
                updates = {}
                if hp and not ex_hp:
                    updates['no_hp'] = hp
                if alamat and not ex_alamat:
                    updates['alamat'] = alamat
                if area and not ex_area:
                    updates['area'] = area
                if updates:
                    sets = ', '.join(f"{k}=?" for k in updates)
                    vals = list(updates.values()) + [did]
                    c.execute(f"UPDATE donatur SET {sets} WHERE id=?", vals)
                    updated += 1
                else:
                    skipped += 1
            else:
                c.execute("""
                    INSERT INTO donatur
                        (nama, alamat, no_hp, sumber_infaq, area, jenis, aktif, aktif_infaq)
                    VALUES (?, ?, ?, ?, ?, 'perorangan', 1,
                            CASE WHEN ? IN ('kencleng','kotak_infaq') THEN 1 ELSE 0 END)
                """, (nama, alamat or None, hp, sumber, area, sumber))
                inserted += 1

    conn.commit()
    conn.close()

    print(f"Selesai:")
    print(f"  Baru dimasukkan : {inserted}")
    print(f"  Diperbarui (HP/alamat/area): {updated}")
    print(f"  Sudah lengkap (skip): {skipped}")
    print(f"  Baris kosong diabaikan: {empty}")
    print()

    # ringkasan area
    conn2 = sqlite3.connect(DB_PATH)
    rows = conn2.execute("""
        SELECT area, COUNT(*) as n
        FROM donatur
        WHERE area IS NOT NULL
        GROUP BY area ORDER BY n DESC
        LIMIT 20
    """).fetchall()
    print("Top 20 area setelah import:")
    for r in rows:
        print(f"  {r[0]}: {r[1]} donatur")
    conn2.close()

if __name__ == '__main__':
    run()
