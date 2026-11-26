#!/bin/bash
# pindah.sh - pindahkan data Baitul Maal VPS -> mini PC. Jalankan di MINI PC sebagai root.
#   bash pindah.sh siap   salin awal data + rahasia + lockfile npm, VPS TETAP jalan (boleh diulang)
#                         lalu uji lewat uji-maal.bmtamalmuslim.web.id (data salinan, jangan dipakai transaksi)
#   bash pindah.sh final  JENDELA PINDAH: stop VPS, salin terakhir, nyalakan di mini PC
# Syarat: root mini PC bisa SSH ke VPS tanpa sandi (pasang /root/.ssh/id_ed25519.pub mini PC
# ke /root/.ssh/authorized_keys VPS).
# Rollback (< 10 menit): stop+disable 2 layanan di sini, hapus /etc/cron.d/bmt-maal, di VPS
#   systemctl enable --now bmt-maal bmt-maal-wa-gateway && crontab /root/crontab.sebelum-pindah-maal
#   lalu arahkan maal.bmtamalmuslim.web.id kembali ke VPS. Data yang masuk di mini PC sejak final hilang.
set -euo pipefail

VPS=root@103.169.207.190
SRC=/var/www/bmt-maal
APP=/srv/bmt-maal
USR=bmtmaal
MODE=${1:-}
R() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$VPS" "$@"; }

[ "$(id -u)" = 0 ] || { echo "Jalankan sebagai root (sudo)."; exit 1; }
[ "$MODE" = siap ] || [ "$MODE" = final ] || { echo "Pakai: $0 siap|final"; exit 1; }
R true || { echo "SSH ke VPS gagal (lihat syarat di kepala skrip)."; exit 1; }

echo "== cek drift: VPS harus = git, commit sama dengan mini PC"
VH=$(R "cd $SRC && git rev-parse HEAD")
MH=$(git -C "$APP" rev-parse HEAD)
DIRTY=$(R "cd $SRC && git status --short --untracked-files=no")
if [ "$VH" != "$MH" ] || [ -n "$DIRTY" ]; then
    echo "[BERHENTI] VPS $VH / mini PC $MH"; echo "$DIRTY"
    echo "Bawa drift VPS ke git dulu (memori: project_maal_deploy_vps), lalu git pull di sini."
    exit 1
fi

if [ "$MODE" = final ]; then
    echo "== VPS: stop layanan + matikan cron maal (crontab lama disimpan)"
    R "systemctl disable --now bmt-maal bmt-maal-wa-gateway \
       && crontab -l > /root/crontab.sebelum-pindah-maal \
       && grep -v bmt-maal /root/crontab.sebelum-pindah-maal | crontab -"
    echo "== VPS: salinan konsisten DB (aplikasi sudah mati)"
    R "cd $SRC/data && $SRC/venv/bin/python -c \"import sqlite3; s=sqlite3.connect('keuangan.db'); d=sqlite3.connect('keuangan.db.pindah'); s.backup(d); d.close()\" && mv keuangan.db.pindah keuangan.db && rm -f keuangan.db-wal keuangan.db-shm"
fi

echo "== salin data/ (DB + backup) dan sesi WA"
rsync -a --delete -e "ssh -o BatchMode=yes" "$VPS:$SRC/data/" "$APP/data/"
rsync -a --delete -e "ssh -o BatchMode=yes" "$VPS:$SRC/wa-gateway/auth_info_baileys/" "$APP/wa-gateway/auth_info_baileys/"
rsync -a -e "ssh -o BatchMode=yes" "$VPS:$SRC/wa-gateway/sent_messages.json" "$VPS:$SRC/wa-gateway/package-lock.json" "$APP/wa-gateway/"

echo "== rahasia -> /etc (0600), nilai SAMA dengan VPS (SECRET_KEY = sesi login & kunci API laporan)"
R "systemctl show bmt-maal -p Environment --value" | tr ' ' '\n' | sed 's/^"//; s/"$//' | grep '=' > /etc/bmt-maal.env
grep -q '^SECRET_KEY=.\+' /etc/bmt-maal.env || { echo "[BERHENTI] SECRET_KEY tidak terbaca dari VPS."; exit 1; }
R "cat $SRC/wa-gateway/.env" > /etc/bmt-maal-wa-gateway.env
chmod 600 /etc/bmt-maal.env /etc/bmt-maal-wa-gateway.env

echo "== npm ci (lockfile dari VPS) + hak akses"
( cd "$APP/wa-gateway" && npm ci --omit=dev --no-audit --no-fund -s )
chown -R "$USR:$USR" "$APP/data" "$APP/wa-gateway"

echo "== integrity_check"
[ "$(sqlite3 "$APP/data/keuangan.db" 'PRAGMA integrity_check')" = ok ] || { echo "[BERHENTI] DB rusak."; exit 1; }

if [ "$MODE" = siap ]; then
    # Hanya aplikasi web; gateway WA TIDAK dinyalakan (nomor WA masih dipakai VPS)
    systemctl restart bmt-maal
    sleep 2; curl -fsS -o /dev/null -w "login: HTTP %{http_code}\n" http://127.0.0.1:5002/
    echo "SIAP. Uji di uji-maal.bmtamalmuslim.web.id. Ulangi 'siap' kapan saja; final saat jam sepi."
    exit 0
fi

echo "== nyalakan di mini PC + cron"
systemctl enable --now bmt-maal bmt-maal-wa-gateway
install -m 644 "$APP/deploy/minipc/bmt-maal.cron" /etc/cron.d/bmt-maal
sleep 3
systemctl is-active bmt-maal bmt-maal-wa-gateway
curl -fsS -o /dev/null -w "login: HTTP %{http_code}\n" http://127.0.0.1:5002/
KEY=$(grep '^LAPORAN_API_KEY=' /etc/bmt-maal.env | cut -d= -f2-)
curl -fsS -o /dev/null -w "api/laporan-harian: HTTP %{http_code}\n" -H "X-Api-Key: $KEY" http://127.0.0.1:5002/api/laporan-harian
echo "SELESAI. Sekarang: arahkan maal.bmtamalmuslim.web.id ke tunnel (Cloudflare), lalu smoke test"
echo "login + 1 transaksi + 1 notifikasi WA. Log: journalctl -u bmt-maal -u bmt-maal-wa-gateway"
