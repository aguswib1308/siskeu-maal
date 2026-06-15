# -*- coding: utf-8 -*-
"""Sortir kolom area: kosongkan nilai yang berupa DESA (diisi manual lagi),
simpan yang berupa DUSUN. Idempoten."""
import sqlite3, sys, os, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB = os.path.join('data', 'keuangan.db')
DESA_REMOVE = {'giriwono', 'bulusulur', 'wonokarto', 'sonoharjo', 'manjung', 'nambangan'}

def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = c.execute("SELECT id, area FROM donatur WHERE area IS NOT NULL AND TRIM(area)<>''").fetchall()
    removed = 0
    for r in rows:
        if r['area'].strip().lower() in DESA_REMOVE:
            c.execute("UPDATE donatur SET area=NULL WHERE id=?", (r['id'],))
            removed += 1
    c.commit()
    sisa = c.execute("SELECT COALESCE(NULLIF(TRIM(area),''),'(kosong)') a, COUNT(*) n FROM donatur GROUP BY a ORDER BY n DESC").fetchall()
    c.close()
    print(f"Area (desa) dikosongkan: {removed}")
    print("\n--- Sisa nilai area (dusun) ---")
    for r in sisa:
        if r['a'] == '(kosong)':
            continue
        print(f"  {r['a']:<16} {r['n']}")

if __name__ == '__main__':
    main()
