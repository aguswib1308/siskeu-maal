# Penyaluran Kelompok + Notifikasi WA Takmir Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admin catat penyaluran bulanan ke sekelompok penerima tetap (mis. 40 masjid untuk Listrik Masjid) dengan sekali "buka periode" + isi nominal per baris, lalu otomatis kirim notifikasi WA (termasuk token untuk prepaid) ke tiap penerima.

**Architecture:** Tiga tabel baru mirror pola `koleksi_bulanan` yang sudah ada (kelompok tetap → anggota tetap → baris bulanan). Flask routes + Jinja templates mengikuti konvensi `bmt-maal/app.py` yang sudah ada (raw sqlite3, `admin_required`, redirect-after-POST, flash). Pengiriman WA lewat gateway Baileys baru (Node, kirim-saja) yang di-deploy terpisah di VPS, dipanggil dari Flask via HTTP kecil (`wa.py`).

**Tech Stack:** Python/Flask/sqlite3 (sisi app, sama seperti existing), Node.js/Baileys/Express (gateway WA baru, mirror `bmt-tagih-vps/wa-gateway/gateway.js`).

## Global Constraints

- Bahasa Indonesia untuk semua teks UI, komentar, dan pesan flash — ikuti konvensi proyek.
- **Tidak ada framework test di proyek ini** (tidak ada pytest, tidak ada `test_*.py` — cek `requirements.txt` & struktur folder). Verifikasi tiap task pakai perintah shell langsung (query sqlite3 / `python -c` self-check) atau cek manual via browser, BUKAN pytest. Ini penyimpangan sadar dari pola default skill ini, mengikuti konvensi proyek yang sudah ada (lihat `CLAUDE.md`: hanya `kandang_app` yang punya test suite).
- Reuse helper yang sudah ada — jangan tulis ulang: `insert_transaksi()` (app.py:35), `parse_jumlah()` (app.py:27), `get_tanggal_kerja()` (app.py:90), `format_bulan()` (app.py:175), `format_rupiah()` (app.py:120), `admin_required` (app.py:80), `get_db()` (app.py:20).
- Semua route baru pakai decorator `@admin_required` (fitur ini khusus admin, bukan marketing).
- Redirect setelah POST harus balik ke halaman yang masih masuk akal buat admin (pola `redirect(url_for(...))` yang sudah dipakai di seluruh `app.py`) — JANGAN redirect polos ke halaman lain yang menghilangkan konteks (pelajaran dari bug filter/scroll donatur yang baru saja diperbaiki).
- Gateway WA baru **terpisah** dari punya `bmt-tagih` (nomor WA beda, keputusan eksplisit user) — mirror pola kode `bmt-tagih-vps/wa-gateway/gateway.js`, folder & service baru, port baru (3004 — 3001/3002/3003 sudah dipakai proyek lain, dicek via `ss -ltnp` di VPS).
- File `bmt-maal/wa-gateway/.env` (token asli) **tidak boleh commit ke git** — hanya `.env.example` yang di-commit.

---

### Task 1: Skema database — tabel kelompok penyaluran

**Files:**
- Modify: `bmt-maal/init_db.py:227` (setelah `CREATE TABLE IF NOT EXISTS transaksi (...);`, sebelum `CREATE TABLE IF NOT EXISTS kategori`)

**Interfaces:**
- Consumes: tabel `chart_of_accounts(id)`, `penerima_manfaat(id)`, `transaksi(id)` — sudah ada.
- Produces: tabel `kelompok_penyaluran`, `kelompok_penyaluran_anggota`, `kelompok_penyaluran_bulanan` — dipakai semua task berikutnya.

- [ ] **Step 1: Tambah 3 CREATE TABLE baru**

Baca dulu `bmt-maal/init_db.py` sekitar baris 213-229 untuk memastikan anchor masih sama (tepat setelah penutup `transaksi (...)`, sebelum `kategori`). Sisipkan blok berikut persis di titik itu, di dalam `executescript` yang sama (jangan buka blok string baru):

```sql
        CREATE TABLE IF NOT EXISTS kelompok_penyaluran (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            coa_id INTEGER REFERENCES chart_of_accounts(id),
            pakai_token INTEGER DEFAULT 0,
            template_pesan TEXT,
            template_pesan_prepaid TEXT,
            aktif INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS kelompok_penyaluran_anggota (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kelompok_id INTEGER REFERENCES kelompok_penyaluran(id),
            penerima_id INTEGER REFERENCES penerima_manfaat(id),
            tipe TEXT CHECK(tipe IN ('postpaid','prepaid')),
            urutan INTEGER DEFAULT 0,
            aktif INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(kelompok_id, penerima_id)
        );

        CREATE TABLE IF NOT EXISTS kelompok_penyaluran_bulanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anggota_id INTEGER REFERENCES kelompok_penyaluran_anggota(id),
            bulan TEXT NOT NULL,
            jumlah REAL,
            token TEXT,
            status TEXT DEFAULT 'draft' CHECK(status IN ('draft','tersalur')),
            transaksi_id INTEGER REFERENCES transaksi(id),
            wa_status TEXT DEFAULT 'belum' CHECK(wa_status IN ('belum','terkirim','gagal')),
            wa_error TEXT,
            wa_sent_at TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(anggota_id, bulan)
        );
```

- [ ] **Step 2: Jalankan migrasi lokal**

Run: `cd bmt-maal && "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" init_db.py`
Expected: script selesai tanpa error (output normal seperti biasa, ada baris `Login admin : admin / admin123` di akhir).

- [ ] **Step 3: Verifikasi tabel & kolom**

Run:
```bash
"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" -c "
import sqlite3
conn = sqlite3.connect('bmt-maal/data/keuangan.db')
for t in ['kelompok_penyaluran','kelompok_penyaluran_anggota','kelompok_penyaluran_bulanan']:
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info({t})')]
    print(t, '->', cols)
"
```
Expected output (3 baris, satu per tabel), masing-masing daftar kolom sesuai definisi di atas — tidak boleh error "no such table".

- [ ] **Step 4: Commit**

```bash
cd bmt-maal
git add init_db.py
git commit -m "feat(maal): skema tabel kelompok penyaluran + anggota + bulanan

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Modul `wa.py` — client gateway WA

**Files:**
- Create: `bmt-maal/wa.py`
- Modify: `bmt-maal/requirements.txt` (tambah `requests`)

**Interfaces:**
- Consumes: env var `WA_GATEWAY_URL`, `WA_GATEWAY_TOKEN` (kosong = gateway belum dikonfigurasi, harus gagal dengan aman, bukan exception).
- Produces: `kirim_wa(no_hp: str, message: str) -> tuple[bool, str|None]`, `render_pesan(template: str, **kwargs) -> str` — dipakai Task 7.

- [ ] **Step 1: Tambah `requests` ke requirements.txt**

Isi `bmt-maal/requirements.txt` saat ini:
```
flask
gunicorn
pywebpush
py-vapid
```

Ubah jadi:
```
flask
gunicorn
pywebpush
py-vapid
requests
```

- [ ] **Step 2: Tulis `bmt-maal/wa.py`**

```python
"""Client HTTP kecil untuk gateway WA Baitul Maal (Baileys, kirim-saja).
Gateway-nya sendiri ada di folder terpisah `wa-gateway/` (Node.js) — lihat
docs/superpowers/specs/2026-09-03-penyaluran-kelompok-design.md.
"""
import os
import requests

WA_GATEWAY_URL = os.environ.get('WA_GATEWAY_URL', '').rstrip('/')
WA_GATEWAY_TOKEN = os.environ.get('WA_GATEWAY_TOKEN', '')


def kirim_wa(no_hp, message):
    """Kirim 1 pesan WA. Return (ok: bool, error: str|None).
    Gagal dengan aman (tidak raise) kalau gateway belum dikonfigurasi/mati —
    supaya penyaluran (transaksi) tetap tersimpan walau WA gagal kirim."""
    if not WA_GATEWAY_URL:
        return False, 'WA_GATEWAY_URL belum diset'
    if not no_hp:
        return False, 'Nomor HP kosong'
    try:
        r = requests.post(
            f'{WA_GATEWAY_URL}/send',
            json={'no_hp': no_hp, 'message': message},
            headers={'X-Bot-Token': WA_GATEWAY_TOKEN},
            timeout=15,
        )
        data = r.json()
        if data.get('status'):
            return True, None
        return False, data.get('reason', f'HTTP {r.status_code}')
    except requests.RequestException as e:
        return False, str(e)


