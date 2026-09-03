# Desain: Penyaluran Kelompok + Notifikasi WA Takmir

**Tanggal:** 2026-09-03
**Status:** Disetujui, siap dibuatkan rencana implementasi

## Latar Belakang

Baitul Maal tiap bulan menyalurkan dana ke ~40 masjid untuk program Listrik
Masjid (akun CoA `5.5.6.01`, dana infak terikat). Penerimanya hampir selalu
sama tiap bulan, hanya nominalnya yang beda (sesuai tagihan/kebutuhan token
bulan itu). Sebagian masjid postpaid (BMT bayar tagihan PLN langsung),
sebagian prepaid (BMT belikan token, lalu token diteruskan ke takmir).

Dua masalah yang mau diselesaikan:

1. **Input berulang.** Mencatat 40 transaksi keluar satu-per-satu tiap bulan
   itu lambat, padahal daftar penerimanya nyaris tidak berubah.
2. **Notifikasi manual.** Tiap bulan admin memberi tahu takmir secara manual
   (WA satu-satu) bahwa pembayaran sudah dilakukan, termasuk kirim kode token
   untuk yang prepaid. Ini juga belum pernah diotomasi — bmt-maal saat ini
   sama sekali belum punya pengiriman WA (beda dari proyek BMT lain yang
   sudah pakai Fonnte/gateway sendiri).

Fitur ini dibuat **generik** — bukan cuma untuk Listrik Masjid — supaya bisa
dipakai untuk program penyaluran rutin bulanan lain di masa depan (mis. honor
mubaligh, santunan dhuafa rutin) tanpa perubahan skema.

## Pola yang Ditiru

App ini sudah punya pola yang persis sama di sisi **penerimaan**: menu
Fundraising untuk donatur kencleng/kotak infaq, berbasis tabel
`koleksi_bulanan` — "buka periode" generate satu baris per donatur aktif per
bulan, lalu admin tinggal mengisi. Fitur ini adalah versi mirror-nya untuk
sisi **penyaluran**, supaya konsisten dengan konvensi yang sudah ada dan
familiar buat admin.

Prefill nominal dari bulan sebelumnya meniru pola "tebakan mustahik" yang
sudah ada di halaman Transaksi (`perlu_lengkap` / `tebakan_mustahik`).

## Pendekatan yang Dipertimbangkan

- **A — Tabel kelompok + keanggotaan tetap + periode bulanan (dipilih).**
  Mirror `koleksi_bulanan`. Admin daftarkan anggota kelompok sekali di awal;
  tiap bulan tinggal "buka periode" lalu isi nominal yang beda-beda saja.
  Ada jejak audit per baris (status kirim WA, link ke transaksi).
- **B — Input massal tanpa keanggotaan tetap.** Halaman pilih banyak
  `penerima_manfaat` via checkbox + nominal per baris, langsung jadi N
  transaksi, tanpa tabel periode/status kirim. Lebih sedikit kode, tapi admin
  tetap harus mencari & mencentang 40 nama tiap bulan — tidak benar-benar
  menghilangkan pekerjaan berulang yang jadi keluhan utama. **Ditolak.**
- **C — Full automation (cron auto-buka-periode, auto-kirim terjadwal).**
  Berlebihan untuk kebutuhan saat ini; admin masih perlu mengoreksi nominal
  tiap bulan secara manual, jadi tidak ada gunanya proses ini berjalan tanpa
  pemicu manusia. **Ditolak (YAGNI).**

## Data Model

### `kelompok_penyaluran`
Definisi satu program penyaluran rutin (mis. "Listrik Masjid").

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER PK | |
| nama | TEXT NOT NULL | mis. "Listrik Masjid" |
| coa_id | INTEGER REFERENCES chart_of_accounts(id) | akun tetap untuk semua transaksi kelompok ini |
| pakai_token | INTEGER DEFAULT 0 | 1 kalau anggotanya punya tipe postpaid/prepaid + field token |
| template_pesan | TEXT | template WA default (dipakai langsung kalau `pakai_token=0`, atau untuk anggota postpaid kalau `pakai_token=1`) |
| template_pesan_prepaid | TEXT | template WA khusus anggota prepaid (hanya relevan kalau `pakai_token=1`) |
| aktif | INTEGER DEFAULT 1 | |
| created_at | TEXT | |

