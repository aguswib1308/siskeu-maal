#!/bin/bash
# Update kode di VPS setelah ada perubahan.
# Jalankan di VPS: bash /var/www/bmt-maal/deploy/update_vps.sh

set -e
APP_DIR=/var/www/bmt-maal

cd $APP_DIR

echo "=== Pull kode terbaru ==="
git pull

echo "=== Install/update dependencies ==="
venv/bin/pip install -r requirements.txt -q

echo "=== Migrasi DB ==="
sudo -u www-data venv/bin/python init_db.py

echo "=== Restart service ==="
systemctl restart bmt-maal

echo ""
echo "Update selesai. Status:"
systemctl status bmt-maal --no-pager