def render_pesan(template, **kwargs):
    """Ganti placeholder {nama}/{bulan}/{nominal}/{token} di template pesan.
    Placeholder yang tidak dikirim di kwargs dibiarkan apa adanya (bukan
    error) — supaya template hasil edit admin tidak pernah bikin pengiriman
    gagal total gara-gara typo placeholder."""
    hasil = template or ''
    for key, val in kwargs.items():
        hasil = hasil.replace('{' + key + '}', str(val))
    return hasil


if __name__ == '__main__':
    # ponytail: self-check manual (proyek ini tidak pakai pytest) — jalankan
    # dengan `python wa.py`, harus print "OK" tanpa AssertionError.
    ok, err = kirim_wa('', 'test')
    assert ok is False and 'kosong' in err.lower() or 'WA_GATEWAY_URL' in err

    ok, err = kirim_wa('6281234567890', 'test')
    assert ok is False and err == 'WA_GATEWAY_URL belum diset'

    assert render_pesan('Halo {nama}', nama='Budi') == 'Halo Budi'
    assert render_pesan('Halo {nama}, {tidak_ada}', nama='Budi') == 'Halo Budi, {tidak_ada}'
    assert render_pesan(None) == ''

    print('OK')
```

- [ ] **Step 3: Install dependency & jalankan self-check**

Run:
```bash
cd bmt-maal
"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" -m pip install requests
"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" wa.py
```
Expected: output `OK`, tidak ada `AssertionError`/`Traceback`.

- [ ] **Step 4: Commit**

```bash
cd bmt-maal
git add wa.py requirements.txt
git commit -m "feat(maal): modul client gateway WA (kirim_wa, render_pesan)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Halaman daftar & tambah kelompok

**Files:**
- Modify: `bmt-maal/app.py` (tambah 2 route, dekat route `master_donatur*` sebagai referensi lokasi — taruh di section baru sebelum `# ── Master: Penerima Manfaat`)
- Create: `bmt-maal/templates/admin/kelompok.html`
- Modify: `bmt-maal/templates/admin/base.html:155` (tambah link sidebar)

**Interfaces:**
- Consumes: tabel `kelompok_penyaluran` (Task 1), `chart_of_accounts`.
- Produces: endpoint `kelompok_list` (`GET /admin/kelompok`), `kelompok_tambah` (`POST /admin/kelompok/tambah`); template `admin/kelompok.html`. Dipakai Task 4 (link "Lihat Detail").

- [ ] **Step 1: Tambah route di app.py**

Cari baris `# ── Master: Penerima Manfaat` (sekitar app.py:1868) dan sisipkan section baru **sebelum** baris itu:

```python
# ── Kelompok Penyaluran ───────────────────────────────────────────────────────

@app.route('/admin/kelompok')
@admin_required
def kelompok_list():
    conn = get_db()
    kelompok = conn.execute("""
        SELECT k.*, c.kode AS coa_kode, c.nama AS coa_nama,
               (SELECT COUNT(*) FROM kelompok_penyaluran_anggota a
                WHERE a.kelompok_id=k.id AND a.aktif=1) AS jml_anggota
        FROM kelompok_penyaluran k
        LEFT JOIN chart_of_accounts c ON k.coa_id=c.id
        ORDER BY k.nama
    """).fetchall()
    coa_list = conn.execute(
        "SELECT id, kode, nama FROM chart_of_accounts WHERE jenis_transaksi='keluar' AND aktif=1 ORDER BY kode"
    ).fetchall()
    conn.close()
    return render_template('admin/kelompok.html', kelompok=kelompok, coa_list=coa_list)

@app.route('/admin/kelompok/tambah', methods=['POST'])
@admin_required
def kelompok_tambah():
    data = request.form
    conn = get_db()
    conn.execute("""INSERT INTO kelompok_penyaluran
        (nama, coa_id, pakai_token, template_pesan, template_pesan_prepaid)
        VALUES (?,?,?,?,?)""",
        (data['nama'].strip(), int(data['coa_id']), 1 if data.get('pakai_token') else 0,
         data.get('template_pesan', '').strip(), data.get('template_pesan_prepaid', '').strip()))
    conn.commit(); conn.close()
    flash('Kelompok penyaluran berhasil dibuat.', 'success')
    return redirect(url_for('kelompok_list'))
```

- [ ] **Step 2: Buat template `admin/kelompok.html`**

```html
{% extends 'admin/base.html' %}
{% block title %}Kelompok Penyaluran{% endblock %}
{% block page_title %}<i class="bi bi-people-fill"></i> Kelompok Penyaluran{% endblock %}

{% block content %}
<div class="row mb-3">
  <div class="col-auto ms-auto">
    <button class="btn btn-sm btn-success" data-bs-toggle="modal" data-bs-target="#modalTambah">
      <i class="bi bi-plus-lg"></i> Kelompok Baru
    </button>
  </div>
</div>

<div class="card p-3">
  <div class="table-responsive">
    <table class="table table-hover table-sm align-middle">
      <thead class="table-light">
        <tr><th>Nama Kelompok</th><th>Akun CoA</th><th class="text-center">Anggota Aktif</th><th class="text-center">Token</th><th></th></tr>
      </thead>
      <tbody>
        {% for k in kelompok %}
        <tr>
          <td class="fw-semibold">{{ k.nama }}</td>
          <td class="small"><code class="me-1" style="font-size:.75rem">{{ k.coa_kode }}</code>{{ k.coa_nama }}</td>
          <td class="text-center">{{ k.jml_anggota }}</td>
          <td class="text-center">
            {% if k.pakai_token %}<span class="badge bg-info">Ya</span>{% else %}<span class="text-muted">—</span>{% endif %}
          </td>
          <td><a href="{{ url_for('kelompok_detail', id=k.id) }}" class="btn btn-sm btn-outline-primary py-0">Detail</a></td>
        </tr>
        {% else %}
        <tr><td colspan="5" class="text-center text-muted py-4">Belum ada kelompok penyaluran</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<div class="modal fade" id="modalTambah" tabindex="-1">
  <div class="modal-dialog modal-lg"><div class="modal-content">
    <form method="POST" action="{{ url_for('kelompok_tambah') }}">
      <div class="modal-header">
        <h6 class="modal-title fw-bold">Kelompok Penyaluran Baru</h6>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body row g-3">
        <div class="col-md-6">
          <label class="form-label fw-semibold">Nama Kelompok</label>
          <input type="text" name="nama" class="form-control" placeholder="cth: Listrik Masjid" required>
        </div>
        <div class="col-md-6">
          <label class="form-label fw-semibold">Akun CoA (tetap untuk semua anggota)</label>
          <select name="coa_id" class="form-select" required>
            <option value="">— Pilih Akun —</option>
            {% for c in coa_list %}
            <option value="{{ c.id }}">{{ c.kode }} — {{ c.nama }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="col-12">
          <div class="form-check">
            <input class="form-check-input" type="checkbox" name="pakai_token" value="1" id="pakaiToken" onchange="toggleTokenFields()">
            <label class="form-check-label small" for="pakaiToken">
              Kelompok ini punya anggota postpaid/prepaid (butuh field token)
            </label>
          </div>
        </div>
        <div class="col-12">
          <label class="form-label fw-semibold">Template Pesan WA <span id="labelDefault">(default)</span></label>
          <textarea name="template_pesan" class="form-control" rows="3"
            placeholder="Assalamu'alaikum, Takmir Masjid {nama}. Kami informasikan tagihan listrik bulan {bulan} sebesar Rp{nominal} telah kami bayarkan. Jazakumullahu khairan. - Baitul Maal BMT Amal Muslim"></textarea>
          <small class="text-muted">Placeholder: {nama}, {bulan}, {nominal}{% raw %}{% endraw %}{% if true %}{% endif %}</small>
        </div>
        <div class="col-12" id="wrapTemplatePrepaid" style="display:none">
          <label class="form-label fw-semibold">Template Pesan WA (khusus prepaid)</label>
          <textarea name="template_pesan_prepaid" class="form-control" rows="3"
            placeholder="Assalamu'alaikum, Takmir Masjid {nama}. Kami informasikan token listrik bulan {bulan} sebesar Rp{nominal} sudah kami belikan. Berikut kode tokennya: {token}. Jazakumullahu khairan. - Baitul Maal BMT Amal Muslim"></textarea>
          <small class="text-muted">Placeholder tambahan: {token}</small>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Batal</button>
        <button type="submit" class="btn btn-success btn-sm">Simpan</button>
      </div>
    </form>
  </div></div>
</div>
{% endblock %}

{% block scripts %}
<script>
function toggleTokenFields() {
  const on = document.getElementById('pakaiToken').checked;
  document.getElementById('wrapTemplatePrepaid').style.display = on ? '' : 'none';
  document.getElementById('labelDefault').textContent = on ? '(postpaid)' : '(default)';
}
</script>
{% endblock %}
```

