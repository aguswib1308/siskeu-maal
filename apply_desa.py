# -*- coding: utf-8 -*-
"""Isi kolom desa/kecamatan donatur dari geocode_result.json.
Hanya seed nama desa yang valid; perumahan & 'Wonogiri' (town-fallback) dikosongkan
agar diset manual. Cocok by koordinat (lat,lng) — sama di lokal & VPS."""
import sqlite3, json, sys, os, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB = os.path.join('data', 'keuangan.db')
RESULT = 'geocode_result.json'

def is_bad(desa):
    if not desa:
        return True
    d = desa.lower()
    if 'perumahan' in d or 'safira' in d:
        return True
    if d.strip() == 'wonogiri':       # town-fallback, bukan desa
        return True
    return False

def main():
    res = json.load(open(RESULT, encoding='utf-8'))
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    # pastikan kolom ada
    cols = {r[1] for r in conn.execute("PRAGMA table_info(donatur)")}
    if 'desa' not in cols:
        conn.execute("ALTER TABLE donatur ADD COLUMN desa TEXT")
    if 'kecamatan' not in cols:
        conn.execute("ALTER TABLE donatur ADD COLUMN kecamatan TEXT")

    rows = conn.execute("SELECT id,lat,lng FROM donatur WHERE lat IS NOT NULL AND lng IS NOT NULL").fetchall()
    seeded, blanked = 0, 0
    dist = collections.Counter()
    for r in rows:
        key = f"{round(r['lat'],6)},{round(r['lng'],6)}"
        g = res.get(key)
        if not g:
            continue
        desa = (g.get('desa') or '').strip()
        kec = (g.get('kec') or '').strip()
        if is_bad(desa):
            conn.execute("UPDATE donatur SET desa=NULL, kecamatan=? WHERE id=?", (kec or None, r['id']))
            blanked += 1
        else:
            conn.execute("UPDATE donatur SET desa=?, kecamatan=? WHERE id=?", (desa, kec or None, r['id']))
            seeded += 1
            dist[desa] += 1
    conn.commit()
    total_set = conn.execute("SELECT COUNT(*) FROM donatur WHERE desa IS NOT NULL AND TRIM(desa)<>''").fetchone()[0]
    need = conn.execute("SELECT COUNT(*) FROM donatur WHERE lat IS NOT NULL AND (desa IS NULL OR TRIM(desa)='')").fetchone()[0]
    conn.close()

    print(f"Seed desa  : {seeded}")
    print(f"Dikosongkan (perlu set manual): {blanked}")
    print(f"Total desa terisi sekarang     : {total_set}")
    print(f"Titik berkoordinat tanpa desa  : {need}")
    print("\n--- Distribusi desa hasil seed ---")
    for d, n in dist.most_common():
        print(f"  {d:<20} {n}")

if __name__ == '__main__':
    main()
