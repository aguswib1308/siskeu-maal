"""
Import donatur kencleng & kotak infaq dari file KML Google My Maps.
Jalankan: python import_kml.py
Pastikan file donatur_map.kml ada di folder ini.
"""
import sqlite3
import xml.etree.ElementTree as ET
import os
from collections import Counter

DB_PATH  = os.path.join('data', 'keuangan.db')
KML_PATH = 'donatur_map.kml'
NS       = 'http://www.opengis.net/kml/2.2'

LAYER_MAP = {
    'kencleng':   'kencleng',
    'mku':        'kotak_infaq',
    'kotak infaq':'kotak_infaq',
    'kotak_infaq':'kotak_infaq',
}

def parse_kml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    doc  = root.find(f'{{{NS}}}Document') or root
    rows = []

    for folder in doc.findall(f'.//{{{NS}}}Folder'):
        fname  = (folder.findtext(f'{{{NS}}}name') or '').strip()
        sumber = LAYER_MAP.get(fname.lower(), 'kotak_infaq')

        for pm in folder.findall(f'{{{NS}}}Placemark'):
            nama  = (pm.findtext(f'{{{NS}}}name') or '').strip()
            coord = pm.find(f'.//{{{NS}}}Point/{{{NS}}}coordinates')
            if not nama or coord is None:
                continue
            parts = coord.text.strip().split(',')
            if len(parts) < 2:
                continue
            try:
                lng = float(parts[0])
                lat = float(parts[1])
            except ValueError:
                continue
            rows.append({'nama': nama, 'sumber_infaq': sumber,
                         'lat': lat, 'lng': lng,
                         'lokasi_nama': nama, 'folder': fname})
    return rows

def import_to_db(rows):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    ok = skip = 0

    for d in rows:
        exists = c.execute(
            "SELECT id FROM donatur WHERE nama=? AND sumber_infaq=?",
            (d['nama'], d['sumber_infaq'])
        ).fetchone()
        if exists:
            skip += 1
            continue
        c.execute("""
            INSERT INTO donatur (nama, sumber_infaq, lat, lng, lokasi_nama,
                                 jenis, aktif, aktif_infaq)
            VALUES (?, ?, ?, ?, ?, 'perorangan', 1, 1)
        """, (d['nama'], d['sumber_infaq'], d['lat'], d['lng'], d['lokasi_nama']))
        ok += 1

    conn.commit()
    conn.close()
    return ok, skip

if __name__ == '__main__':
    if not os.path.exists(KML_PATH):
        print(f"ERROR: {KML_PATH} tidak ditemukan.")
        print("Taruh file KML hasil export Google My Maps di folder ini,")
        print("beri nama 'donatur_map.kml', lalu jalankan ulang.")
        exit(1)

    if not os.path.exists(DB_PATH):
        print("ERROR: database belum ada, jalankan init_db.py terlebih dahulu.")
        exit(1)

    print(f"Membaca {KML_PATH} ...")
    rows = parse_kml(KML_PATH)
    print(f"Ditemukan {len(rows)} titik:")
    for folder, n in Counter(d['folder'] for d in rows).items():
        sumber = LAYER_MAP.get(folder.lower(), 'kotak_infaq')
        print(f"  [{folder}] -> {sumber}: {n} titik")

    ok, skip = import_to_db(rows)
    print(f"\nSelesai: {ok} diimport, {skip} dilewati (sudah ada).")
    print("Buka Admin > Master > Donatur untuk melengkapi kolom Area.")