Catatan: baris `<small>Placeholder: {nama}, {bulan}, {nominal}...</small>` di atas sengaja ditulis tanpa kurung kurawal Jinja aktif di sekitarnya (itu teks statis biasa, bukan ekspresi Jinja) — hapus fragmen `{% raw %}{% endraw %}{% if true %}{% endif %}` yang tidak perlu itu, cukup tulis:
```html
<small class="text-muted">Placeholder: {nama}, {bulan}, {nominal}</small>
```
(Kurung kurawal literal aman di Jinja selama tidak diawali `{{` atau `{%`.)

- [ ] **Step 3: Tambah link sidebar**

Di `bmt-maal/templates/admin/base.html`, cari blok ini (sekitar baris 153-155):

```html
    <a href="/admin/koleksi" class="nav-link {% if '/koleksi' in request.path %}active{% endif %}">
      <i class="bi bi-basket"></i> Fundraising
    </a>
```

Tambahkan tepat setelahnya:

```html
    <a href="/admin/kelompok" class="nav-link {% if '/kelompok' in request.path %}active{% endif %}">
      <i class="bi bi-people-fill"></i> Penyaluran Kelompok
    </a>
```

- [ ] **Step 4: Verifikasi manual di browser**

Jalankan dev server (`preview_start` dengan config `bmt-maal` dari `.claude/launch.json`), login admin, buka `/admin/kelompok` → harus tampil halaman kosong "Belum ada kelompok penyaluran" + tombol "Kelompok Baru" berfungsi (modal terbuka). Isi form (nama "Listrik Masjid", pilih akun CoA `5.5.6.01`, centang "pakai token", isi 2 template) → Simpan → harus redirect ke `/admin/kelompok` dan baris baru muncul di tabel dengan badge "Token: Ya".

Cek juga lewat DB langsung:
```bash
"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" -c "
import sqlite3
conn = sqlite3.connect('bmt-maal/data/keuangan.db')
print(conn.execute('SELECT id, nama, coa_id, pakai_token FROM kelompok_penyaluran').fetchall())
"
```
Expected: satu baris `(1, 'Listrik Masjid', <id_coa>, 1)`.

- [ ] **Step 5: Commit**

```bash
cd bmt-maal
git add app.py templates/admin/kelompok.html templates/admin/base.html
git commit -m "feat(maal): halaman daftar & tambah kelompok penyaluran

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Halaman detail kelompok — kelola anggota

**Files:**
- Modify: `bmt-maal/app.py` (tambah 3 route setelah route Task 3)
- Create: `bmt-maal/templates/admin/kelompok_detail.html`

**Interfaces:**
- Consumes: `kelompok_penyaluran_anggota` (Task 1), `penerima_manfaat` (existing), endpoint `kelompok_list` (Task 3, untuk link "kembali").
- Produces: endpoint `kelompok_detail` (`GET /admin/kelompok/<int:id>`), `kelompok_anggota_tambah` (`POST .../anggota/tambah`), `kelompok_anggota_toggle` (`POST .../anggota/<int:anggota_id>/toggle`); template `admin/kelompok_detail.html` — akan ditambahi section "Periode" oleh Task 5 di file yang sama.

- [ ] **Step 1: Tambah route di app.py**

Tambahkan setelah `kelompok_tambah` (akhir Task 3):

```python
@app.route('/admin/kelompok/<int:id>')
@admin_required
def kelompok_detail(id):
    conn = get_db()
    kelompok = conn.execute("""
        SELECT k.*, c.kode AS coa_kode, c.nama AS coa_nama
        FROM kelompok_penyaluran k LEFT JOIN chart_of_accounts c ON k.coa_id=c.id
        WHERE k.id=?
    """, (id,)).fetchone()
    if not kelompok:
        conn.close()
        flash('Kelompok tidak ditemukan.', 'danger')
        return redirect(url_for('kelompok_list'))
    anggota = conn.execute("""
        SELECT a.*, p.nama AS penerima_nama, p.no_hp, p.alamat
        FROM kelompok_penyaluran_anggota a JOIN penerima_manfaat p ON a.penerima_id=p.id
        WHERE a.kelompok_id=? ORDER BY a.urutan, p.nama
    """, (id,)).fetchall()
    penerima_tersedia = conn.execute("""
        SELECT id, nama FROM penerima_manfaat
        WHERE aktif=1 AND id NOT IN
            (SELECT penerima_id FROM kelompok_penyaluran_anggota WHERE kelompok_id=?)
        ORDER BY nama
    """, (id,)).fetchall()
    conn.close()
    return render_template('admin/kelompok_detail.html', kelompok=kelompok, anggota=anggota,
                            penerima_tersedia=penerima_tersedia, periode=[],
                            bulan_ini=date.today().strftime('%Y-%m'))

@app.route('/admin/kelompok/<int:id>/anggota/tambah', methods=['POST'])
@admin_required
def kelompok_anggota_tambah(id):
    data = request.form
    conn = get_db()
    try:
        conn.execute("""INSERT INTO kelompok_penyaluran_anggota (kelompok_id, penerima_id, tipe)
            VALUES (?,?,?)""", (id, int(data['penerima_id']), data.get('tipe') or None))
        conn.commit()
        flash('Anggota ditambahkan ke kelompok.', 'success')
    except sqlite3.IntegrityError:
        flash('Penerima ini sudah jadi anggota kelompok.', 'warning')
    conn.close()
    return redirect(url_for('kelompok_detail', id=id))

@app.route('/admin/kelompok/<int:id>/anggota/<int:anggota_id>/toggle', methods=['POST'])
@admin_required
def kelompok_anggota_toggle(id, anggota_id):
    conn = get_db()
    conn.execute("""UPDATE kelompok_penyaluran_anggota SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END
        WHERE id=? AND kelompok_id=?""", (anggota_id, id))
    conn.commit(); conn.close()
    return redirect(url_for('kelompok_detail', id=id))
```

Catatan: `kelompok_detail` mengirim `periode=[]` (placeholder kosong) — Task 5 akan mengganti baris ini dengan query riwayat periode sungguhan. Ini bukan pelanggaran "no placeholder" plan (kode Python-nya lengkap & jalan), hanya nilai sementara yang secara eksplisit ditimpa Task 5.

- [ ] **Step 2: Buat template `admin/kelompok_detail.html`**

```html
{% extends 'admin/base.html' %}
{% block title %}{{ kelompok.nama }}{% endblock %}
{% block page_title %}<i class="bi bi-people-fill"></i> {{ kelompok.nama }}{% endblock %}

{% block content %}
<a href="{{ url_for('kelompok_list') }}" class="btn btn-sm btn-outline-secondary mb-3">
  <i class="bi bi-arrow-left"></i> Kembali ke Daftar Kelompok
</a>

<div class="card p-3 mb-4">
  <div class="row g-2 small">
    <div class="col-md-4"><span class="text-muted">Akun CoA:</span> <code>{{ kelompok.coa_kode }}</code> {{ kelompok.coa_nama }}</div>
    <div class="col-md-4"><span class="text-muted">Pakai Token:</span> {% if kelompok.pakai_token %}Ya{% else %}Tidak{% endif %}</div>
    <div class="col-md-4"><span class="text-muted">Anggota Aktif:</span> {{ anggota|selectattr('aktif')|list|length }}</div>
  </div>
</div>

