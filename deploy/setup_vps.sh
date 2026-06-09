#!/bin/bash
# Jalankan di VPS sebagai root:
#   bash setup_vps.sh
# Pastikan kode sudah ter-upload ke /var/www/bmt-maal/ sebelum menjalankan ini.

set -e
APP_DIR=/var/www/bmt-maal

echo "=== 1. Install sistem dependencies ==="
apt-get update -qq
apt-get install -y python3-pip python3-venv

echo "=== 2. Buat folder log ==="
mkdir -p /var/log/bmt-maal
chown www-data:www-data /var/log/bmt-maal

echo "=== 3. Setup virtualenv & install requirements ==="
cd $APP_DIR
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q

echo "=== 4. Inisialisasi database ==="
mkdir -p data
chown -R www-data:www-data $APP_DIR

echo "=== 5. Inisialisasi DB (hanya pertama kali) ==="
sudo -u www-data venv/bin/python init_db.py

echo "=== 6. Install systemd service ==="
cp deploy/bmt-maal.service /etc/systemd/system/bmt-maal.service
systemctl daemon-reload
systemctl enable bmt-maal
systemctl restart bmt-maal

echo "=== 7. Install Nginx config ==="
cp deploy/nginx-maal.conf /etc/nginx/sites-available/bmt-maal
ln -sf /etc/nginx/sites-available/bmt-maal /etc/nginx/sites-enabled/bmt-maal
nginx -t && systemctl reload nginx

echo "=== 8. Buka port 8080 di firewall (UFW) ==="
ufw allow 8080/tcp 2>/dev/null || true

echo ""
echo "======================================"
echo " SELESAI!"
echo " Akses: http://103.169.207.190:8080"
echo " Login admin    : admin / admin123"
echo " Login marketing: marketing1 / marketing123"
echo "======================================"

systemctl status bmt-maal --no-pager
