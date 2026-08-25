"""Cron: buka periode koleksi fundraising bulan berjalan secara otomatis.
Dijadwalkan tiap tanggal 1 (lihat crontab VPS). Idempotent -- aman dijalankan
ulang, buka_periode() melewati donatur yg sudah py record bulan tsb.

Jalankan dari root proyek: python cron_buka_periode.py
"""
from datetime import date
from app import buka_periode

if __name__ == '__main__':
    bulan = date.today().strftime('%Y-%m')
    created = buka_periode(bulan, None)
    print(f"[{date.today().isoformat()}] Buka periode {bulan}: {created} record koleksi baru dibuat.")