<div class="row g-4">
  <div class="col-lg-7">
    <div class="card p-3">
      <div class="fw-semibold mb-3">Anggota Kelompok</div>
      <div class="table-responsive">
        <table class="table table-hover table-sm align-middle">
          <thead class="table-light">
            <tr><th>Nama</th><th>No HP</th>{% if kelompok.pakai_token %}<th>Tipe</th>{% endif %}<th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {% for a in anggota %}
            <tr class="{% if not a.aktif %}table-secondary text-muted{% endif %}">
              <td class="small">{{ a.penerima_nama }}</td>
              <td class="small">{{ a.no_hp or '—' }}</td>
              {% if kelompok.pakai_token %}
              <td class="small">
                {% if a.tipe=='prepaid' %}<span class="badge bg-warning text-dark">Prepaid</span>
                {% elif a.tipe=='postpaid' %}<span class="badge bg-secondary">Postpaid</span>
                {% else %}—{% endif %}
              </td>
              {% endif %}
              <td><span class="badge {% if a.aktif %}bg-success{% else %}bg-secondary{% endif %}">{% if a.aktif %}Aktif{% else %}Nonaktif{% endif %}</span></td>
              <td>
                <form method="POST" action="{{ url_for('kelompok_anggota_toggle', id=kelompok.id, anggota_id=a.id) }}">
                  <button class="btn btn-sm btn-outline-{% if a.aktif %}warning{% else %}success{% endif %} py-0">
                    {% if a.aktif %}Nonaktifkan{% else %}Aktifkan{% endif %}
                  </button>
                </form>
              </td>
            </tr>
            {% else %}
            <tr><td colspan="{% if kelompok.pakai_token %}5{% else %}4{% endif %}" class="text-center text-muted py-3">Belum ada anggota</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <hr>
      <div class="fw-semibold mb-2 small">Tambah Anggota</div>
      <form method="POST" action="{{ url_for('kelompok_anggota_tambah', id=kelompok.id) }}" class="d-flex gap-2 flex-wrap">
        <select name="penerima_id" class="form-select form-select-sm" style="width:220px" required>
          <option value="">— Pilih Penerima —</option>
          {% for p in penerima_tersedia %}
          <option value="{{ p.id }}">{{ p.nama }}</option>
          {% endfor %}
        </select>
        {% if kelompok.pakai_token %}
        <select name="tipe" class="form-select form-select-sm" style="width:140px" required>
          <option value="">— Tipe —</option>
          <option value="postpaid">Postpaid</option>
          <option value="prepaid">Prepaid</option>
        </select>
        {% endif %}
        <button class="btn btn-sm btn-success">Tambah</button>
      </form>
      <small class="text-muted d-block mt-2">
        Penerima belum ada di daftar? Tambahkan dulu lewat
        <a href="{{ url_for('master_penerima') }}">Master Penerima Manfaat</a> (bisa import Excel massal).
      </small>
    </div>
  </div>

  <div class="col-lg-5">
    <div class="card p-3 mb-3">
      <div class="fw-semibold mb-3">Buka Periode Baru</div>
      <form method="POST" action="{{ url_for('kelompok_buka_periode', id=kelompok.id) }}" class="d-flex gap-2 align-items-end">
        <div>
          <label class="form-label fw-semibold small">Bulan</label>
          <input type="month" name="bulan" value="{{ bulan_ini }}" class="form-control" required>
        </div>
        <button type="submit" class="btn btn-success">
          <i class="bi bi-play-circle"></i> Buka Periode
        </button>
      </form>
    </div>

    <div class="card p-3">
      <div class="fw-semibold mb-3">Riwayat Periode</div>
      {% if periode %}
      <div class="table-responsive">
        <table class="table table-hover table-sm align-middle">
          <thead class="table-light"><tr><th>Bulan</th><th class="text-center">Tersalur</th><th class="text-end">Nominal</th><th></th></tr></thead>
          <tbody>
            {% for p in periode %}
            <tr>
              <td class="fw-semibold">{{ p.bulan|bulan_label }}</td>
              <td class="text-center">{{ p.tersalur }}/{{ p.total }}</td>
              <td class="text-end">{{ (p.total_nominal or 0)|rupiah }}</td>
              <td><a href="{{ url_for('kelompok_bulanan_detail', id=kelompok.id, bulan=p.bulan) }}" class="btn btn-sm btn-outline-primary py-0">Detail</a></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% else %}
      <div class="text-center text-muted py-3">Belum ada periode dibuka.</div>
      {% endif %}
    </div>
  </div>
</div>
{% endblock %}
```

Catatan: form "Buka Periode" & tabel "Riwayat Periode" di atas memanggil endpoint `kelompok_buka_periode` dan `kelompok_bulanan_detail` yang **baru dibuat di Task 5** — halaman ini akan error `BuildError` kalau dibuka sebelum Task 5 selesai. Itu wajar untuk task ini (anggota-management sudah bisa diuji lewat bagian atas halaman); Step 3 di bawah hanya menguji bagian anggota, bukan bagian periode.

- [ ] **Step 3: Verifikasi manual (bagian anggota saja)**

Karena `kelompok_buka_periode`/`kelompok_bulanan_detail` belum ada, buka `/admin/kelompok/1` akan **gagal** dengan `werkzeug.routing.BuildError` di bagian "Buka Periode"/"Riwayat Periode". Ini **diharapkan** — lanjutkan ke Task 5 dulu sebelum verifikasi penuh di browser. Untuk memastikan route & query anggota sendiri benar tanpa render halaman penuh, cek lewat shell:

```bash
"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" -c "
import sqlite3
conn = sqlite3.connect('bmt-maal/data/keuangan.db')
conn.row_factory = sqlite3.Row
kelompok = conn.execute('SELECT * FROM kelompok_penyaluran WHERE id=1').fetchone()
print('kelompok:', dict(kelompok) if kelompok else None)
anggota = conn.execute('SELECT a.*, p.nama FROM kelompok_penyaluran_anggota a JOIN penerima_manfaat p ON a.penerima_id=p.id WHERE a.kelompok_id=1').fetchall()
print('anggota:', [dict(r) for r in anggota])
"
```
Expected: `kelompok` bukan `None` (baris yang dibuat di Task 3), `anggota` list kosong `[]` (belum ada anggota ditambahkan lewat UI — itu wajar di titik ini, uji lengkap-nya dilakukan setelah Task 5 saat halaman bisa dibuka utuh).

- [ ] **Step 4: Commit**

```bash
cd bmt-maal
git add app.py templates/admin/kelompok_detail.html
git commit -m "feat(maal): kelola anggota kelompok penyaluran

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Buka periode + halaman detail periode bulanan

**Files:**
- Modify: `bmt-maal/app.py` (tambah 2 route + ganti `periode=[]` jadi query sungguhan di `kelompok_detail`)
- Create: `bmt-maal/templates/admin/kelompok_bulanan.html`

**Interfaces:**
- Consumes: `kelompok_penyaluran_bulanan` (Task 1), route `kelompok_detail` (Task 4, field `periode` diisi sungguhan di sini).
- Produces: endpoint `kelompok_buka_periode` (`POST /admin/kelompok/<int:id>/buka`), `kelompok_bulanan_detail` (`GET /admin/kelompok/<int:id>/<bulan>`); template `admin/kelompok_bulanan.html` — akan ditambahi tombol Simpan oleh Task 6.

- [ ] **Step 1: Ganti `periode=[]` di `kelompok_detail` dengan query sungguhan**

Di `app.py`, dalam fungsi `kelompok_detail` (Task 4), ganti baris:

```python
    conn.close()
    return render_template('admin/kelompok_detail.html', kelompok=kelompok, anggota=anggota,
                            penerima_tersedia=penerima_tersedia, periode=[],
                            bulan_ini=date.today().strftime('%Y-%m'))
```

menjadi:

```python
    periode = conn.execute("""
        SELECT b.bulan,
               COUNT(*) AS total,
               SUM(CASE WHEN b.status='tersalur' THEN 1 ELSE 0 END) AS tersalur,
               SUM(b.jumlah) AS total_nominal
        FROM kelompok_penyaluran_bulanan b
        JOIN kelompok_penyaluran_anggota a ON b.anggota_id=a.id
        WHERE a.kelompok_id=?
        GROUP BY b.bulan ORDER BY b.bulan DESC
    """, (id,)).fetchall()
    conn.close()
    return render_template('admin/kelompok_detail.html', kelompok=kelompok, anggota=anggota,
                            penerima_tersedia=penerima_tersedia, periode=periode,
                            bulan_ini=date.today().strftime('%Y-%m'))
```

- [ ] **Step 2: Tambah route `kelompok_buka_periode` & `kelompok_bulanan_detail`**

Tambahkan setelah `kelompok_anggota_toggle` (akhir Task 4):

