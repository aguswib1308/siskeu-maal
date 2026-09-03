'use strict';

/**
 * gateway.js — Gateway WA kirim-pesan-saja (Baileys) khusus notifikasi
 * penyaluran Baitul Maal (mis. konfirmasi + token listrik masjid).
 * Nomor WA sengaja terpisah dari gateway bmt-tagih & wa-bot laporan harian —
 * kalau nomor ini bermasalah, notifikasi lain tetap jalan.
 *
 * Volume: blast ~40 pesan sekali sebulan (dipicu 1 klik "Simpan & Kirim
 * Notifikasi WA" di bmt-maal, dengan jeda antar kirim di sisi pemanggil).
 * ponytail: kalau volume naik jauh (banyak kelompok besar tiap bulan),
 * pertimbangkan antrian/rate-limit di sini sebelum nambah nomor lagi.
 *
 * Endpoint:
 *   GET  /qr      - halaman scan QR (login WhatsApp pertama kali)
 *   GET  /status  - status koneksi
 *   POST /send    - kirim 1 pesan ke 1 nomor: { no_hp, message }
 *                   Balasan: { status: true } / { status: false, reason }
 *
 * Variabel env (.env):
 *   WA_GATEWAY_PORT   - port HTTP server (default: 3004)
 *   WA_GATEWAY_TOKEN  - token auth header X-Bot-Token
 */

require('dotenv').config();

const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const express = require('express');
const pino = require('pino');

const PORT = parseInt(process.env.WA_GATEWAY_PORT || '3004', 10);
const BOT_TOKEN = process.env.WA_GATEWAY_TOKEN || '';
const AUTH_DIR = './auth_info_baileys';

const app = express();
app.use(express.json());

let sock = null;
let isReady = false;
let qrData = null;

const logger = pino({ level: 'silent' });

function log(msg) {
    const ts = new Date().toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' });
    console.log(`[${ts}] ${msg}`);
}

/** Normalisasi nomor HP ke JID Baileys (628xxx@s.whatsapp.net) */
function toJid(raw) {
    const digits = String(raw || '').replace(/\D/g, '');
    const norm = digits.startsWith('62') ? digits
        : digits.startsWith('0') ? '62' + digits.slice(1)
        : digits;
    return norm ? `${norm}@s.whatsapp.net` : null;
}

// ============================================================
// Koneksi Baileys
// ============================================================
async function startBot() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        logger,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, logger),
        },
        browser: ['BMT Maal Gateway', 'Chrome', '1.0.0'],
        printQRInTerminal: false,
        syncFullHistory: false,
        markOnlineOnConnect: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            qrData = qr;
            qrcode.generate(qr, { small: true });
            log('QR siap. Scan via browser: http://<IP_VPS>:' + PORT + '/qr');
        }

        if (connection === 'close') {
            isReady = false;
            qrData = null;
            const code = lastDisconnect?.error instanceof Boom
                ? lastDisconnect.error.output.statusCode
                : 0;
            const shouldReconnect = code !== DisconnectReason.loggedOut;
            log(`Koneksi terputus (kode ${code}). Reconnect: ${shouldReconnect}`);
            if (shouldReconnect) setTimeout(startBot, 5000);
        } else if (connection === 'open') {
            isReady = true;
            qrData = null;
            log('Gateway WA siap dan terhubung.');
        }
    });

    // Kirim-saja: pesan masuk tidak diproses (tidak ada listener !command / AI).
}

// ============================================================
// HTTP API
// ============================================================

app.get('/qr', async (req, res) => {
    if (isReady) return res.send('<h2>Gateway sudah terhubung ke WhatsApp ✅</h2>');
    if (!qrData) return res.send('<h2>QR belum tersedia, tunggu beberapa detik lalu refresh.</h2><script>setTimeout(()=>location.reload(),3000)</script>');
    try {
        const dataUrl = await QRCode.toDataURL(qrData, { width: 300 });
        res.send(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Scan QR WA Gateway Maal</title></head><body style="text-align:center;font-family:sans-serif;padding:20px"><h2>Scan QR dengan WhatsApp (nomor khusus Baitul Maal)</h2><img src="${dataUrl}" style="width:300px"><p>Buka WhatsApp → titik tiga → <b>Perangkat Tertaut</b> → Tautkan Perangkat</p><p style="color:gray;font-size:12px">Refresh otomatis tiap 20 detik</p><script>setTimeout(()=>location.reload(),20000)</script></body></html>`);
    } catch {
        res.send('<h2>Gagal render QR. Coba refresh.</h2>');
    }
});

app.get('/status', (req, res) => {
    res.json({ ok: true, ready: isReady });
});

// Auth middleware (di bawah /qr & /status supaya keduanya tetap publik)
app.use((req, res, next) => {
    if (BOT_TOKEN && req.headers['x-bot-token'] !== BOT_TOKEN) {
        return res.status(401).json({ status: false, reason: 'Unauthorized' });
    }
    next();
});

app.post('/send', async (req, res) => {
    const { no_hp, message } = req.body || {};
    if (!no_hp || !message) {
        return res.status(400).json({ status: false, reason: 'Field "no_hp" dan "message" wajib diisi' });
    }
    if (!isReady || !sock) {
        return res.status(503).json({ status: false, reason: 'Gateway WA belum terhubung' });
    }
    const jid = toJid(no_hp);
    if (!jid) {
        return res.status(400).json({ status: false, reason: 'Nomor HP tidak valid' });
    }
    try {
        await sock.sendMessage(jid, { text: message });
        log(`Pesan terkirim ke ${jid}`);
        res.json({ status: true });
    } catch (e) {
        log(`Gagal kirim ke ${jid}: ${e.message}`);
        res.status(500).json({ status: false, reason: e.message });
    }
});

// ============================================================
// Start
// ============================================================
app.listen(PORT, '127.0.0.1', () => {
    log(`HTTP API listening di 127.0.0.1:${PORT}`);
    log('Endpoint: POST /send | GET /status | GET /qr');
});

startBot().catch(e => {
    log(`Gagal start gateway: ${e.message}`);
    process.exit(1);
});
