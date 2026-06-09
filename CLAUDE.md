# SISTEM KEUANGAN BAITUL MAAL

## Deskripsi
Aplikasi manajemen keuangan Baitul Maal — admin pakai desktop (browser), marketing pakai HP (mobile browser).

## Stack
- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML/CSS/JS + Bootstrap 5 (responsive)
- **Server lokal**: Flask dev server (admin desktop)
- **Deployment**: VPS (opsional, untuk akses marketing via HP)

## Struktur Folder
```
SISTEM KEUANGAN MAAL/
├── app.py              # Main Flask app
├── init_db.py          # Inisialisasi database
├── requirements.txt    # Dependencies Python
├── .gitignore
├── static/
│   ├── css/            # Custom CSS
│   ├── js/             # Custom JS
│   └── img/            # Gambar/logo
├── templates/
│   ├── admin/          # Halaman khusus admin (desktop)
│   └── marketing/      # Halaman khusus marketing (mobile)
└── data/
    └── keuangan.db     # Database SQLite
```

## Cara Jalankan
```bash
pip install -r requirements.txt
python init_db.py      # Pertama kali saja
python app.py
```
Akses: http://localhost:5000

## Role User
- **Admin**: akses penuh, buka di desktop browser
- **Marketing**: akses terbatas, buka di HP browser

## Konvensi
- Template admin: layout lebar (desktop), sidebar navigasi
- Template marketing: layout mobile-first, bottom navigation
- Database: SQLite di folder `data/`
- Semua route API prefix `/api/`
- Login session pakai Flask session

## Referensi
- Proyek terkait: BMT Billing System (bmt-tagih) di VPS 103.169.207.190