```python
@app.route('/admin/kelompok/<int:id>/buka', methods=['POST'])
@admin_required
def kelompok_buka_periode(id):
    bulan = request.form.get('bulan', '').strip()
    if not bulan:
        flash('Bulan wajib diisi.', 'danger')
        return redirect(url_for('kelompok_detail', id=id))
    conn = get_db()
    anggota = conn.execute(
        "SELECT id FROM kelompok_penyaluran_anggota WHERE kelompok_id=? AND aktif=1", (id,)
    ).fetchall()
    created = 0
    for a in anggota:
        prefill = conn.execute("""
            SELECT jumlah FROM kelompok_penyaluran_bulanan
            WHERE anggota_id=? AND bulan < ? ORDER BY bulan DESC LIMIT 1
        """, (a['id'], bulan)).fetchone()
        try:
            conn.execute("""INSERT INTO kelompok_penyaluran_bulanan (anggota_id, bulan, jumlah)
                VALUES (?,?,?)""", (a['id'], bulan, prefill['jumlah'] if prefill else None))
            created += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit(); conn.close()
    flash(f'Periode {bulan} dibuka, {created} baris dibuat.', 'success')
    return redirect(url_for('kelompok_bulanan_detail', id=id, bulan=bulan))

@app.route('/admin/kelompok/<int:id>/<bulan>')
@admin_required
def kelompok_bulanan_detail(id, bulan):
    conn = get_db()
    kelompok = conn.execute("SELECT * FROM kelompok_penyaluran WHERE id=?", (id,)).fetchone()
    if not kelompok:
        conn.close()
        flash('Kelompok tidak ditemukan.', 'danger')
        return redirect(url_for('kelompok_list'))
    baris = conn.execute("""
        SELECT b.*, p.nama AS penerima_nama, p.no_hp, a.tipe
        FROM kelompok_penyaluran_bulanan b
        JOIN kelompok_penyaluran_anggota a ON b.anggota_id=a.id
        JOIN penerima_manfaat p ON a.penerima_id=p.id
        WHERE a.kelompok_id=? AND b.bulan=?
        ORDER BY a.urutan, p.nama
    """, (id, bulan)).fetchall()
    conn.close()
    return render_template('admin/kelompok_bulanan.html', kelompok=kelompok, bulan=bulan, baris=baris)
```

- [ ] **Step 3: Buat template `admin/kelompok_bulanan.html`**

```html
{% extends 'admin/base.html' %}
{% block title %}{{ kelompok.nama }} — {{ bulan|bulan_label }}{% endblock %}
{% block page_title %}<i class="bi bi-people-fill"></i> {{ kelompok.nama }} — {{ bulan|bulan_label }}{% endblock %}

{% block content %}
<a href="{{ url_for('kelompok_detail', id=kelompok.id) }}" class="btn btn-sm btn-outline-secondary mb-3">
  <i class="bi bi-arrow-left"></i> Kembali ke {{ kelompok.nama }}
</a>

<form method="POST" action="{{ url_for('kelompok_bulanan_simpan', id=kelompok.id, bulan=bulan) }}">
<div class="card p-3">
  <div class="table-responsive">
    <table class="table table-hover table-sm align-middle">
      <thead class="table-light">
        <tr>
          <th>Penerima</th><th>No HP</th>{% if kelompok.pakai_token %}<th>Tipe</th>{% endif %}
          <th style="width:160px">Nominal</th>
          {% if kelompok.pakai_token %}<th style="width:180px">Token (kalau prepaid)</th>{% endif %}
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {% for b in baris %}
        <tr>
          <td class="small">{{ b.penerima_nama }}</td>
          <td class="small">{{ b.no_hp or '—' }}</td>
          {% if kelompok.pakai_token %}
          <td class="small">
            {% if b.tipe=='prepaid' %}<span class="badge bg-warning text-dark">Prepaid</span>
            {% elif b.tipe=='postpaid' %}<span class="badge bg-secondary">Postpaid</span>
            {% else %}—{% endif %}
          </td>
          {% endif %}
          <td>
            <input type="text" name="jumlah_{{ b.id }}" class="form-control form-control-sm"
                   value="{{ b.jumlah|int if b.jumlah else '' }}" placeholder="0">
          </td>
          {% if kelompok.pakai_token %}
          <td>
            {% if b.tipe=='prepaid' %}
            <input type="text" name="token_{{ b.id }}" class="form-control form-control-sm" value="{{ b.token or '' }}">
            {% else %}—{% endif %}
          </td>
          {% endif %}
          <td>
            <span class="badge {% if b.status=='tersalur' %}bg-success{% else %}bg-secondary{% endif %}">
              {% if b.status=='tersalur' %}Tersalur{% else %}Draft{% endif %}
            </span>
          </td>
        </tr>
        {% else %}
        <tr><td colspan="6" class="text-center text-muted py-4">Belum ada baris — buka periode dulu dari halaman kelompok.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% if baris %}
  <button type="submit" class="btn btn-success mt-2">
    <i class="bi bi-check2-circle"></i> Simpan Semua
  </button>
  {% endif %}
</div>
</form>
{% endblock %}
```

Catatan: tombol submit di atas memanggil endpoint `kelompok_bulanan_simpan` yang **baru dibuat di Task 6** — sama seperti Task 4, halaman ini akan `BuildError` sampai Task 6 selesai. Verifikasi Step 4 di bawah cuma menguji buka-periode & render tabel, bukan submit-nya.

- [ ] **Step 4: Verifikasi manual — buka periode**

Di browser: buka `/admin/kelompok/1`, isi form "Buka Periode" dengan bulan berjalan → submit. Karena template `kelompok_bulanan.html` memanggil endpoint yang belum ada, halaman hasil redirect akan **error 500** (`BuildError: kelompok_bulanan_simpan`) — itu diharapkan di titik ini. Verifikasi lewat DB langsung bahwa baris memang ter-generate:

```bash
"C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe" -c "
import sqlite3
conn = sqlite3.connect('bmt-maal/data/keuangan.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('''SELECT b.id, b.bulan, b.jumlah, b.status, p.nama
    FROM kelompok_penyaluran_bulanan b
    JOIN kelompok_penyaluran_anggota a ON b.anggota_id=a.id
    JOIN penerima_manfaat p ON a.penerima_id=p.id''').fetchall()
print([dict(r) for r in rows])
"
```
Expected: satu baris per anggota aktif kelompok, `status='draft'`, `jumlah=None` (belum ada histori bulan sebelumnya utk prefill).

Uji juga **buka-periode-dobel**: submit form "Buka Periode" sekali lagi untuk bulan yang sama → jalankan ulang query di atas → jumlah baris (`len(rows)`) harus **tetap sama**, tidak dobel (constraint `UNIQUE(anggota_id, bulan)` menjaga ini).

- [ ] **Step 5: Commit**

```bash
cd bmt-maal
git add app.py templates/admin/kelompok_bulanan.html
git commit -m "feat(maal): buka periode bulanan + halaman detail periode

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Simpan periode → buat transaksi keluar

**Files:**
- Modify: `bmt-maal/app.py` (tambah 1 route)

**Interfaces:**
- Consumes: `insert_transaksi()` (app.py:35), `parse_jumlah()` (app.py:27), `get_tanggal_kerja()` (app.py:90), `format_bulan()` (app.py:175), route `kelompok_bulanan_detail` (Task 5, redirect target).
- Produces: endpoint `kelompok_bulanan_simpan` (`POST /admin/kelompok/<int:id>/<bulan>/simpan`) — melengkapi `BuildError` dari Task 5.

- [ ] **Step 1: Tambah route `kelompok_bulanan_simpan`**

Tambahkan setelah `kelompok_bulanan_detail` (akhir Task 5):

```python
@app.route('/admin/kelompok/<int:id>/<bulan>/simpan', methods=['POST'])
@admin_required
def kelompok_bulanan_simpan(id, bulan):
    conn = get_db()
    kelompok = conn.execute("SELECT * FROM kelompok_penyaluran WHERE id=?", (id,)).fetchone()
    if not kelompok:
        conn.close()
        flash('Kelompok tidak ditemukan.', 'danger')
        return redirect(url_for('kelompok_list'))
    baris = conn.execute("""
        SELECT b.id, b.status, b.transaksi_id, a.penerima_id
        FROM kelompok_penyaluran_bulanan b
        JOIN kelompok_penyaluran_anggota a ON b.anggota_id=a.id
        WHERE a.kelompok_id=? AND b.bulan=?
    """, (id, bulan)).fetchall()
    tanggal = get_tanggal_kerja()
    disimpan = 0
    for b in baris:
        jumlah = parse_jumlah(request.form.get(f'jumlah_{b["id"]}'))
        token = request.form.get(f'token_{b["id"]}', '').strip()
        if jumlah is None:
            continue
        if b['status'] == 'tersalur' and b['transaksi_id']:
            # Sudah pernah disimpan (mis. koreksi nominal) — update transaksi
            # yang ada, jangan bikin baris baru supaya buku besar tidak dobel.
            conn.execute("UPDATE transaksi SET jumlah=? WHERE id=?", (jumlah, b['transaksi_id']))
            trx_id = b['transaksi_id']
        else:
            trx_id, _ = insert_transaksi(
                conn, tanggal, 'keluar', kelompok['coa_id'], None, b['penerima_id'], jumlah,
                f"Penyaluran {kelompok['nama']} – {format_bulan(bulan)}", session['user_id'],
            )
        conn.execute("""UPDATE kelompok_penyaluran_bulanan
            SET jumlah=?, token=?, status='tersalur', transaksi_id=? WHERE id=?""",
            (jumlah, token or None, trx_id, b['id']))
        disimpan += 1
    conn.commit(); conn.close()
    flash(f'{disimpan} penyaluran disimpan.', 'success')
    return redirect(url_for('kelompok_bulanan_detail', id=id, bulan=bulan))
