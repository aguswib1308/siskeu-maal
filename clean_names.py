# -*- coding: utf-8 -*-
"""Bersihkan nama donatur: hapus prefix panggilan di awal (juga setelah gelar Dr./H.).
Nama usaha aman (diawali Toko/Bakso/dll, bukan panggilan). Idempoten.
Mode: dry-run (default) / --apply."""
import sqlite3, sys, os, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB = os.path.join('data', 'keuangan.db')
APPLY = '--apply' in sys.argv

TITLES = {'dr', 'h', 'hj', 'ir', 'drs'}
PANGGILAN = {'bapak', 'pak', 'ibu', 'bu', 'mas', 'mbak', 'sdr', 'sdri', 'saudara'}

def clean(name):
    s = re.sub(r'\s+', ' ', (name or '').strip())
    tokens = s.split(' ')
    if not tokens:
        return name
    out, i = [], 0
    if tokens[0].lower().rstrip('.') in TITLES:   # pertahankan gelar di depan
        out.append(tokens[0]); i = 1
    while i < len(tokens) and tokens[i].lower().rstrip('.') in PANGGILAN:
        i += 1
    out.extend(tokens[i:])
    res = ' '.join(out).strip()
    return res if res else s   # jangan kosongkan nama

def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = c.execute("SELECT id, nama FROM donatur").fetchall()
    changes = []
    for r in rows:
        nm = r['nama'] or ''
        cl = clean(nm)
        if cl != nm.strip():
            changes.append((r['id'], nm, cl))
            if APPLY:
                c.execute("UPDATE donatur SET nama=? WHERE id=?", (cl, r['id']))
    if APPLY:
        c.commit()
    c.close()
    print(f"{'APPLIED' if APPLY else 'DRY-RUN'}: {len(changes)} nama dibersihkan dari {len(rows)} total")
    for did, a, b in changes[:35]:
        print(f"  {a!r:<28} -> {b!r}")
    if len(changes) > 35:
        print(f"  ... dan {len(changes)-35} lagi")

if __name__ == '__main__':
    main()