### `kelompok_penyaluran_anggota`
Keanggotaan tetap — siapa saja yang rutin menerima dari kelompok ini.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER PK | |
| kelompok_id | INTEGER REFERENCES kelompok_penyaluran(id) | |
| penerima_id | INTEGER REFERENCES penerima_manfaat(id) | reuse tabel penerima yang sudah ada (nama, no_hp, alamat) |
| tipe | TEXT CHECK(tipe IN ('postpaid','prepaid')) NULL | hanya diisi kalau kelompok `pakai_token=1` |
| urutan | INTEGER DEFAULT 0 | untuk pengurutan tampilan |
| aktif | INTEGER DEFAULT 1 | nonaktifkan tanpa hapus riwayat |
| UNIQUE(kelompok_id, penerima_id) | | satu penerima sekali per kelompok |

### `kelompok_penyaluran_bulanan`
Mirror `koleksi_bulanan` — satu baris per anggota per bulan.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER PK | |
| anggota_id | INTEGER REFERENCES kelompok_penyaluran_anggota(id) | |
| bulan | TEXT | format `YYYY-MM` |
| jumlah | REAL | nominal bulan itu |
| token | TEXT NULL | kode token PLN, diisi manual kalau tipe prepaid |
| status | TEXT CHECK(status IN ('draft','tersalur')) DEFAULT 'draft' | |
| transaksi_id | INTEGER REFERENCES transaksi(id) NULL | terisi setelah disimpan |
| wa_status | TEXT CHECK(wa_status IN ('belum','terkirim','gagal')) DEFAULT 'belum' | |
| wa_error | TEXT NULL | alasan gagal, untuk ditampilkan ke admin |
| wa_sent_at | TEXT NULL | |
| created_at | TEXT | |
| UNIQUE(anggota_id, bulan) | | cegah buka periode dobel |

## Alur Kerja

1. **Setup kelompok (sekali di awal).** Admin bikin kelompok "Listrik
   Masjid", pilih akun CoA `5.5.6.01`, aktifkan `pakai_token`, isi 2 template
   pesan. 40 masjid dimasukkan ke `penerima_manfaat` (pakai fitur Import
   Excel yang sudah ada kalau belum terdaftar), lalu ditandai sebagai
   anggota kelompok + tipe postpaid/prepaid masing-masing.
2. **Buka periode.** Admin klik "Buka Periode Bulan Ini" di halaman detail
   kelompok → sistem generate baris `kelompok_penyaluran_bulanan` untuk
   semua anggota aktif, `jumlah` di-prefill dari nominal bulan sebelumnya
   (kalau ada) sebagai titik awal, `status='draft'`.
3. **Isi & simpan.** Admin buka tabel bulan itu, koreksi nominal yang beda
   (+ token untuk yang prepaid), lalu klik **"Simpan & Kirim Notifikasi
   WA"**. Server, untuk tiap baris dengan `jumlah > 0`:
   - Bikin `transaksi` (jenis=`keluar`, `coa_id` dari kelompok, `penerima_id`
     dari anggota, `jumlah`, keterangan otomatis "Penyaluran {nama
     kelompok} – {bulan}").
   - Update baris `kelompok_penyaluran_bulanan`: `status='tersalur'`,
     `transaksi_id`.
   - Kirim WA ke `no_hp` penerima pakai template sesuai tipe (dengan jeda ±2
     detik antar kirim), lalu catat `wa_status`/`wa_error`/`wa_sent_at`.
4. **Retry kalau ada yang gagal.** Halaman hasil menampilkan status kirim
   per baris. Baris dengan `wa_status='gagal'` punya tombol "Kirim Ulang"
   yang cuma mengulang langkah kirim WA (transaksi tidak dibuat ulang).

## Gateway WA Baru (khusus Baitul Maal)

Bukan reuse gateway `bmt-tagih` (nomor beda by design). Dibuat baru dengan
pola identik ke `bmt-tagih-vps/wa-gateway/gateway.js` (Baileys, kirim-saja,
tanpa listener AI) — copy pola, bukan copy instance:

- Folder baru `bmt-maal/wa-gateway/` (gateway.js, package.json, .env.example).
- Port baru (mis. **3004** — 3002 dipakai tagihan, 3003 dipakai laporan
  harian; dicek dulu saat implementasi biar tidak bentrok).