```

- [ ] **Step 2: Verifikasi manual end-to-end (tanpa WA dulu)**

Di browser: buka periode yang sudah dibuat di Task 5 Step 4 (`/admin/kelompok/1/<bulan-berjalan>`), isi nominal untuk 2-3 baris (mis. 150000, 200000), klik "Simpan Semua" → harus redirect balik ke halaman yang sama, flash "N penyaluran disimpan.", dan baris yang diisi sekarang berstatus badge "Tersalur" dengan nilai nominal tersimpan di kolom input.

Cek transaksi benar-benar tercatat — buka `/admin/transaksi`, cari baris dengan keterangan "Penyaluran Listrik Masjid – ..." dan pastikan kolom Jenis=`keluar`, Akun sesuai CoA yang dipilih, Jumlah sesuai yang diinput, Donatur/Penerima = nama masjid yang diisi.

Uji **koreksi tanpa dobel**: ubah salah satu nominal yang sudah "Tersalur" (mis. dari 150000 jadi 175000) lalu Simpan Semua lagi → cek `/admin/transaksi`, jumlah transaksi untuk masjid itu harus **tetap 1 baris** dengan nominal ter-update ke 175000 (bukan 2 baris terpisah).

- [ ] **Step 3: Commit**

```bash
cd bmt-maal
git add app.py
git commit -m "feat(maal): simpan periode kelompok -> transaksi keluar (blm kirim WA)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Kirim notifikasi WA + retry per baris

**Files:**
- Modify: `bmt-maal/app.py` (import `wa`, `time`; tambah helper `kirim_notifikasi_penyaluran`; ubah `kelompok_bulanan_simpan`; tambah route retry)
- Modify: `bmt-maal/templates/admin/kelompok_bulanan.html` (kolom status WA + tombol kirim ulang)

**Interfaces:**
- Consumes: `kirim_wa()`, `render_pesan()` (Task 2, `wa.py`), `format_rupiah()` (app.py:120), `format_bulan()` (app.py:175), route `kelompok_bulanan_simpan` (Task 6, dimodifikasi).
- Produces: helper `kirim_notifikasi_penyaluran(conn, bulanan_id)`; endpoint `kelompok_bulanan_kirim_ulang` (`POST /admin/kelompok/bulanan/<int:bulanan_id>/kirim-ulang`).

- [ ] **Step 1: Tambah import**

Di baris import paling atas `app.py` (baris 2), ubah:
```python
import sqlite3, hashlib, os, re, json, calendar as cal_mod, io, shutil, glob as glob_mod
```
menjadi:
```python
import sqlite3, hashlib, os, re, json, calendar as cal_mod, io, shutil, glob as glob_mod, time
```

Tambahkan setelah baris `import laz_pusat_report` (baris 8):
```python
from wa import kirim_wa, render_pesan
```

- [ ] **Step 2: Tambah helper `kirim_notifikasi_penyaluran`**

Tambahkan tepat sebelum route `kelompok_bulanan_simpan` (yang ditulis di Task 6):

```python
def kirim_notifikasi_penyaluran(conn, bulanan_id):
    """Kirim WA notifikasi utk 1 baris kelompok_penyaluran_bulanan, lalu update
    status kirimnya di DB (tidak commit — caller yang commit)."""
    row = conn.execute("""
        SELECT b.id, b.jumlah, b.token, b.bulan, p.nama AS penerima_nama, p.no_hp, a.tipe,
               k.pakai_token, k.template_pesan, k.template_pesan_prepaid
        FROM kelompok_penyaluran_bulanan b
        JOIN kelompok_penyaluran_anggota a ON b.anggota_id=a.id
        JOIN penerima_manfaat p ON a.penerima_id=p.id
        JOIN kelompok_penyaluran k ON a.kelompok_id=k.id
        WHERE b.id=?
    """, (bulanan_id,)).fetchone()
    if not row:
        return
    if not row['no_hp']:
        conn.execute("UPDATE kelompok_penyaluran_bulanan SET wa_status='gagal', wa_error=? WHERE id=?",
                     ('Nomor HP kosong', bulanan_id))
        return
    template = row['template_pesan']
    if row['pakai_token'] and row['tipe'] == 'prepaid':
        template = row['template_pesan_prepaid']
    pesan = render_pesan(template or '', nama=row['penerima_nama'], bulan=format_bulan(row['bulan']),
                          nominal=format_rupiah(row['jumlah']), token=row['token'] or '')
    ok, error = kirim_wa(row['no_hp'], pesan)
    if ok:
        conn.execute("""UPDATE kelompok_penyaluran_bulanan
            SET wa_status='terkirim', wa_error=NULL, wa_sent_at=datetime('now','localtime') WHERE id=?""",
            (bulanan_id,))
    else:
        conn.execute("UPDATE kelompok_penyaluran_bulanan SET wa_status='gagal', wa_error=? WHERE id=?",
                     (error, bulanan_id))
```

- [ ] **Step 3: Wire ke `kelompok_bulanan_simpan` + tambah route retry**

Di route `kelompok_bulanan_simpan` (Task 6), ubah blok ini:
```python
        conn.execute("""UPDATE kelompok_penyaluran_bulanan
            SET jumlah=?, token=?, status='tersalur', transaksi_id=? WHERE id=?""",
            (jumlah, token or None, trx_id, b['id']))
        disimpan += 1
    conn.commit(); conn.close()
```
menjadi:
```python
        conn.execute("""UPDATE kelompok_penyaluran_bulanan
            SET jumlah=?, token=?, status='tersalur', transaksi_id=? WHERE id=?""",
            (jumlah, token or None, trx_id, b['id']))
        disimpan += 1
        # ponytail: kirim WA sinkron dalam request (blocking ~1-2 detik x jumlah
        # anggota) — aman utk skala saat ini (~40 anggota/bulan, sekali sebulan).
        # Kalau kelompok makin besar/banyak, pindah ke background job sebelum
        # request ini menabrak timeout gunicorn (lihat Task 9: timeout dinaikkan
        # ke 180s sbg jaring pengaman, bukan solusi permanen).
        kirim_notifikasi_penyaluran(conn, b['id'])
        time.sleep(1)
    conn.commit(); conn.close()
```

Lalu tambahkan route baru setelah `kelompok_bulanan_simpan`:

```python
@app.route('/admin/kelompok/bulanan/<int:bulanan_id>/kirim-ulang', methods=['POST'])
@admin_required
def kelompok_bulanan_kirim_ulang(bulanan_id):
    conn = get_db()
    row = conn.execute("""
        SELECT b.bulan, a.kelompok_id FROM kelompok_penyaluran_bulanan b
        JOIN kelompok_penyaluran_anggota a ON b.anggota_id=a.id
        WHERE b.id=?
    """, (bulanan_id,)).fetchone()
    if not row:
        conn.close()
        flash('Data tidak ditemukan.', 'danger')
        return redirect(url_for('kelompok_list'))
    kirim_notifikasi_penyaluran(conn, bulanan_id)
    conn.commit(); conn.close()
    return redirect(url_for('kelompok_bulanan_detail', id=row['kelompok_id'], bulan=row['bulan']))
```

