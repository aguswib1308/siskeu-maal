# -*- coding: utf-8 -*-
"""Sinkronisasi koordinat dari file KML ke database donatur.
Cocokkan by nama dengan fuzzy match (strip prefix Pak/Bapak/Bu/Ibu/dll).
Mode: dry-run (default) atau --apply.
"""
import sys, re, sqlite3, os
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

KML_PATH = sys.argv[1] if len(sys.argv) > 1 else 'KOTAK & KENCLENG.kml'
DB_PATH  = os.path.join('data', 'keuangan.db')
APPLY    = '--apply' in sys.argv

PREFIXES = ['bapak', 'pak', 'ibu', 'bu', 'sdr.', 'sdr', 'saudara',
            'mbak', 'mas', 'ustadz', 'ustadzah', 'dr.', 'dr', 'h.', 'hj.', 'p.']
PREFIX_NORM = set(p.rstrip('.') for p in PREFIXES)

def normalize(name):
    s = (name or '').lower().strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def strip_prefix(norm):
    tokens = norm.split(' ')
    changed = True
    while changed and tokens:
        changed = False
        if tokens[0].rstrip('.') in PREFIX_NORM:
            tokens = tokens[1:]
            changed = True
    return ' '.join(tokens)

def parse_kml(path):
    """Return list of dicts: {name, lat, lng, folder}."""
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {'k': 'http://www.opengis.net/kml/2.2'}
    out = []
    for folder in root.iter('{http://www.opengis.net/kml/2.2}Folder'):
        fname_el = folder.find('k:name', ns)
        folder_name = fname_el.text.strip() if fname_el is not None and fname_el.text else ''
        for pm in folder.findall('k:Placemark', ns):
            nm = pm.find('k:name', ns)
            coord = pm.find('.//k:coordinates', ns)
            if nm is None or coord is None or not coord.text:
                continue
            name = (nm.text or '').strip()
            parts = coord.text.strip().split(',')
            if len(parts) < 2:
                continue
            try:
                lng = float(parts[0]); lat = float(parts[1])
            except ValueError:
                continue
            out.append({'name': name, 'lat': lat, 'lng': lng, 'folder': folder_name})
    return out

def main():
    placemarks = parse_kml(KML_PATH)
    print(f"KML: {len(placemarks)} placemark")
    by_folder = {}
    for p in placemarks:
        by_folder[p['folder']] = by_folder.get(p['folder'], 0) + 1
    print("  Per folder:", by_folder)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    donatur = conn.execute("SELECT id, nama, lat, lng FROM donatur").fetchall()
    print(f"DB: {len(donatur)} donatur\n")

    # Index DB by exact-normalized and prefix-stripped key -> list of records
    exact_idx, fuzzy_idx = {}, {}
    for d in donatur:
        nrm = normalize(d['nama'])
        exact_idx.setdefault(nrm, []).append(dict(d))
        fuzzy_idx.setdefault(strip_prefix(nrm), []).append(dict(d))

    consumed = set()   # donatur ids already matched
    updated, same, ambiguous, notfound = [], [], [], []

    def pick(candidates):
        """Pilih kandidat: utamakan yang belum dipakai & koord kosong."""
        free = [c for c in candidates if c['id'] not in consumed]
        if not free:
            return None
        empty = [c for c in free if c['lat'] is None or c['lng'] is None]
        return (empty or free)[0]

    for p in placemarks:
        nrm = normalize(p['name'])
        cand = exact_idx.get(nrm)
        how = 'exact'
        if not cand:
            cand = fuzzy_idx.get(strip_prefix(nrm))
            how = 'fuzzy'
        if not cand:
            notfound.append(p)
            continue
        chosen = pick(cand)
        if chosen is None:
            ambiguous.append((p, cand))
            continue
        consumed.add(chosen['id'])
        old_lat, old_lng = chosen['lat'], chosen['lng']
        # bandingkan dgn toleransi kecil
        def close(a, b):
            return a is not None and b is not None and abs(a - b) < 1e-6
        if close(old_lat, p['lat']) and close(old_lng, p['lng']):
            same.append((p, chosen))
        else:
            updated.append((p, chosen, how))
            if APPLY:
                conn.execute("UPDATE donatur SET lat=?, lng=? WHERE id=?",
                             (p['lat'], p['lng'], chosen['id']))

    if APPLY:
        conn.commit()

    print(f"=== HASIL {'(APPLIED)' if APPLY else '(DRY-RUN)'} ===")
    print(f"Update koordinat : {len(updated)}")
    print(f"Sudah sama       : {len(same)}")
    print(f"Ambigu (nama dobel, kandidat habis): {len(ambiguous)}")
    print(f"Tidak ditemukan  : {len(notfound)}\n")

    if updated:
        print("--- Contoh update (maks 15) ---")
        for p, c, how in updated[:15]:
            print(f"  [{how}] DB#{c['id']} '{c['nama']}' <- '{p['name']}' ({p['lat']},{p['lng']}) [koord lama: {c['lat']},{c['lng']}]")
    if ambiguous:
        print(f"\n--- Ambigu ({len(ambiguous)}) ---")
        for p, cand in ambiguous[:20]:
            print(f"  '{p['name']}' [{p['folder']}] -> {len(cand)} kandidat semua sudah dipakai")
    if notfound:
        print(f"\n--- Tidak ditemukan di DB ({len(notfound)}) ---")
        for p in notfound:
            print(f"  '{p['name']}' [{p['folder']}] ({p['lat']},{p['lng']})")

    conn.close()

if __name__ == '__main__':
    main()
