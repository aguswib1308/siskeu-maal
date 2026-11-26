#!/bin/bash
# pasang.sh - siapkan Baitul Maal di mini PC (Ubuntu Server 26.04.1 LTS). Root, aman diulang:
#   git clone https://github.com/aguswib1308/siskeu-maal.git /srv/bmt-maal
#   bash /srv/bmt-maal/deploy/minipc/pasang.sh
# Hanya MEMASANG. Tidak menyalakan layanan & tidak memasang cron: data dan sesi WA
# masih di VPS. Lanjut: pindah.sh siap  ->  uji  ->  pindah.sh final
set -euo pipefail

APP=/srv/bmt-maal
USR=bmtmaal
D=$APP/deploy/minipc

[ "$(id -u)" = 0 ] || { echo "Jalankan sebagai root (sudo)."; exit 1; }
[ -f "$APP/app.py" ] || { echo "Kode belum ada di $APP (git clone dulu)."; exit 1; }

echo "== 1. paket sistem"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nodejs npm nginx rsync git sqlite3 >/dev/null
node -e 'process.exit(+process.versions.node.split(".")[0] < 20)' || { echo "Node < 20, Baileys butuh >= 20."; exit 1; }

echo "== 2. user layanan & folder"
id "$USR" >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin "$USR"
mkdir -p "$APP/data/backups"
chown -R "$USR:$USR" "$APP/data" "$APP/wa-gateway"
chmod 750 "$APP/data"

echo "== 3. venv + dependensi Python"
[ -d "$APP/venv" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"

echo "== 4. tes (DB sementara) - harus lulus"
for t in "$APP"/test_*.py; do
    case "$t" in *LAPTOP*) continue;; esac
    ( cd "$APP" && "$APP/venv/bin/python" "$t" ) | tail -1
done

echo "== 5. systemd (dipasang, BELUM dinyalakan)"
install -m 644 "$D/bmt-maal.service" "$D/bmt-maal-wa-gateway.service" /etc/systemd/system/
systemctl daemon-reload

echo "== 6. nginx"
install -m 644 "$D/nginx-maal.conf" /etc/nginx/sites-available/bmt-maal
ln -sf /etc/nginx/sites-available/bmt-maal /etc/nginx/sites-enabled/bmt-maal
nginx -t && systemctl reload nginx

echo "SELESAI. Berikutnya: bash $D/pindah.sh siap"