- [ ] **Step 4: Tambah kolom status WA & tombol kirim ulang di template**

Di `bmt-maal/templates/admin/kelompok_bulanan.html`, ubah baris header tabel:
```html
        <tr>
          <th>Penerima</th><th>No HP</th>{% if kelompok.pakai_token %}<th>Tipe</th>{% endif %}
          <th style="width:160px">Nominal</th>
          {% if kelompok.pakai_token %}<th style="width:180px">Token (kalau prepaid)</th>{% endif %}
          <th>Status</th>
        </tr>
```
menjadi:
```html
        <tr>
          <th>Penerima</th><th>No HP</th>{% if kelompok.pakai_token %}<th>Tipe</th>{% endif %}
          <th style="width:160px">Nominal</th>
          {% if kelompok.pakai_token %}<th style="width:180px">Token (kalau prepaid)</th>{% endif %}
          <th>Status</th><th>WA</th>
        </tr>
```

Dan ubah sel `<td>` terakhir tiap baris:
```html
          <td>
            <span class="badge {% if b.status=='tersalur' %}bg-success{% else %}bg-secondary{% endif %}">
              {% if b.status=='tersalur' %}Tersalur{% else %}Draft{% endif %}
            </span>
          </td>
        </tr>
```
menjadi:
```html
          <td>
            <span class="badge {% if b.status=='tersalur' %}bg-success{% else %}bg-secondary{% endif %}">
              {% if b.status=='tersalur' %}Tersalur{% else %}Draft{% endif %}
            </span>
          </td>
          <td class="small">
            {% if b.wa_status=='terkirim' %}
              <span class="badge bg-success">Terkirim</span>
            {% elif b.wa_status=='gagal' %}
              <span class="badge bg-danger" title="{{ b.wa_error }}">Gagal</span>
              <form method="POST" action="{{ url_for('kelompok_bulanan_kirim_ulang', bulanan_id=b.id) }}" class="d-inline">
                <button class="btn btn-sm btn-outline-danger py-0 px-1" title="{{ b.wa_error }}">
                  <i class="bi bi-arrow-clockwise"></i>
                </button>
              </form>
            {% else %}
              <span class="text-muted">—</span>
            {% endif %}
          </td>
        </tr>
```

Ubah juga colspan pada baris kosong `{% else %}` dari `colspan="6"` jadi `colspan="7"`.

Terakhir, ganti label tombol submit dari "Simpan Semua" jadi "Simpan & Kirim Notifikasi WA":
```html
  <button type="submit" class="btn btn-success mt-2">
    <i class="bi bi-check2-circle"></i> Simpan & Kirim Notifikasi WA
  </button>
```

- [ ] **Step 5: Verifikasi manual (gateway belum ada — harus gagal dengan aman)**

Pastikan env `WA_GATEWAY_URL` **tidak diset** di lingkungan dev lokal (default kosong). Di browser: buka periode baru / edit nominal baris yang sudah ada di `/admin/kelompok/1/<bulan>`, klik "Simpan & Kirim Notifikasi WA" → harus **tetap sukses menyimpan transaksi** (cek `/admin/transaksi` seperti Task 6 Step 2), dan kolom "WA" tiap baris yang diisi menunjukkan badge merah "Gagal" (hover/title menampilkan "WA_GATEWAY_URL belum diset"). Klik tombol retry (ikon panah) pada satu baris → tetap "Gagal" dengan alasan yang sama (belum ada gateway) — ini **perilaku yang benar** untuk tahap ini, membuktikan alur retry jalan tanpa meng-crash halaman.

- [ ] **Step 6: Commit**

```bash
cd bmt-maal
git add app.py templates/admin/kelompok_bulanan.html
git commit -m "feat(maal): kirim notifikasi WA saat simpan periode + retry per baris

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Gateway WA baru (Node/Baileys) — file lokal

**Files:**
- Create: `bmt-maal/wa-gateway/gateway.js`
- Create: `bmt-maal/wa-gateway/package.json`
- Create: `bmt-maal/wa-gateway/.env.example`
- Modify: `bmt-maal/.gitignore` (abaikan `wa-gateway/.env`, `wa-gateway/auth_info_baileys/`, `wa-gateway/node_modules/`)

**Interfaces:**
- Consumes: pola referensi `bmt-tagih-vps/wa-gateway/gateway.js` (repo lain, hanya dibaca sebagai contoh — tidak ada dependency kode).
- Produces: HTTP API `POST /send {no_hp, message}` (header `X-Bot-Token`) → `{status: true}` / `{status: false, reason}`; `GET /status`; `GET /qr` — dikonsumsi `wa.py` (Task 2) lewat `WA_GATEWAY_URL`.

- [ ] **Step 1: Buat `bmt-maal/wa-gateway/package.json`**

```json
{
  "name": "bmt-maal-wa-gateway",
  "version": "1.0.0",
  "description": "Gateway WA kirim-pesan-saja (Baileys) khusus notifikasi penyaluran Baitul Maal",
  "main": "gateway.js",
  "scripts": {
    "start": "node gateway.js"
  },
  "dependencies": {
    "@hapi/boom": "^10.0.1",
    "@whiskeysockets/baileys": "^6.7.18",
    "dotenv": "^17.4.2",
    "express": "^4.18.2",
    "pino": "^9.5.0",
    "qrcode": "^1.5.4",
    "qrcode-terminal": "^0.12.0"
  }
}
```

- [ ] **Step 2: Buat `bmt-maal/wa-gateway/.env.example`**

```
# Konfigurasi WA gateway Baitul Maal — salin ke .env lalu isi nilainya
# (jangan commit .env ke git; chmod 600 di VPS)

# Port HTTP server (default 3004 — 3001/3002/3003 sudah dipakai proyek lain)
WA_GATEWAY_PORT=3004

# Token auth — bmt-maal (wa.py) harus kirim header X-Bot-Token: <nilai ini>
# Isi string acak yang kuat, mis: openssl rand -hex 20
WA_GATEWAY_TOKEN=isi_token_rahasia_disini
```

- [ ] **Step 3: Buat `bmt-maal/wa-gateway/gateway.js`**

```javascript
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
```

- [ ] **Step 4: Tambah `.gitignore` untuk folder gateway**

Buka `bmt-maal/.gitignore`, tambahkan baris:
```
wa-gateway/.env
wa-gateway/node_modules/
wa-gateway/auth_info_baileys/
```

- [ ] **Step 5: Verifikasi sintaks lokal**

Node tidak wajib terpasang di PC lokal untuk task ini (instalasi dependency & run sungguhan terjadi di VPS pada Task 9, sama seperti pola `bmt-tagih-vps/wa-gateway`). Kalau `node` tersedia di lokal, cek cepat:
```bash
node --check "bmt-maal/wa-gateway/gateway.js"
```
Expected: tidak ada output (artinya sintaks valid). Kalau `node` tidak terpasang di PC lokal, lewati step ini — verifikasi sintaks akan tetap dilakukan di VPS sebagai bagian Task 9 Step 2 sebelum service dijalankan.

- [ ] **Step 6: Commit**

```bash
cd bmt-maal
git add wa-gateway/gateway.js wa-gateway/package.json wa-gateway/.env.example .gitignore
git commit -m "feat(maal): gateway WA baru (Baileys) khusus notifikasi penyaluran

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: Deploy ke VPS + sambungkan gateway ke bmt-maal

**Files:**
- VPS: `/var/www/bmt-maal/` (pull dari git)
- VPS: buat baru `/etc/systemd/system/bmt-maal-wa-gateway.service`
- VPS: modify `/etc/systemd/system/bmt-maal.service` (tambah 2 env var, naikkan `--timeout`)

**Interfaces:**
- Consumes: seluruh Task 1-8 (kode sudah di-push ke `origin/master` lewat commit tiap task sebelumnya).
- Produces: fitur hidup di `maal.bmtamalmuslim.web.id`; service `bmt-maal-wa-gateway` aktif di port 3004.

**Prasyarat non-kode (di luar kendali Claude):** perlu **nomor WhatsApp baru** khusus Baitul Maal (SIM + HP yang bisa dipakai scan QR sekali). Siapkan ini sebelum Step 4 di bawah — tanpa ini, Step 4 (scan QR) tidak bisa dilakukan dan gateway akan tetap `ready:false` (fitur tetap jalan mencatat transaksi, hanya WA yang gagal terkirim, sama seperti behavior Task 7 Step 5).