- Endpoint sama: `GET /qr`, `GET /status`, `POST /send {no_hp, message}`
  dengan header `X-Bot-Token`, balasan `{status: true/false}`.
- Systemd service baru `bmt-maal-wa-gateway`, jalan di VPS billing yang sama
  (satu VPS sudah menghost billing+maal+absensi+sis-arsip).
- **Prasyarat operasional:** perlu nomor WA baru khusus Baitul Maal (SIM +
  HP yang bisa dipakai scan QR sekali saat setup). Ini di luar kendali kode
  — perlu disiapkan user sebelum langkah deploy gateway.
- Karena ini blast ~40 pesan sekaligus (beda dari gateway tagihan yang
  kirim manual satu-satu), loop pengiriman di sisi `bmt-maal` diberi jeda
  ±2 detik antar pesan untuk memperkecil risiko nomor kena banned/limit.

## Template Pesan

Placeholder yang didukung: `{nama}` (nama penerima/masjid), `{bulan}`
(format "September 2026"), `{nominal}` (format rupiah), `{token}` (khusus
template prepaid).

Draft awal (bisa diedit admin lewat form kelompok, bukan hardcode):

- **Postpaid / default:**
  > Assalamu'alaikum, Takmir Masjid {nama}. Kami informasikan tagihan
  > listrik bulan {bulan} sebesar Rp{nominal} telah kami bayarkan.
  > Jazakumullahu khairan. - Baitul Maal BMT Amal Muslim

- **Prepaid:**
  > Assalamu'alaikum, Takmir Masjid {nama}. Kami informasikan token listrik
  > bulan {bulan} sebesar Rp{nominal} sudah kami belikan. Berikut kode
  > tokennya: {token}. Jazakumullahu khairan. - Baitul Maal BMT Amal Muslim

## UI

- Menu sidebar admin baru: **"Penyaluran Kelompok"** (ikon `bi-people-fill`
  atau serupa), ditempatkan berdekatan dengan menu Fundraising karena
  konsepnya paralel.
- Halaman list kelompok + tombol tambah kelompok (mirip `koleksi.html`).
- Halaman detail kelompok: kelola anggota (tambah dari `penerima_manfaat`
  yang sudah ada + set tipe, nonaktifkan anggota) + riwayat periode bulanan
  dengan progress bar (mirip `koleksi.html`).
- Halaman detail periode bulanan: tabel input nominal/token per anggota +
  tombol "Simpan & Kirim Notifikasi WA" + status kirim per baris setelah
  disimpan.

## Error Handling

- Gateway WA tidak terhubung / timeout → baris ditandai `wa_status='gagal'`,
  `wa_error` diisi pesan errornya, transaksi tetap tersimpan (pencatatan
  keuangan tidak boleh gagal hanya karena WA gagal kirim). Admin bisa retry
  kirim WA tanpa mengulang transaksi.
- Penerima tanpa `no_hp` terisi → baris otomatis `wa_status='gagal'` dengan
  keterangan "Nomor HP kosong", tanpa mencoba kirim.
- Buka periode dobel untuk bulan yang sama → diabaikan diam-diam per
  anggota (pola `try/except IntegrityError` sama seperti `koleksi_bulanan`),
  tidak menimpa data yang sudah diisi.

## Testing

- `smoke`/manual: buka periode → isi 2-3 baris dummy (1 postpaid, 1
  prepaid) → simpan & kirim → verifikasi transaksi masuk di halaman
  Transaksi dengan akun & nominal benar, dan verifikasi isi pesan WA yang
  terkirim (lewat gateway `/status` + log) sesuai template & placeholder
  terisi benar.
- Test buka-periode-dobel: pastikan tidak menimpa baris yang statusnya
  sudah `tersalur`.
- Test retry kirim WA: matikan gateway sementara, simpan periode (harus
  tetap sukses bikin transaksi, wa_status='gagal'), nyalakan gateway lagi,
  klik retry, pastikan terkirim tanpa transaksi dobel.

## Di Luar Cakupan (Tidak Dikerjakan Sekarang)

- Auto-buka-periode terjadwal (cron) — tetap manual dipicu admin.
- Integrasi API pembelian token PLN — token tetap diketik manual.
- Blast WA ke grup (fitur ini kirim ke nomor pribadi takmir satu-satu).
