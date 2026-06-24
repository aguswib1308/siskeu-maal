# -*- coding: utf-8 -*-
"""Tambah 3 donatur dari KML yang namanya dobel (titik kedua, belum ada di DB)."""
import sqlite3, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DB = os.path.join('data', 'keuangan.db')
ROWS = [
    ('Bu Warmi',      'kencleng',    -7.8082742, 110.9159507),
    ('Bu Purwanti',   'kencleng',    -7.8259213, 110.9562573),
    ('BAKSO PAK MAN',  'kotak_infaq', -7.8092084, 110.9131512),
]
c = sqlite3.connect(DB)
added = 0
for nama, sumber, lat, lng in ROWS:
    ex = c.execute(
        "SELECT id FROM donatur WHERE nama=? AND lat IS NOT NULL "
        "AND ABS(lat-?)<1e-6 AND ABS(lng-?)<1e-6", (nama, lat, lng)).fetchone()
    if ex:
        print('skip (sudah ada):', nama); continue
    c.execute(
        "INSERT INTO donatur (nama,jenis,sumber_infaq,area,lokasi_nama,lat,lng,aktif,aktif_infaq) "
        "VALUES (?,?,?,?,?,?,?,1,1)",
        (nama, 'perorangan', sumber, '', '', lat, lng))
    added += 1
    print('tambah:', nama, '|', sumber, '|', lat, lng)
c.commit()
print('Total ditambah:', added)
c.close()
