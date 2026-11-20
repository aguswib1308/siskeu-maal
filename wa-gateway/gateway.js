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
 *                   Nomor dinormalisasi & diverifikasi terdaftar di WhatsApp
 *                   (onWhatsApp) sebelum dikirim -- status:true berarti benar2
 *                   terkirim ke akun WA yang ada, bukan sekadar "tidak error".
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

/** Normalisasi nomor HP Indonesia ke digit E.164 tanpa '+' (mis. 628123456789).
 *  Return null kalau nomornya tidak masuk akal sbg nomor HP Indonesia --
 *  lebih baik ditolak dgn alasan jelas daripada dikirim ke JID ngawur.
 *  Versi lama meloloskan nomor tanpa awalan 0/62 apa adanya (mis. '8123...',
 *  khas kolom HP hasil import Excel yg angka 0 depannya kepotong). */
function normalizeNomor(raw) {
    let digits = String(raw || '').replace(/\D/g, '');
    if (!digits) return null;
    if (digits.startsWith('00')) digits = digits.slice(2);   // awalan internasional 0062...
    if (digits.startsWith('62')) {
        // sudah format negara
    } else if (digits.startsWith('0')) {
        digits = '62' + digits.slice(1);
    } else if (digits.startsWith('8')) {
        digits = '62' + digits;                              // angka 0 depan kepotong
    } else {
        return null;
    }
    // Nomor HP Indonesia selalu '8' setelah kode negara (62 8xx ...), panjang
    // lokal 9-13 digit. Cek ini menyaring telepon rumah (0271..., 021...) dan
    // isian ngawur sebelum menyentuh WhatsApp -- tanpa cek awalan '8',
    // '0271123456' lolos jadi '62271123456'.
    const lokal = digits.slice(2);
    if (!lokal.startsWith('8')) return null;
    if (lokal.length < 9 || lokal.length > 13) return null;
    return digits;
}

/** Nomor HP -> JID Baileys (628xxx@s.whatsapp.net). Null kalau nomor tidak valid. */
function toJid(raw) {
    const nomor = normalizeNomor(raw);
    return nomor ? `${nomor}@s.whatsapp.net` : null;
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
    const nomor = normalizeNomor(no_hp);
    if (!nomor) {
        log(`Nomor HP tidak valid, tidak dikirim: ${no_hp}`);
        return res.status(400).json({ status: false, reason: 'Nomor HP tidak valid' });
    }

    // Verifikasi nomor benar-benar terdaftar di WhatsApp SEBELUM kirim.
    // Tanpa ini sock.sendMessage() ke nomor non-WA (salah ketik, nomor rumah,
    // nomor yg belum pernah pakai WA) SUKSES tanpa error, lalu pemanggil
    // (bmt-maal) menandai baris itu wa_status='terkirim' padahal penerima tidak
    // pernah menerima apa pun -- kegagalan paling mahal krn tidak kelihatan.
    let info;
    try {
        const hasil = await sock.onWhatsApp(nomor);
        info = Array.isArray(hasil) && hasil.length ? hasil[0] : null;
    } catch (e) {
        // Gagal cek != nomor tidak ada. Sengaja gagal-tertutup: lebih baik
        // dilaporkan gagal & bisa Kirim Ulang daripada diklaim terkirim.
        log(`Gagal cek pendaftaran ${nomor}: ${e.message}`);
        return res.status(502).json({ status: false, reason: `Gagal cek nomor di WhatsApp: ${e.message}` });
    }
    if (!info || !info.exists) {
        log(`Nomor ${nomor} tidak terdaftar di WhatsApp, tidak dikirim`);
        return res.status(400).json({ status: false, reason: 'Nomor tidak terdaftar di WhatsApp' });
    }

    // Pakai JID dari hasil onWhatsApp (bukan rakitan sendiri) supaya akun yg
    // JID-nya bukan <nomor>@s.whatsapp.net tetap kena.
    const jid = info.jid || toJid(nomor);
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
// Self-check
// ============================================================
// Proyek ini tidak pakai test runner (lihat konvensi wa.py di root: self-check
// manual di __main__). Jalankan `node gateway.js --self-check` -- harus print
// "OK" lalu exit 0, tanpa menyentuh WhatsApp / membuka port.
if (process.argv.includes('--self-check')) {
    const kasus = [
        ['081234567890', '6281234567890'],      // lokal, 0 di depan
        ['6281234567890', '6281234567890'],     // sudah kode negara
        ['+62 812-3456-7890', '6281234567890'], // ada '+' & pemisah
        ['0062812345678', '62812345678'],       // awalan internasional 00
        ['81234567890', '6281234567890'],       // 0 depan kepotong (import Excel)
        ['', null],                             // kosong
        [null, null],
        ['-', null],                            // bukan angka
        ['0271123456', null],                   // telepon rumah, bukan HP
        ['12345', null],                        // terlalu pendek
        ['628123456789012345', null],           // terlalu panjang
        ['628', null],                          // 62 tanpa nomor lokal
    ];
    let gagal = 0;
    for (const [input, harap] of kasus) {
        const hasil = normalizeNomor(input);
        if (hasil !== harap) {
            console.error(`GAGAL: normalizeNomor(${JSON.stringify(input)}) = ${JSON.stringify(hasil)}, harap ${JSON.stringify(harap)}`);
            gagal++;
        }
    }
    if (gagal) {
        console.error(`${gagal} kasus gagal.`);
        process.exit(1);
    }
    console.log('OK');
    process.exit(0);
}

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
