# -*- coding: utf-8 -*-
"""Reverse-geocode donatur (lat,lng) -> nama desa via Nominatim. READ-ONLY.
Simpan hasil ke geocode_result.json (key by koordinat) + cetak ringkasan."""
import sqlite3, json, time, sys, urllib.request, urllib.parse, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB = 'data/keuangan.db'
HDR = {'User-Agent': 'bmt-maal-geocode/1.0 (amalmuslim.bmt@gmail.com)'}

def geocode(lat, lng):
    q = urllib.parse.urlencode({'lat': lat, 'lon': lng, 'format': 'jsonv2',
                                'addressdetails': 1, 'accept-language': 'id', 'zoom': 16})
    url = 'https://nominatim.openstreetmap.org/reverse?' + q
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=HDR)
            d = json.load(urllib.request.urlopen(req, timeout=30))
            a = d.get('address', {})
            desa = a.get('village') or a.get('suburb') or a.get('neighbourhood') or a.get('hamlet') or a.get('town') or ''
            kec = a.get('subdistrict') or a.get('municipality') or a.get('city_district') or ''
            return desa.strip(), kec.strip()
        except Exception:
            time.sleep(2)
    return '', ''

def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = c.execute("SELECT id,nama,lat,lng FROM donatur WHERE lat IS NOT NULL AND lng IS NOT NULL").fetchall()
    c.close()
    print(f"Geocode {len(rows)} titik...\n", flush=True)
    result = {}
    for i, r in enumerate(rows, 1):
        desa, kec = geocode(r['lat'], r['lng'])
        key = f"{round(r['lat'],6)},{round(r['lng'],6)}"
        result[key] = {'desa': desa, 'kec': kec, 'nama': r['nama']}
        if i % 20 == 0:
            print(f"  ...{i}/{len(rows)}", flush=True)
        time.sleep(1.1)
    json.dump(result, open('geocode_result.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    desa_count = collections.Counter(v['desa'] or '(kosong)' for v in result.values())
    unresolved = [v for v in result.values() if not v['desa']]
    print(f"\n=== RINGKASAN ===")
    print(f"Total geocoded   : {len(result)}")
    print(f"Dapat desa       : {len(result) - len(unresolved)}")
    print(f"Tidak dapat desa : {len(unresolved)}")
    print(f"Jumlah desa unik : {len([d for d in desa_count if d != '(kosong)'])}\n")
    print("--- Distribusi per desa ---")
    for d, n in desa_count.most_common():
        print(f"  {d:<28} {n}")
    if unresolved:
        print("\n--- Titik tanpa desa (manual) ---")
        for v in unresolved:
            print(f"  {v['nama']}")

if __name__ == '__main__':
    main()