- [ ] **Step 1: Push semua commit Task 1-8 ke GitHub**

```bash
cd bmt-maal
git push
```
Expected: `master -> master` sukses, tidak ada conflict (kalau ada, `git fetch` dulu dan selesaikan sebelum lanjut — jangan force push).

- [ ] **Step 2: Pull kode ke VPS + install dependency Python**

```bash
ssh root@103.169.207.190 "cd /var/www/bmt-maal && git pull && venv/bin/pip install -r requirements.txt -q"
```
Expected: `git pull` menunjukkan commit-commit baru masuk (fast-forward), `pip install` selesai tanpa error (menambahkan `requests`).

- [ ] **Step 3: Migrasi skema DB produksi**

```bash
ssh root@103.169.207.190 "cd /var/www/bmt-maal && sudo -u www-data venv/bin/python init_db.py"
```
Expected: selesai tanpa error. Verifikasi tabel baru ada di DB produksi:
```bash
ssh root@103.169.207.190 "cd /var/www/bmt-maal && sqlite3 data/keuangan.db '.tables' | tr -s ' ' '\n' | grep kelompok"
```
Expected output (3 baris): `kelompok_penyaluran`, `kelompok_penyaluran_anggota`, `kelompok_penyaluran_bulanan`.

- [ ] **Step 4: Install & jalankan gateway WA di VPS**

```bash
ssh root@103.169.207.190 "cd /var/www/bmt-maal/wa-gateway && npm install && node --check gateway.js && echo SYNTAX_OK"
```
Expected: `npm install` selesai (mengunduh Baileys dkk — bisa 1-2 menit), diakhiri `SYNTAX_OK`.

```bash
ssh root@103.169.207.190 "cd /var/www/bmt-maal/wa-gateway && cp .env.example .env && sed -i \"s/isi_token_rahasia_disini/\$(openssl rand -hex 20)/\" .env && chmod 600 .env && cat .env"
```
Expected: isi `.env` tampil dengan `WA_GATEWAY_PORT=3004` dan `WA_GATEWAY_TOKEN=<64 karakter hex>` — **catat token ini**, dipakai Step 6.

Buat service:
```bash
ssh root@103.169.207.190 "cat > /etc/systemd/system/bmt-maal-wa-gateway.service <<'EOF'
[Unit]
Description=Gateway WA kirim-pesan-saja untuk notifikasi penyaluran Baitul Maal
After=network.target

[Service]
WorkingDirectory=/var/www/bmt-maal/wa-gateway
EnvironmentFile=/var/www/bmt-maal/wa-gateway/.env
ExecStart=/usr/bin/node gateway.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now bmt-maal-wa-gateway
systemctl status bmt-maal-wa-gateway --no-pager"
```
Expected: `Active: active (running)`.

- [ ] **Step 5: Scan QR (butuh HP dengan nomor WA baru Baitul Maal)**

Buka tunnel dari PC lokal ke VPS (port 3004 tidak dibuka ke publik):
```bash
ssh -L 3004:127.0.0.1:3004 root@103.169.207.190
```
Di tab terminal lain (biarkan tunnel di atas tetap jalan), buka `http://localhost:3004/qr` di browser lokal → scan pakai WhatsApp di HP nomor Baitul Maal yang baru (titik tiga → Perangkat Tertaut → Tautkan Perangkat). Tunggu sampai halaman bilang "sudah terhubung ✅", atau cek:
```bash
ssh root@103.169.207.190 "journalctl -u bmt-maal-wa-gateway -n 20 --no-pager"
```
Expected: ada baris `Gateway WA siap dan terhubung.`.

- [ ] **Step 6: Sambungkan env ke service `bmt-maal` + naikkan timeout**

```bash
ssh root@103.169.207.190 "cp /etc/systemd/system/bmt-maal.service /etc/systemd/system/bmt-maal.service.bak.$(date +%Y%m%d%H%M%S)"
```

Edit `/etc/systemd/system/bmt-maal.service` (pakai `nano`/`vi` di VPS, atau `sed`) sehingga blok `[Service]` jadi:
```ini
[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/bmt-maal
Environment="SECRET_KEY=MaalBmt@2026!"
Environment="LAPORAN_API_KEY=99421807f3bb66d95d0b64f6034e5d899889049f"
Environment="WA_GATEWAY_URL=http://127.0.0.1:3004"
Environment="WA_GATEWAY_TOKEN=<token dari Step 4>"
ExecStart=/var/www/bmt-maal/venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:5002 \
    --timeout 180 \
    --access-logfile /var/log/bmt-maal/access.log \
    --error-logfile /var/log/bmt-maal/error.log \
    app:app
Restart=always
RestartSec=5
```

(Perubahan dari sebelumnya: 2 baris `Environment=` baru, dan `--timeout 60` → `--timeout 180` — jaring pengaman utk blast ~40 kirim WA sinkron per Task 7.)

```bash
ssh root@103.169.207.190 "systemctl daemon-reload && systemctl restart bmt-maal && sleep 2 && systemctl is-active bmt-maal"
```
Expected: `active`.

- [ ] **Step 7: Uji end-to-end di produksi**

Login admin di `https://maal.bmtamalmuslim.web.id`, buka menu "Penyaluran Kelompok" → buat kelompok test kecil (1-2 anggota, pakai nomor HP milik sendiri utk uji) → buka periode → isi nominal → "Simpan & Kirim Notifikasi WA" → pastikan:
1. Transaksi keluar tercatat di halaman Transaksi.
2. WA benar-benar masuk ke HP penguji, isi pesan sesuai template dengan placeholder terisi benar (nama, bulan, nominal, token kalau prepaid).
3. Kolom "WA" di tabel menunjukkan badge hijau "Terkirim".

Cek log gateway kalau ada yang aneh:
```bash
ssh root@103.169.207.190 "journalctl -u bmt-maal-wa-gateway -n 30 --no-pager"
```

Setelah uji selesai, hapus kelompok test (langsung lewat sqlite kalau belum ada UI hapus kelompok — di luar cakupan spec ini) supaya tidak mengganggu data produksi:
```bash
ssh root@103.169.207.190 "cd /var/www/bmt-maal && sqlite3 data/keuangan.db \"DELETE FROM kelompok_penyaluran_bulanan WHERE anggota_id IN (SELECT id FROM kelompok_penyaluran_anggota WHERE kelompok_id=(SELECT id FROM kelompok_penyaluran WHERE nama='<nama kelompok test>')); DELETE FROM kelompok_penyaluran_anggota WHERE kelompok_id=(SELECT id FROM kelompok_penyaluran WHERE nama='<nama kelompok test>'); DELETE FROM kelompok_penyaluran WHERE nama='<nama kelompok test>';\""
```

- [ ] **Step 8: Tidak ada commit di step ini** (perubahan sistemd unit file & `.env` di VPS bukan bagian dari repo git, sengaja tidak di-commit — sudah tercatat manual di plan ini sebagai dokumentasi).

**Rollback kalau ada masalah setelah Step 6/7:**
```bash
ssh root@103.169.207.190 "cp /etc/systemd/system/bmt-maal.service.bak.<timestamp dari Step 6> /etc/systemd/system/bmt-maal.service && systemctl daemon-reload && systemctl restart bmt-maal"
```
Fitur "Penyaluran Kelompok" di kode tetap ada (tidak perlu revert git) — ini cuma mematikan pengiriman WA (`WA_GATEWAY_URL` hilang lagi → `kirim_wa()` gagal dengan aman seperti di Task 7 Step 5, transaksi tetap tercatat normal). Kalau gateway-nya sendiri yang bermasalah (bukan config bmt-maal): `systemctl stop bmt-maal-wa-gateway` — efeknya sama, WA gagal terkirim tapi pencatatan tetap jalan.

---

## Ringkasan Urutan

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. Task 1-7 bisa diuji penuh secara lokal tanpa gateway WA (Task 7 sengaja diverifikasi dalam mode "gateway belum ada" supaya kegagalan WA tidak pernah menghalangi pencatatan transaksi). Task 8-9 baru menyalakan pengiriman WA sungguhan, dan Task 9 Step 5 butuh tindakan fisik user (scan QR pakai HP nomor baru).
