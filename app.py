from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
import sqlite3, hashlib, os, re, json, calendar as cal_mod, io
from datetime import datetime, date
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from functools import wraps

app = Flask(__name__)
app.secret_key = 'BmtMaal@2026!'
DB_PATH = os.path.join('data', 'keuangan.db')

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return redirect(url_for('marketing_dashboard'))
        return f(*args, **kwargs)
    return decorated

def format_rupiah(angka):
    try:
        return f"Rp {int(angka):,}".replace(',', '.')
    except (TypeError, ValueError):
        return "Rp 0"

app.jinja_env.filters['rupiah'] = format_rupiah

LABEL_DANA  = {'zakat':'Zakat','infak_sedekah':'Infak/Sedekah','amil':'Amil','wakaf':'Wakaf','umum':'Umum'}
LABEL_ASNAF = {'fakir':'Fakir','miskin':'Miskin','amil':'Amil','muallaf':'Muallaf',
               'riqab':'Riqab','gharim':'Gharim','fisabilillah':'Fisabilillah','ibnu_sabil':'Ibnu Sabil'}
LABEL_SUMBER = {'tunai':'Tunai','kencleng':'Kencleng','kotak_infaq':'Kotak Infaq'}
BULAN_IND   = {1:'Januari',2:'Februari',3:'Maret',4:'April',5:'Mei',6:'Juni',
               7:'Juli',8:'Agustus',9:'September',10:'Oktober',11:'November',12:'Desember'}

def format_bulan(b):
    try:
        y, m = b.split('-')
        return f"{BULAN_IND[int(m)]} {y}"
    except:
        return b

app.jinja_env.filters['bulan_label'] = format_bulan
app.jinja_env.globals.update(LABEL_DANA=LABEL_DANA, LABEL_ASNAF=LABEL_ASNAF,
                              LABEL_SUMBER=LABEL_SUMBER)

def parse_gmaps_url(url):
    """Ekstrak (lat, lng) dari berbagai format URL Google Maps."""
    patterns = [
        r'@(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)',
        r'[?&]ll=(-?\d+\.\d+),(-?\d+\.\d+)',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None

def buka_periode(bulan, user_id):
    """Generate koleksi_bulanan untuk semua donatur aktif bulan tsb."""
    conn = get_db()
    donatur = conn.execute(
        "SELECT id FROM donatur WHERE sumber_infaq IN ('kencleng','kotak_infaq') "
        "AND aktif_infaq=1 AND aktif=1"
    ).fetchall()
    created = 0
    for d in donatur:
        try:
            conn.execute("INSERT INTO koleksi_bulanan (donatur_id, bulan) VALUES (?,?)",
                         (d['id'], bulan))
            created += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return created

def auto_koleksi_donatur_baru(conn, donatur_id, sumber_infaq):
    """Buat koleksi_bulanan bulan ini untuk donatur baru kencleng/kotak_infaq."""
    if sumber_infaq in ('kencleng', 'kotak_infaq'):
        bulan = date.today().strftime('%Y-%m')
        try:
            conn.execute("INSERT INTO koleksi_bulanan (donatur_id, bulan) VALUES (?,?)",
                         (donatur_id, bulan))
        except:
            pass

def get_instansi(conn=None):
    close = False
    if conn is None:
        conn = get_db(); close = True
    row = conn.execute("SELECT * FROM instansi WHERE id=1").fetchone()
    if close: conn.close()
    if row:
        return dict(row)
    return {'nama': 'BAITUL MAAL BMT', 'nama_lembaga': '', 'alamat': '', 'telepon': '',
            'email': '', 'website': '', 'ketua': '', 'bendahara': '', 'sekretaris': '',
            'no_izin': ''}

def auto_transaksi_koleksi(conn, koleksi_id, donatur_id, bulan, sumber, jumlah, tanggal, user_id):
    """Buat transaksi otomatis saat koleksi terkumpul."""
    coa = conn.execute("SELECT id FROM chart_of_accounts WHERE kode='4.2.2'").fetchone()
    keterangan = f"Koleksi {LABEL_SUMBER.get(sumber, sumber)} – {bulan}"
    cur = conn.execute("""
        INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,donatur_id,jumlah,keterangan,user_id)
        VALUES (?,?,?,?,?,?,?,?)
    """, (tanggal, 'masuk', 'infak_sedekah', coa['id'] if coa else None,
          donatur_id, jumlah, keterangan, user_id))
    trx_id = cur.lastrowid
    conn.execute("UPDATE koleksi_bulanan SET transaksi_id=? WHERE id=?", (trx_id, koleksi_id))
    return trx_id

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard') if session['role']=='admin' else url_for('marketing_dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND aktif=1",
            (username, hash_pw(password))
        ).fetchone()
        conn.close()
        if user:
            session.update({'user_id':user['id'],'username':user['username'],
                            'nama':user['nama'],'role':user['role']})
            return redirect(url_for('admin_dashboard') if user['role']=='admin' else url_for('marketing_dashboard'))
        error = 'Username atau password salah.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Admin Dashboard ───────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    total_masuk  = conn.execute("SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE jenis='masuk' AND strftime('%Y-%m',tanggal)=?", (bulan,)).fetchone()[0]
    total_keluar = conn.execute("SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE jenis='keluar' AND strftime('%Y-%m',tanggal)=?", (bulan,)).fetchone()[0]
    saldo = conn.execute("SELECT COALESCE(SUM(CASE WHEN jenis='masuk' THEN jumlah ELSE -jumlah END),0) FROM transaksi").fetchone()[0]
    transaksi_terakhir = conn.execute('''
        SELECT t.*, c.nama as coa_nama, c.jenis_dana, d.nama as donatur_nama, u.nama as petugas
        FROM transaksi t
        LEFT JOIN chart_of_accounts c ON t.coa_id=c.id
        LEFT JOIN donatur d ON t.donatur_id=d.id
        LEFT JOIN users u ON t.user_id=u.id
        ORDER BY t.created_at DESC LIMIT 10
    ''').fetchall()
    rekap_dana = conn.execute('''
        SELECT jenis_dana, jenis, SUM(jumlah) as total FROM transaksi
        WHERE strftime('%Y-%m',tanggal)=? AND jenis_dana IS NOT NULL
        GROUP BY jenis_dana, jenis ORDER BY jenis_dana
    ''', (bulan,)).fetchall()
    conn.close()
    return render_template('admin/dashboard.html', total_masuk=total_masuk,
        total_keluar=total_keluar, saldo=saldo, transaksi_terakhir=transaksi_terakhir,
        rekap_dana=rekap_dana, bulan=bulan)

# ── Admin Transaksi ───────────────────────────────────────────────────────────

@app.route('/admin/transaksi')
@admin_required
def admin_transaksi():
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    jenis = request.args.get('jenis', '')
    jenis_dana = request.args.get('jenis_dana', '')
    query = '''
        SELECT t.*, c.nama as coa_nama, c.kode as coa_kode, c.jenis_dana,
               d.nama as donatur_nama, p.nama as penerima_nama, u.nama as petugas
        FROM transaksi t
        LEFT JOIN chart_of_accounts c ON t.coa_id=c.id
        LEFT JOIN donatur d ON t.donatur_id=d.id
        LEFT JOIN penerima_manfaat p ON t.penerima_id=p.id
        LEFT JOIN users u ON t.user_id=u.id
        WHERE strftime('%Y-%m',t.tanggal)=?'''
    params = [bulan]
    if jenis in ('masuk','keluar'):
        query += ' AND t.jenis=?'; params.append(jenis)
    if jenis_dana:
        query += ' AND t.jenis_dana=?'; params.append(jenis_dana)
    query += ' ORDER BY t.tanggal DESC, t.created_at DESC'
    transaksi   = conn.execute(query, params).fetchall()
    coa_list    = conn.execute("SELECT * FROM chart_of_accounts WHERE jenis_transaksi IS NOT NULL AND aktif=1 ORDER BY kode").fetchall()
    coa_parents = conn.execute(
        "SELECT * FROM chart_of_accounts WHERE parent_kode IS NOT NULL AND aktif=1 ORDER BY kode"
    ).fetchall()
    donatur_list= conn.execute("SELECT * FROM donatur WHERE aktif=1 ORDER BY nama").fetchall()
    penerima_list=conn.execute("SELECT * FROM penerima_manfaat WHERE aktif=1 ORDER BY nama").fetchall()
    conn.close()
    return render_template('admin/transaksi.html', transaksi=transaksi, coa_list=coa_list,
        coa_parents=coa_parents, donatur_list=donatur_list, penerima_list=penerima_list,
        bulan=bulan, jenis=jenis, jenis_dana=jenis_dana)

@app.route('/admin/transaksi/tambah', methods=['POST'])
@admin_required
def tambah_transaksi():
    data = request.form
    conn = get_db()
    coa_id = data.get('coa_id') or None
    jenis_dana = None
    if coa_id:
        row = conn.execute("SELECT jenis_dana FROM chart_of_accounts WHERE id=?", (coa_id,)).fetchone()
        if row: jenis_dana = row['jenis_dana']
    conn.execute('''INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,donatur_id,penerima_id,jumlah,keterangan,user_id)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (data['tanggal'], data['jenis'], jenis_dana, coa_id,
         data.get('donatur_id') or None, data.get('penerima_id') or None,
         float(data['jumlah'].replace('.','').replace(',','')),
         data.get('keterangan',''), session['user_id']))
    conn.commit(); conn.close()
    flash('Transaksi berhasil dicatat.', 'success')
    return redirect(url_for('admin_transaksi'))

@app.route('/admin/transaksi/hapus/<int:id>', methods=['POST'])
@admin_required
def hapus_transaksi(id):
    conn = get_db()
    conn.execute("DELETE FROM transaksi WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Transaksi dihapus.', 'warning')
    return redirect(url_for('admin_transaksi'))

# ── Admin Laporan ─────────────────────────────────────────────────────────────

@app.route('/admin/laporan')
@admin_required
def admin_laporan():
    return render_template('admin/laporan.html')


def _last_day(bulan):
    y, m = map(int, bulan.split('-'))
    return f"{bulan}-{cal_mod.monthrange(y, m)[1]:02d}"

def _prev_last_day(bulan):
    y, m = map(int, bulan.split('-'))
    if m == 1: py, pm = y-1, 12
    else:      py, pm = y,   m-1
    return f"{py}-{pm:02d}-{cal_mod.monthrange(py, pm)[1]:02d}"

def _dana_summary(conn, bulan):
    """Hitung saldo awal, penerimaan, penyaluran, saldo akhir per jenis dana."""
    dana_types = ['zakat', 'infak_sedekah', 'amil', 'wakaf']

    rows_awal = conn.execute("""
        SELECT jenis_dana,
               COALESCE(SUM(CASE WHEN jenis='masuk' THEN jumlah ELSE -jumlah END),0) as saldo
        FROM transaksi WHERE strftime('%Y-%m',tanggal) < ? AND jenis_dana IS NOT NULL
        GROUP BY jenis_dana
    """, (bulan,)).fetchall()
    saldo_awal = {r['jenis_dana']: r['saldo'] for r in rows_awal}

    masuk_rows = conn.execute("""
        SELECT c.kode, c.nama, c.jenis_dana, c.parent_kode, SUM(t.jumlah) as total
        FROM transaksi t JOIN chart_of_accounts c ON t.coa_id=c.id
        WHERE t.jenis='masuk' AND strftime('%Y-%m',t.tanggal)=?
        GROUP BY c.id ORDER BY c.kode
    """, (bulan,)).fetchall()

    keluar_rows = conn.execute("""
        SELECT c.kode, c.nama, c.jenis_dana, c.parent_kode, SUM(t.jumlah) as total
        FROM transaksi t JOIN chart_of_accounts c ON t.coa_id=c.id
        WHERE t.jenis='keluar' AND strftime('%Y-%m',t.tanggal)=?
        GROUP BY c.id ORDER BY c.kode
    """, (bulan,)).fetchall()

    data = {}
    for dana in dana_types:
        masuk  = [r for r in masuk_rows  if r['jenis_dana'] == dana]
        keluar = [r for r in keluar_rows if r['jenis_dana'] == dana]
        tm = sum(r['total'] for r in masuk)
        tk = sum(r['total'] for r in keluar)
        sa = saldo_awal.get(dana, 0)
        data[dana] = {
            'masuk': masuk, 'keluar': keluar,
            'total_masuk': tm, 'total_keluar': tk,
            'saldo_awal': sa, 'saldo_akhir': sa + tm - tk,
        }
    return data


@app.route('/admin/laporan/neraca')
@admin_required
def laporan_neraca():
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    ld    = _last_day(bulan)
    conn  = get_db()

    rows = conn.execute("""
        SELECT jenis_dana,
               COALESCE(SUM(CASE WHEN jenis='masuk' THEN jumlah ELSE -jumlah END),0) as saldo
        FROM transaksi WHERE tanggal <= ? AND jenis_dana IS NOT NULL
        GROUP BY jenis_dana
    """, (ld,)).fetchall()
    kas = {r['jenis_dana']: r['saldo'] for r in rows}

    dana_types = ['zakat', 'infak_sedekah', 'amil', 'wakaf']
    total_aset = sum(kas.get(d, 0) for d in dana_types)
    inst = get_instansi(conn)
    conn.close()
    return render_template('admin/laporan_neraca.html',
        kas=kas, dana_types=dana_types, total_aset=total_aset,
        bulan=bulan, last_day=ld, inst=inst)


@app.route('/admin/laporan/dana')
@admin_required
def laporan_dana():
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    conn  = get_db()
    data  = _dana_summary(conn, bulan)
    inst  = get_instansi(conn)
    conn.close()
    return render_template('admin/laporan_dana.html',
        data=data, bulan=bulan, inst=inst,
        dana_types=['zakat', 'infak_sedekah', 'amil', 'wakaf'])


@app.route('/admin/laporan/arus-kas')
@admin_required
def laporan_arus_kas():
    bulan    = request.args.get('bulan', date.today().strftime('%Y-%m'))
    prev_ld  = _prev_last_day(bulan)
    conn     = get_db()

    saldo_awal = conn.execute("""
        SELECT COALESCE(SUM(CASE WHEN jenis='masuk' THEN jumlah ELSE -jumlah END),0)
        FROM transaksi WHERE tanggal <= ?
    """, (prev_ld,)).fetchone()[0]

    masuk = conn.execute("""
        SELECT c.kode, c.nama, c.jenis_dana, SUM(t.jumlah) as total
        FROM transaksi t JOIN chart_of_accounts c ON t.coa_id=c.id
        WHERE t.jenis='masuk' AND strftime('%Y-%m',t.tanggal)=?
        GROUP BY c.id ORDER BY c.kode
    """, (bulan,)).fetchall()

    keluar = conn.execute("""
        SELECT c.kode, c.nama, c.jenis_dana, SUM(t.jumlah) as total
        FROM transaksi t JOIN chart_of_accounts c ON t.coa_id=c.id
        WHERE t.jenis='keluar' AND strftime('%Y-%m',t.tanggal)=?
        GROUP BY c.id ORDER BY c.kode
    """, (bulan,)).fetchall()

    total_masuk  = sum(r['total'] for r in masuk)
    total_keluar = sum(r['total'] for r in keluar)
    conn.close()

    inst = get_instansi()
    return render_template('admin/laporan_arus_kas.html',
        masuk=masuk, keluar=keluar,
        total_masuk=total_masuk, total_keluar=total_keluar,
        saldo_awal=saldo_awal, saldo_akhir=saldo_awal + total_masuk - total_keluar,
        bulan=bulan, inst=inst)

# ── Admin Koleksi ─────────────────────────────────────────────────────────────

@app.route('/admin/koleksi')
@admin_required
def admin_koleksi():
    conn = get_db()
    periode = conn.execute('''
        SELECT bulan,
               COUNT(*) as total,
               SUM(CASE WHEN status='terkumpul' THEN 1 ELSE 0 END) as terkumpul,
               SUM(CASE WHEN status='tidak_ada' THEN 1 ELSE 0 END) as tidak_ada,
               SUM(CASE WHEN status='terjadwal' THEN 1 ELSE 0 END) as terjadwal,
               COALESCE(SUM(CASE WHEN status='terkumpul' THEN jumlah ELSE 0 END),0) as total_nominal
        FROM koleksi_bulanan GROUP BY bulan ORDER BY bulan DESC
    ''').fetchall()
    total_donatur = conn.execute(
        "SELECT COUNT(*) FROM donatur WHERE sumber_infaq IN ('kencleng','kotak_infaq') AND aktif_infaq=1 AND aktif=1"
    ).fetchone()[0]
    conn.close()
    return render_template('admin/koleksi.html', periode=periode,
        total_donatur=total_donatur, bulan_ini=date.today().strftime('%Y-%m'))

@app.route('/admin/koleksi/buka', methods=['POST'])
@admin_required
def admin_koleksi_buka():
    bulan = request.form.get('bulan', date.today().strftime('%Y-%m'))
    created = buka_periode(bulan, session['user_id'])
    if created:
        flash(f'Periode {bulan} dibuka: {created} record koleksi dibuat.', 'success')
    else:
        flash(f'Periode {bulan} sudah ada atau tidak ada donatur aktif.', 'warning')
    return redirect(url_for('admin_koleksi'))

@app.route('/admin/koleksi/<bulan>')
@admin_required
def admin_koleksi_detail(bulan):
    conn = get_db()
    status_filter = request.args.get('status', '')
    area_filter   = request.args.get('area', '')
    query = '''
        SELECT kb.*, d.nama as donatur_nama, d.sumber_infaq, d.area, d.lokasi_nama,
               d.lat, d.lng, u.nama as marketing_nama,
               uk.nama as kunjungi_nama
        FROM koleksi_bulanan kb
        JOIN donatur d ON kb.donatur_id=d.id
        LEFT JOIN users u ON kb.marketing_id=u.id
        LEFT JOIN users uk ON kb.marketing_kunjungi_terakhir=uk.id
        WHERE kb.bulan=?'''
    params = [bulan]
    if status_filter:
        query += ' AND kb.status=?'; params.append(status_filter)
    if area_filter:
        query += ' AND d.area=?'; params.append(area_filter)
    query += ' ORDER BY d.area, d.nama'
    koleksi = conn.execute(query, params).fetchall()
    areas   = conn.execute(
        "SELECT DISTINCT d.area FROM koleksi_bulanan kb JOIN donatur d ON kb.donatur_id=d.id "
        "WHERE kb.bulan=? AND d.area IS NOT NULL ORDER BY d.area", (bulan,)
    ).fetchall()
    stats = conn.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status='terkumpul' THEN 1 ELSE 0 END) as terkumpul,
               SUM(CASE WHEN status='tidak_ada' THEN 1 ELSE 0 END) as tidak_ada,
               SUM(CASE WHEN status='terjadwal' THEN 1 ELSE 0 END) as terjadwal,
               COALESCE(SUM(CASE WHEN status='terkumpul' THEN jumlah ELSE 0 END),0) as total_nominal
        FROM koleksi_bulanan WHERE bulan=?
    ''', (bulan,)).fetchone()
    conn.close()
    return render_template('admin/koleksi_detail.html', koleksi=koleksi,
        bulan=bulan, stats=stats, areas=areas,
        status_filter=status_filter, area_filter=area_filter)

@app.route('/admin/koleksi/capaian')
@admin_required
def admin_koleksi_capaian():
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    capaian = conn.execute('''
        SELECT u.nama, u.username,
               COUNT(*) as jumlah_koleksi,
               COALESCE(SUM(kb.jumlah),0) as total_nominal,
               SUM(CASE WHEN d.sumber_infaq='kencleng' THEN 1 ELSE 0 END) as kencleng,
               SUM(CASE WHEN d.sumber_infaq='kotak_infaq' THEN 1 ELSE 0 END) as kotak
        FROM koleksi_bulanan kb
        JOIN users u ON kb.marketing_id=u.id
        JOIN donatur d ON kb.donatur_id=d.id
        WHERE kb.bulan=? AND kb.status='terkumpul'
        GROUP BY u.id ORDER BY total_nominal DESC
    ''', (bulan,)).fetchall()
    conn.close()
    return render_template('admin/koleksi_capaian.html', capaian=capaian, bulan=bulan)

# ── Admin Peta ────────────────────────────────────────────────────────────────

@app.route('/admin/peta')
@admin_required
def admin_peta():
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    donatur = conn.execute('''
        SELECT d.id, d.nama, d.sumber_infaq, d.area, d.lokasi_nama, d.lat, d.lng,
               kb.status as koleksi_status, kb.jumlah as koleksi_jumlah
        FROM donatur d
        LEFT JOIN koleksi_bulanan kb ON kb.donatur_id=d.id AND kb.bulan=?
        WHERE d.sumber_infaq IN ('kencleng','kotak_infaq') AND d.aktif=1
              AND d.lat IS NOT NULL AND d.lng IS NOT NULL
        ORDER BY d.area, d.nama
    ''', (bulan,)).fetchall()
    donatur_json = json.dumps([dict(d) for d in donatur])
    conn.close()
    return render_template('admin/peta.html', donatur_json=donatur_json, bulan=bulan)

# ── Master: Users ─────────────────────────────────────────────────────────────

@app.route('/admin/master/users')
@admin_required
def master_users():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY role, nama").fetchall()
    conn.close()
    return render_template('admin/master/users.html', users=users)

@app.route('/admin/master/users/tambah', methods=['POST'])
@admin_required
def master_users_tambah():
    data = request.form
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username,password,nama,role,no_hp) VALUES (?,?,?,?,?)",
                     (data['username'], hash_pw(data['password']), data['nama'],
                      data['role'], data.get('no_hp','')))
        conn.commit(); flash('User berhasil ditambahkan.', 'success')
    except sqlite3.IntegrityError:
        flash('Username sudah dipakai.', 'danger')
    conn.close()
    return redirect(url_for('master_users'))

@app.route('/admin/master/users/edit/<int:id>', methods=['POST'])
@admin_required
def master_users_edit(id):
    data = request.form
    conn = get_db()
    if data.get('password'):
        conn.execute("UPDATE users SET nama=?,role=?,no_hp=?,password=? WHERE id=?",
                     (data['nama'],data['role'],data.get('no_hp',''),hash_pw(data['password']),id))
    else:
        conn.execute("UPDATE users SET nama=?,role=?,no_hp=? WHERE id=?",
                     (data['nama'],data['role'],data.get('no_hp',''),id))
    conn.commit(); conn.close()
    flash('User diperbarui.', 'success')
    return redirect(url_for('master_users'))

@app.route('/admin/master/users/toggle/<int:id>', methods=['POST'])
@admin_required
def master_users_toggle(id):
    conn = get_db()
    conn.execute("UPDATE users SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('master_users'))

# ── Master: CoA ───────────────────────────────────────────────────────────────

@app.route('/admin/master/coa')
@admin_required
def master_coa():
    conn = get_db()
    coa = conn.execute("SELECT * FROM chart_of_accounts ORDER BY kode").fetchall()
    conn.close()
    return render_template('admin/master/coa.html', coa=coa)

@app.route('/admin/master/coa/tambah', methods=['POST'])
@admin_required
def master_coa_tambah():
    data = request.form
    conn = get_db()
    try:
        conn.execute('''INSERT INTO chart_of_accounts
            (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi) VALUES (?,?,?,?,?,?)''',
            (data['kode'].strip(), data['nama'].strip(), data['kelompok'],
             data.get('jenis_dana') or None, data.get('parent_kode') or None,
             data.get('jenis_transaksi') or None))
        conn.commit(); flash('Akun berhasil ditambahkan.', 'success')
    except sqlite3.IntegrityError:
        flash('Kode akun sudah ada.', 'danger')
    conn.close()
    return redirect(url_for('master_coa'))

@app.route('/admin/master/coa/toggle/<int:id>', methods=['POST'])
@admin_required
def master_coa_toggle(id):
    conn = get_db()
    conn.execute("UPDATE chart_of_accounts SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('master_coa'))

# ── Master: Donatur ───────────────────────────────────────────────────────────

@app.route('/admin/master/donatur')
@admin_required
def master_donatur():
    conn = get_db()
    q       = request.args.get('q','')
    sumber  = request.args.get('sumber','')
    area    = request.args.get('area','')
    query   = "SELECT d.*, c.nama AS program_nama FROM donatur d LEFT JOIN chart_of_accounts c ON d.program_id=c.id WHERE 1=1"
    params  = []
    if q:
        query += " AND (d.nama LIKE ? OR d.no_hp LIKE ? OR d.lokasi_nama LIKE ?)";
        params += [f'%{q}%',f'%{q}%',f'%{q}%']
    if sumber:
        query += " AND d.sumber_infaq=?"; params.append(sumber)
    if area:
        query += " AND d.area=?"; params.append(area)
    query += " ORDER BY d.sumber_infaq, d.area, d.nama"
    donatur = conn.execute(query, params).fetchall()
    areas   = conn.execute("SELECT nama AS area FROM area WHERE aktif=1 ORDER BY nama").fetchall()
    produk_list = conn.execute(
        "SELECT id, kode, nama, parent_kode FROM chart_of_accounts WHERE parent_kode IN ('4.1','4.2.1','4.4') AND jenis_transaksi='masuk' AND aktif=1 ORDER BY kode"
    ).fetchall()
    conn.close()
    return render_template('admin/master/donatur.html',
        donatur=donatur, areas=areas, produk_list=produk_list, q=q, sumber=sumber, area=area)

@app.route('/admin/master/donatur/tambah', methods=['POST'])
@admin_required
def master_donatur_tambah():
    data = request.form
    lat = lng = None
    gmaps = data.get('gmaps_url','').strip()
    if gmaps:
        lat, lng = parse_gmaps_url(gmaps)
    if not lat and data.get('lat'):
        try: lat = float(data['lat']); lng = float(data['lng'])
        except: pass
    conn = get_db()
    program_id = int(data['program_id']) if data.get('program_id') else None
    sumber = data.get('sumber_infaq', 'tunai')
    cur = conn.execute("""INSERT INTO donatur
        (nama,nik,no_hp,alamat,jenis,sumber_infaq,area,lokasi_nama,lat,lng,aktif_infaq,program_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data['nama'], data.get('nik',''), data.get('no_hp',''), data.get('alamat',''),
         data.get('jenis','perorangan'), sumber,
         data.get('area',''), data.get('lokasi_nama',''),
         lat, lng, 1 if data.get('aktif_infaq') else 0, program_id))
    auto_koleksi_donatur_baru(conn, cur.lastrowid, sumber)
    conn.commit(); conn.close()
    flash('Donatur berhasil ditambahkan.', 'success')
    return redirect(url_for('master_donatur'))

@app.route('/admin/master/donatur/edit/<int:id>', methods=['POST'])
@admin_required
def master_donatur_edit(id):
    data = request.form
    lat = lng = None
    gmaps = data.get('gmaps_url','').strip()
    if gmaps:
        lat, lng = parse_gmaps_url(gmaps)
    if not lat and data.get('lat'):
        try: lat = float(data['lat']); lng = float(data['lng'])
        except: pass
    conn = get_db()
    existing = conn.execute("SELECT lat,lng FROM donatur WHERE id=?", (id,)).fetchone()
    if lat is None and existing:
        lat, lng = existing['lat'], existing['lng']
    program_id = int(data['program_id']) if data.get('program_id') else None
    conn.execute("""UPDATE donatur SET
        nama=?,nik=?,no_hp=?,alamat=?,jenis=?,sumber_infaq=?,area=?,lokasi_nama=?,lat=?,lng=?,aktif_infaq=?,program_id=?
        WHERE id=?""",
        (data['nama'], data.get('nik',''), data.get('no_hp',''), data.get('alamat',''),
         data.get('jenis','perorangan'), data.get('sumber_infaq','tunai'),
         data.get('area',''), data.get('lokasi_nama',''),
         lat, lng, 1 if data.get('aktif_infaq') else 0, program_id, id))
    conn.commit(); conn.close()
    flash('Donatur diperbarui.', 'success')
    return redirect(url_for('master_donatur'))

@app.route('/admin/master/donatur/toggle/<int:id>', methods=['POST'])
@admin_required
def master_donatur_toggle(id):
    conn = get_db()
    conn.execute("UPDATE donatur SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('master_donatur'))

@app.route('/admin/master/donatur/quick/<int:id>', methods=['POST'])
@admin_required
def master_donatur_quick(id):
    ALLOWED = {'nama', 'area', 'no_hp', 'sumber_infaq', 'lokasi_nama'}
    data = request.json or {}
    field = data.get('field', '')
    value = data.get('value', '').strip()
    if field not in ALLOWED:
        return jsonify(ok=False, msg='Field tidak valid'), 400
    if field == 'nama' and not value:
        return jsonify(ok=False, msg='Nama wajib diisi'), 400
    conn = get_db()
    conn.execute(f"UPDATE donatur SET {field}=? WHERE id=?", (value or None, id))
    conn.commit(); conn.close()
    return jsonify(ok=True, field=field, value=value)

@app.route('/admin/master/donatur/template')
@admin_required
def donatur_template():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Donatur'
    headers = ['nama', 'no_hp', 'nik', 'alamat', 'jenis', 'sumber_infaq', 'area', 'lokasi_nama']
    hdr_font = Font(bold=True, color='FFFFFF')
    hdr_fill = PatternFill('solid', fgColor='27AE60')
    thin = Side(style='thin', color='CCCCCC')
    border = Border(bottom=thin)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal='center')
    examples = [
        ['Ahmad Fauzi', '6281234567890', '3301010101010001', 'Jl. Mawar No. 5', 'perorangan', 'kencleng', 'Giriwono', 'Rumah Pak Ahmad'],
        ['Toko Berkah', '6289876543210', '', 'Pasar Wonogiri', 'lembaga', 'kotak_infaq', 'Wonokarto', 'Toko Berkah - Pasar'],
    ]
    for r, row in enumerate(examples, 2):
        for c, val in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = Font(italic=True, color='999999')
            cell.border = border
    note = ws.cell(row=4, column=1, value='Catatan: Hapus baris contoh di atas, lalu isi data Anda.')
    note.font = Font(italic=True, color='FF0000')
    note2 = ws.cell(row=5, column=1, value='jenis: perorangan / lembaga | sumber_infaq: tunai / kencleng / kotak_infaq / zakat / infaq_terikat / wakaf')
    note2.font = Font(italic=True, color='666666')
    for col in range(1, len(headers)+1):
        ws.column_dimensions[chr(64+col)].width = 20
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, download_name='template_donatur.xlsx',
                     as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/master/donatur/import', methods=['POST'])
@admin_required
def donatur_import():
    f = request.files.get('file')
    if not f or not f.filename.endswith(('.xlsx', '.xls')):
        flash('Upload file Excel (.xlsx) yang valid.', 'danger')
        return redirect(url_for('master_donatur'))
    try:
        wb = load_workbook(f, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=1, values_only=True))
        wb.close()
    except Exception as e:
        flash(f'Gagal membaca file: {e}', 'danger')
        return redirect(url_for('master_donatur'))
    if len(rows) < 2:
        flash('File kosong atau hanya berisi header.', 'warning')
        return redirect(url_for('master_donatur'))
    header = [str(h).strip().lower() if h else '' for h in rows[0]]
    required = {'nama'}
    if not required.issubset(set(header)):
        flash('Kolom "nama" wajib ada di header.', 'danger')
        return redirect(url_for('master_donatur'))
    col_map = {h: i for i, h in enumerate(header) if h}
    conn = get_db()
    imported = 0
    skipped = 0
    incomplete = 0
    for row in rows[1:]:
        nama = str(row[col_map['nama']]).strip() if col_map.get('nama') is not None and row[col_map['nama']] else ''
        if not nama or nama.lower() in ('none', 'catatan:', 'catatan'):
            continue
        no_hp = str(row[col_map.get('no_hp', -1)] or '').strip() if 'no_hp' in col_map else ''
        nik = str(row[col_map.get('nik', -1)] or '').strip() if 'nik' in col_map else ''
        alamat = str(row[col_map.get('alamat', -1)] or '').strip() if 'alamat' in col_map else ''
        jenis = str(row[col_map.get('jenis', -1)] or '').strip().lower() if 'jenis' in col_map else 'perorangan'
        if jenis not in ('perorangan', 'lembaga'):
            jenis = 'perorangan'
        sumber = str(row[col_map.get('sumber_infaq', -1)] or '').strip().lower() if 'sumber_infaq' in col_map else 'tunai'
        if sumber not in ('tunai', 'kencleng', 'kotak_infaq', 'zakat', 'infaq_terikat', 'wakaf'):
            sumber = 'tunai'
        area_val = str(row[col_map.get('area', -1)] or '').strip() if 'area' in col_map else ''
        lokasi = str(row[col_map.get('lokasi_nama', -1)] or '').strip() if 'lokasi_nama' in col_map else ''
        existing = conn.execute("SELECT id FROM donatur WHERE LOWER(TRIM(nama))=LOWER(?)", (nama,)).fetchone()
        if existing:
            skipped += 1
            continue
        if not no_hp or not alamat or not area_val:
            incomplete += 1
        conn.execute("""INSERT INTO donatur (nama,no_hp,nik,alamat,jenis,sumber_infaq,area,lokasi_nama)
                        VALUES (?,?,?,?,?,?,?,?)""",
                     (nama, no_hp, nik, alamat, jenis, sumber, area_val, lokasi))
        imported += 1
    conn.commit()
    conn.close()
    msg = f'Import selesai: {imported} donatur ditambahkan, {skipped} duplikat dilewati.'
    if incomplete:
        msg += f' ({incomplete} dari {imported} data tidak lengkap — no_hp/alamat/area kosong)'
    flash(msg, 'success' if not incomplete else 'warning')
    return redirect(url_for('master_donatur'))

# ── Master: Penerima Manfaat ──────────────────────────────────────────────────

@app.route('/admin/master/penerima')
@admin_required
def master_penerima():
    conn = get_db()
    q = request.args.get('q',''); asnaf = request.args.get('asnaf','')
    query = "SELECT * FROM penerima_manfaat WHERE 1=1"; params = []
    if q:
        query += " AND (nama LIKE ? OR nik LIKE ? OR no_hp LIKE ?)"; params += [f'%{q}%']*3
    if asnaf:
        query += " AND asnaf=?"; params.append(asnaf)
    penerima = conn.execute(query + " ORDER BY nama", params).fetchall()
    conn.close()
    return render_template('admin/master/penerima.html', penerima=penerima, q=q, asnaf=asnaf)

@app.route('/admin/master/penerima/tambah', methods=['POST'])
@admin_required
def master_penerima_tambah():
    data = request.form
    conn = get_db()
    conn.execute("INSERT INTO penerima_manfaat (nama,nik,no_hp,alamat,asnaf,keterangan) VALUES (?,?,?,?,?,?)",
                 (data['nama'],data.get('nik',''),data.get('no_hp',''),
                  data.get('alamat',''),data.get('asnaf',''),data.get('keterangan','')))
    conn.commit(); conn.close()
    flash('Penerima manfaat berhasil ditambahkan.', 'success')
    return redirect(url_for('master_penerima'))

@app.route('/admin/master/penerima/edit/<int:id>', methods=['POST'])
@admin_required
def master_penerima_edit(id):
    data = request.form
    conn = get_db()
    conn.execute("UPDATE penerima_manfaat SET nama=?,nik=?,no_hp=?,alamat=?,asnaf=?,keterangan=? WHERE id=?",
                 (data['nama'],data.get('nik',''),data.get('no_hp',''),
                  data.get('alamat',''),data.get('asnaf',''),data.get('keterangan',''),id))
    conn.commit(); conn.close()
    flash('Penerima manfaat diperbarui.', 'success')
    return redirect(url_for('master_penerima'))

@app.route('/admin/master/penerima/toggle/<int:id>', methods=['POST'])
@admin_required
def master_penerima_toggle(id):
    conn = get_db()
    conn.execute("UPDATE penerima_manfaat SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('master_penerima'))

@app.route('/admin/master/penerima/template')
@admin_required
def penerima_template():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Penerima Manfaat'
    headers = ['nama', 'nik', 'no_hp', 'alamat', 'asnaf', 'keterangan']
    hdr_font = Font(bold=True, color='FFFFFF')
    hdr_fill = PatternFill('solid', fgColor='E74C3C')
    thin = Side(style='thin', color='CCCCCC')
    border = Border(bottom=thin)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal='center')
    examples = [
        ['Siti Aminah', '3301010203040005', '6281234000111', 'Dusun Bakaran RT 02/05', 'fakir', 'Janda, 3 anak'],
        ['Ahmad Soleh', '3301010203040006', '6289876000222', 'Ds. Krisak RT 01/03', 'miskin', 'Buruh tani'],
    ]
    for r, row in enumerate(examples, 2):
        for c, val in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = Font(italic=True, color='999999')
            cell.border = border
    note = ws.cell(row=4, column=1, value='Catatan: Hapus baris contoh di atas, lalu isi data Anda.')
    note.font = Font(italic=True, color='FF0000')
    note2 = ws.cell(row=5, column=1, value='asnaf: fakir / miskin / amil / muallaf / riqab / gharim / fisabilillah / ibnu_sabil')
    note2.font = Font(italic=True, color='666666')
    for col in range(1, len(headers)+1):
        ws.column_dimensions[chr(64+col)].width = 22
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, download_name='template_penerima_manfaat.xlsx',
                     as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/master/penerima/import', methods=['POST'])
@admin_required
def penerima_import():
    f = request.files.get('file')
    if not f or not f.filename.endswith(('.xlsx', '.xls')):
        flash('Upload file Excel (.xlsx) yang valid.', 'danger')
        return redirect(url_for('master_penerima'))
    try:
        wb = load_workbook(f, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=1, values_only=True))
        wb.close()
    except Exception as e:
        flash(f'Gagal membaca file: {e}', 'danger')
        return redirect(url_for('master_penerima'))
    if len(rows) < 2:
        flash('File kosong atau hanya berisi header.', 'warning')
        return redirect(url_for('master_penerima'))
    header = [str(h).strip().lower() if h else '' for h in rows[0]]
    if 'nama' not in header:
        flash('Kolom "nama" wajib ada di header.', 'danger')
        return redirect(url_for('master_penerima'))
    col_map = {h: i for i, h in enumerate(header) if h}
    valid_asnaf = {'fakir', 'miskin', 'amil', 'muallaf', 'riqab', 'gharim', 'fisabilillah', 'ibnu_sabil'}
    conn = get_db()
    imported = 0
    skipped = 0
    incomplete = 0
    for row in rows[1:]:
        nama = str(row[col_map['nama']]).strip() if col_map.get('nama') is not None and row[col_map['nama']] else ''
        if not nama or nama.lower() in ('none', 'catatan:', 'catatan'):
            continue
        nik = str(row[col_map.get('nik', -1)] or '').strip() if 'nik' in col_map else ''
        no_hp = str(row[col_map.get('no_hp', -1)] or '').strip() if 'no_hp' in col_map else ''
        alamat = str(row[col_map.get('alamat', -1)] or '').strip() if 'alamat' in col_map else ''
        asnaf = str(row[col_map.get('asnaf', -1)] or '').strip().lower() if 'asnaf' in col_map else ''
        if asnaf not in valid_asnaf:
            asnaf = ''
        keterangan = str(row[col_map.get('keterangan', -1)] or '').strip() if 'keterangan' in col_map else ''
        existing = conn.execute("SELECT id FROM penerima_manfaat WHERE LOWER(TRIM(nama))=LOWER(?)", (nama,)).fetchone()
        if existing:
            skipped += 1
            continue
        if not alamat or not asnaf or not no_hp:
            incomplete += 1
        conn.execute("INSERT INTO penerima_manfaat (nama,nik,no_hp,alamat,asnaf,keterangan) VALUES (?,?,?,?,?,?)",
                     (nama, nik, no_hp, alamat, asnaf, keterangan))
        imported += 1
    conn.commit()
    conn.close()
    msg = f'Import selesai: {imported} penerima ditambahkan, {skipped} duplikat dilewati.'
    if incomplete:
        msg += f' ({incomplete} dari {imported} data tidak lengkap — alamat/asnaf/no_hp kosong)'
    flash(msg, 'success' if not incomplete else 'warning')
    return redirect(url_for('master_penerima'))

# ── Master: Area ─────────────────────────────────────────────────────────────

@app.route('/admin/master/area')
@admin_required
def master_area():
    conn = get_db()
    areas = conn.execute("SELECT a.*, (SELECT COUNT(*) FROM donatur d WHERE d.area=a.nama) AS jml_donatur FROM area a ORDER BY a.nama").fetchall()
    conn.close()
    return render_template('admin/master/area.html', areas=areas)

@app.route('/admin/master/area/tambah', methods=['POST'])
@admin_required
def master_area_tambah():
    nama = request.form.get('nama', '').strip()
    if not nama:
        flash('Nama area wajib diisi.', 'danger')
        return redirect(url_for('master_area'))
    conn = get_db()
    existing = conn.execute("SELECT id FROM area WHERE nama=?", (nama,)).fetchone()
    if existing:
        flash('Area sudah ada.', 'warning')
    else:
        conn.execute("INSERT INTO area (nama) VALUES (?)", (nama,))
        conn.commit()
        flash(f'Area "{nama}" ditambahkan.', 'success')
    conn.close()
    return redirect(url_for('master_area'))

@app.route('/admin/master/area/edit/<int:id>', methods=['POST'])
@admin_required
def master_area_edit(id):
    nama = request.form.get('nama', '').strip()
    if not nama:
        flash('Nama area wajib diisi.', 'danger')
        return redirect(url_for('master_area'))
    conn = get_db()
    old = conn.execute("SELECT nama FROM area WHERE id=?", (id,)).fetchone()
    dup = conn.execute("SELECT id FROM area WHERE nama=? AND id!=?", (nama, id)).fetchone()
    if dup:
        flash('Nama area sudah dipakai.', 'warning')
    else:
        conn.execute("UPDATE area SET nama=? WHERE id=?", (nama, id))
        if old and old['nama']:
            conn.execute("UPDATE donatur SET area=? WHERE area=?", (nama, old['nama']))
        conn.commit()
        flash(f'Area diperbarui menjadi "{nama}".', 'success')
    conn.close()
    return redirect(url_for('master_area'))

@app.route('/admin/master/area/toggle/<int:id>', methods=['POST'])
@admin_required
def master_area_toggle(id):
    conn = get_db()
    conn.execute("UPDATE area SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(url_for('master_area'))

@app.route('/admin/master/area/hapus/<int:id>', methods=['POST'])
@admin_required
def master_area_hapus(id):
    conn = get_db()
    cnt = conn.execute("SELECT COUNT(*) FROM donatur WHERE area=(SELECT nama FROM area WHERE id=?)", (id,)).fetchone()[0]
    if cnt > 0:
        flash(f'Tidak bisa hapus — masih ada {cnt} donatur di area ini.', 'danger')
    else:
        conn.execute("DELETE FROM area WHERE id=?", (id,))
        conn.commit()
        flash('Area dihapus.', 'success')
    conn.close()
    return redirect(url_for('master_area'))

# ── Master: Instansi ─────────────────────────────────────────────────────────

@app.route('/admin/master/instansi')
@admin_required
def master_instansi():
    conn = get_db()
    inst = get_instansi(conn)
    conn.close()
    return render_template('admin/master/instansi.html', inst=inst)

@app.route('/admin/master/instansi/simpan', methods=['POST'])
@admin_required
def master_instansi_simpan():
    data = request.form
    conn = get_db()
    conn.execute("""UPDATE instansi SET
        nama=?, nama_lembaga=?, alamat=?, telepon=?, email=?, website=?,
        ketua=?, bendahara=?, sekretaris=?, no_izin=?,
        updated_at=datetime('now','localtime')
        WHERE id=1""",
        (data.get('nama','').strip(), data.get('nama_lembaga','').strip(),
         data.get('alamat','').strip(), data.get('telepon','').strip(),
         data.get('email','').strip(), data.get('website','').strip(),
         data.get('ketua','').strip(), data.get('bendahara','').strip(),
         data.get('sekretaris','').strip(), data.get('no_izin','').strip()))
    conn.commit(); conn.close()
    flash('Data instansi berhasil diperbarui.', 'success')
    return redirect(url_for('master_instansi'))

# ── Admin Jurnal (Non-Tunai) ─────────────────────────────────────────────────

@app.route('/admin/jurnal')
@admin_required
def admin_jurnal():
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    jurnal = conn.execute('''
        SELECT j.*, cd.kode as debit_kode, cd.nama as debit_nama,
               ck.kode as kredit_kode, ck.nama as kredit_nama, u.nama as petugas
        FROM jurnal j
        LEFT JOIN chart_of_accounts cd ON j.debit_coa_id=cd.id
        LEFT JOIN chart_of_accounts ck ON j.kredit_coa_id=ck.id
        LEFT JOIN users u ON j.user_id=u.id
        WHERE strftime('%Y-%m',j.tanggal)=?
        ORDER BY j.tanggal DESC, j.created_at DESC
    ''', (bulan,)).fetchall()
    coa_all = conn.execute(
        "SELECT id, kode, nama, kelompok, jenis_dana FROM chart_of_accounts WHERE aktif=1 ORDER BY kode"
    ).fetchall()
    conn.close()
    return render_template('admin/jurnal.html', jurnal=jurnal, coa_all=coa_all, bulan=bulan)

@app.route('/admin/jurnal/tambah', methods=['POST'])
@admin_required
def admin_jurnal_tambah():
    data = request.form
    conn = get_db()
    debit_coa_id = int(data['debit_coa_id'])
    kredit_coa_id = int(data['kredit_coa_id'])
    jumlah = float(data['jumlah'].replace('.','').replace(',',''))
    tanggal = data['tanggal']
    keterangan = data.get('keterangan', '')
    no_bukti = data.get('no_bukti', '').strip()

    cur = conn.execute("""INSERT INTO jurnal
        (tanggal, no_bukti, keterangan, debit_coa_id, kredit_coa_id, jumlah, user_id)
        VALUES (?,?,?,?,?,?,?)""",
        (tanggal, no_bukti, keterangan, debit_coa_id, kredit_coa_id, jumlah, session['user_id']))
    jurnal_id = cur.lastrowid

    debit_coa = conn.execute("SELECT jenis_dana, jenis_transaksi FROM chart_of_accounts WHERE id=?",
                              (debit_coa_id,)).fetchone()
    kredit_coa = conn.execute("SELECT jenis_dana, jenis_transaksi FROM chart_of_accounts WHERE id=?",
                               (kredit_coa_id,)).fetchone()

    conn.execute("""INSERT INTO transaksi
        (tanggal, jenis, jenis_dana, coa_id, jumlah, keterangan, user_id, jurnal_id)
        VALUES (?,?,?,?,?,?,?,?)""",
        (tanggal, 'masuk', debit_coa['jenis_dana'] if debit_coa else None,
         debit_coa_id, jumlah, f'[Jurnal] {keterangan}', session['user_id'], jurnal_id))

    conn.execute("""INSERT INTO transaksi
        (tanggal, jenis, jenis_dana, coa_id, jumlah, keterangan, user_id, jurnal_id)
        VALUES (?,?,?,?,?,?,?,?)""",
        (tanggal, 'keluar', kredit_coa['jenis_dana'] if kredit_coa else None,
         kredit_coa_id, jumlah, f'[Jurnal] {keterangan}', session['user_id'], jurnal_id))

    conn.commit(); conn.close()
    flash('Jurnal berhasil dicatat.', 'success')
    return redirect(url_for('admin_jurnal'))

@app.route('/admin/jurnal/hapus/<int:id>', methods=['POST'])
@admin_required
def admin_jurnal_hapus(id):
    conn = get_db()
    conn.execute("DELETE FROM transaksi WHERE jurnal_id=?", (id,))
    conn.execute("DELETE FROM jurnal WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Jurnal dan transaksi terkait dihapus.', 'warning')
    return redirect(url_for('admin_jurnal'))

# ── Marketing Dashboard ───────────────────────────────────────────────────────

@app.route('/marketing')
@login_required
def marketing_dashboard():
    conn = get_db()
    bulan = date.today().strftime('%Y-%m')
    total_masuk_bulan = conn.execute(
        "SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE jenis='masuk' AND strftime('%Y-%m',tanggal)=? AND user_id=?",
        (bulan, session['user_id'])
    ).fetchone()[0]
    koleksi_bulan = conn.execute(
        "SELECT COUNT(*) as jumlah, COALESCE(SUM(jumlah),0) as nominal FROM koleksi_bulanan "
        "WHERE bulan=? AND marketing_id=? AND status='terkumpul'",
        (bulan, session['user_id'])
    ).fetchone()
    transaksi_hari = conn.execute('''
        SELECT t.*, c.nama as coa_nama, c.jenis_dana, d.nama as donatur_nama
        FROM transaksi t
        LEFT JOIN chart_of_accounts c ON t.coa_id=c.id
        LEFT JOIN donatur d ON t.donatur_id=d.id
        WHERE t.user_id=? AND t.tanggal=? ORDER BY t.created_at DESC
    ''', (session['user_id'], date.today().isoformat())).fetchall()
    conn.close()
    return render_template('marketing/dashboard.html',
        total_masuk_bulan=total_masuk_bulan, koleksi_bulan=koleksi_bulan,
        transaksi_hari=transaksi_hari, hari_ini=date.today().strftime('%d %B %Y'))

# ── Marketing Koleksi ─────────────────────────────────────────────────────────

@app.route('/marketing/koleksi')
@login_required
def marketing_koleksi():
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    area  = request.args.get('area', '')
    q     = request.args.get('q', '').strip()
    query = '''
        SELECT kb.*, d.nama as donatur_nama, d.sumber_infaq, d.area,
               d.lokasi_nama, d.lat, d.lng, u.nama as marketing_nama
        FROM koleksi_bulanan kb
        JOIN donatur d ON kb.donatur_id=d.id
        LEFT JOIN users u ON kb.marketing_kunjungi_terakhir=u.id
        WHERE kb.bulan=? AND kb.status != 'terkumpul' '''
    params = [bulan]
    if area == '__none__':
        query += " AND (d.area IS NULL OR d.area='')"
    elif area:
        query += ' AND d.area=?'; params.append(area)
    if q:
        query += ' AND (d.nama LIKE ? OR d.lokasi_nama LIKE ?)'
        params += [f'%{q}%', f'%{q}%']
    query += ' ORDER BY d.area, d.sumber_infaq, d.nama'
    koleksi = conn.execute(query, params).fetchall()
    areas = conn.execute(
        "SELECT DISTINCT d.area FROM koleksi_bulanan kb JOIN donatur d ON kb.donatur_id=d.id "
        "WHERE kb.bulan=? AND kb.status!='terkumpul' AND d.area IS NOT NULL ORDER BY d.area",
        (bulan,)
    ).fetchall()
    stats = conn.execute(
        "SELECT COUNT(*) as total, SUM(CASE WHEN status='terkumpul' THEN 1 ELSE 0 END) as terkumpul "
        "FROM koleksi_bulanan WHERE bulan=?", (bulan,)
    ).fetchone()
    conn.close()
    return render_template('marketing/koleksi.html', koleksi=koleksi, areas=areas,
        bulan=bulan, area=area, q=q, stats=stats)

@app.route('/marketing/koleksi/<int:id>', methods=['GET'])
@login_required
def marketing_koleksi_form(id):
    conn = get_db()
    koleksi = conn.execute('''
        SELECT kb.*, d.nama as donatur_nama, d.sumber_infaq, d.area,
               d.lokasi_nama, d.lat, d.lng
        FROM koleksi_bulanan kb JOIN donatur d ON kb.donatur_id=d.id
        WHERE kb.id=?
    ''', (id,)).fetchone()
    if not koleksi:
        flash('Data koleksi tidak ditemukan.', 'danger')
        return redirect(url_for('marketing_koleksi'))
    if koleksi['status'] == 'terkumpul':
        flash('Kencleng/kotak ini sudah dikoleksi.', 'warning')
        return redirect(url_for('marketing_koleksi'))
    riwayat = conn.execute('''
        SELECT kb.*, u.nama as marketing_nama
        FROM koleksi_bulanan kb LEFT JOIN users u ON kb.marketing_id=u.id
        WHERE kb.donatur_id=? AND kb.status='terkumpul'
        ORDER BY kb.bulan DESC LIMIT 6
    ''', (koleksi['donatur_id'],)).fetchall()
    conn.close()
    return render_template('marketing/koleksi_catat.html', koleksi=koleksi,
        riwayat=riwayat, hari_ini=date.today().isoformat())

@app.route('/marketing/koleksi/<int:id>/catat', methods=['POST'])
@login_required
def marketing_koleksi_catat(id):
    conn  = get_db()
    aksi  = request.form.get('aksi')   # 'terkumpul' atau 'tidak_ada'
    today = date.today().isoformat()

    if aksi == 'terkumpul':
        jumlah = float((request.form.get('jumlah', '0') or '0').replace('.','').replace(',',''))
        kol = conn.execute("SELECT * FROM koleksi_bulanan WHERE id=?", (id,)).fetchone()
        if not kol:
            conn.close(); flash('Data tidak ditemukan.', 'danger')
            return redirect(url_for('marketing_koleksi'))

        rows = conn.execute(
            "UPDATE koleksi_bulanan SET status='terkumpul', marketing_id=?, "
            "tanggal_koleksi=?, jumlah=?, keterangan=? "
            "WHERE id=? AND status != 'terkumpul'",
            (session['user_id'], today, jumlah,
             request.form.get('keterangan',''), id)
        ).rowcount

        if rows == 0:
            conn.close()
            # Cek siapa yang sudah koleksi duluan
            other = conn.execute(
                "SELECT u.nama, kb.tanggal_koleksi FROM koleksi_bulanan kb "
                "JOIN users u ON kb.marketing_id=u.id WHERE kb.id=?", (id,)
            ).fetchone()
            msg = f"Sudah dikoleksi oleh {other['nama']} pada {other['tanggal_koleksi']}." if other else "Sudah dikoleksi."
            flash(msg, 'warning')
            return redirect(url_for('marketing_koleksi'))

        donatur = conn.execute("SELECT * FROM donatur WHERE id=?", (kol['donatur_id'],)).fetchone()
        auto_transaksi_koleksi(conn, id, kol['donatur_id'], kol['bulan'],
                               donatur['sumber_infaq'], jumlah, today, session['user_id'])
        conn.commit(); conn.close()
        flash(f'Koleksi berhasil dicatat: {format_rupiah(jumlah)}', 'success')

    elif aksi == 'tidak_ada':
        conn.execute(
            "UPDATE koleksi_bulanan SET status='tidak_ada', "
            "jumlah_kunjungan = jumlah_kunjungan + 1, "
            "kunjungan_terakhir=?, marketing_kunjungi_terakhir=?, keterangan=? "
            "WHERE id=?",
            (today, session['user_id'], request.form.get('keterangan',''), id)
        )
        conn.commit(); conn.close()
        flash('Kunjungan dicatat. Coba lagi lain waktu.', 'info')

    return redirect(url_for('marketing_koleksi'))

# ── Marketing Donatur Detail ──────────────────────────────────────────────────

@app.route('/marketing/donatur/<int:id>')
@login_required
def marketing_donatur_detail(id):
    conn = get_db()
    donatur = conn.execute("SELECT * FROM donatur WHERE id=?", (id,)).fetchone()
    if not donatur:
        conn.close(); flash('Donatur tidak ditemukan.', 'danger')
        return redirect(url_for('marketing_koleksi'))
    riwayat = conn.execute('''
        SELECT kb.*, u.nama as marketing_nama
        FROM koleksi_bulanan kb LEFT JOIN users u ON kb.marketing_id=u.id
        WHERE kb.donatur_id=? ORDER BY kb.bulan DESC
    ''', (id,)).fetchall()
    conn.close()
    return render_template('marketing/donatur_detail.html', donatur=donatur, riwayat=riwayat)

# ── Marketing Peta ────────────────────────────────────────────────────────────

@app.route('/marketing/peta')
@login_required
def marketing_peta():
    conn = get_db()
    bulan = date.today().strftime('%Y-%m')
    titik = conn.execute('''
        SELECT kb.id, kb.status, kb.jumlah_kunjungan,
               d.nama, d.sumber_infaq, d.area, d.lokasi_nama, d.lat, d.lng
        FROM koleksi_bulanan kb JOIN donatur d ON kb.donatur_id=d.id
        WHERE kb.bulan=? AND kb.status != 'terkumpul'
              AND d.lat IS NOT NULL AND d.lng IS NOT NULL
        ORDER BY d.area, d.nama
    ''', (bulan,)).fetchall()
    titik_json = json.dumps([dict(t) for t in titik])
    conn.close()
    return render_template('marketing/peta.html', titik_json=titik_json, bulan=bulan)

# ── Marketing Donatur ─────────────────────────────────────────────────────────

@app.route('/marketing/donatur')
@login_required
def marketing_donatur_list():
    conn = get_db()
    q = request.args.get('q', '').strip()
    query = "SELECT * FROM donatur WHERE aktif=1"
    params = []
    if q:
        query += " AND (nama LIKE ? OR area LIKE ? OR no_hp LIKE ?)"
        params += [f'%{q}%'] * 3
    query += " ORDER BY nama"
    donatur = conn.execute(query, params).fetchall()
    areas = conn.execute("SELECT nama AS area FROM area WHERE aktif=1 ORDER BY nama").fetchall()
    conn.close()
    return render_template('marketing/donatur.html', donatur=donatur, areas=areas, q=q)

@app.route('/marketing/donatur/tambah', methods=['POST'])
@login_required
def marketing_donatur_tambah():
    data = request.form
    lat = lng = None
    gmaps = data.get('gmaps_url', '').strip()
    if gmaps:
        lat, lng = parse_gmaps_url(gmaps)
    if not lat and data.get('lat'):
        try: lat = float(data['lat']); lng = float(data['lng'])
        except: pass
    conn = get_db()
    sumber = data.get('sumber_infaq', 'tunai')
    cur = conn.execute("""INSERT INTO donatur
        (nama,no_hp,sumber_infaq,area,lokasi_nama,lat,lng,aktif_infaq)
        VALUES (?,?,?,?,?,?,?,?)""",
        (data['nama'], data.get('no_hp', ''),
         sumber,
         data.get('area', ''), data.get('lokasi_nama', ''),
         lat, lng, 1 if data.get('aktif_infaq') else 0))
    auto_koleksi_donatur_baru(conn, cur.lastrowid, sumber)
    conn.commit(); conn.close()
    flash(f'Donatur "{data["nama"]}" berhasil ditambahkan.', 'success')
    return redirect(url_for('marketing_donatur_list'))

# ── Marketing Transaksi Tunai ─────────────────────────────────────────────────

@app.route('/marketing/catat', methods=['GET', 'POST'])
@login_required
def marketing_catat():
    conn = get_db()
    if request.method == 'POST':
        data = request.form
        coa_id = data.get('coa_id') or None
        jenis_dana = None
        if coa_id:
            row = conn.execute("SELECT jenis_dana FROM chart_of_accounts WHERE id=?", (coa_id,)).fetchone()
            if row: jenis_dana = row['jenis_dana']
        conn.execute('''INSERT INTO transaksi
            (tanggal,jenis,jenis_dana,coa_id,donatur_id,penerima_id,jumlah,keterangan,user_id)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['tanggal'], data['jenis'], jenis_dana, coa_id,
             data.get('donatur_id') or None, data.get('penerima_id') or None,
             float(data['jumlah'].replace('.','').replace(',','')),
             data.get('keterangan',''), session['user_id']))
        conn.commit(); conn.close()
        flash('Transaksi berhasil dicatat!', 'success')
        return redirect(url_for('marketing_dashboard'))
    coa_list      = conn.execute("SELECT * FROM chart_of_accounts WHERE jenis_transaksi IS NOT NULL AND aktif=1 ORDER BY kode").fetchall()
    coa_parents   = conn.execute("SELECT kode, nama FROM chart_of_accounts WHERE parent_kode IS NOT NULL AND aktif=1 ORDER BY kode").fetchall()
    donatur_list  = conn.execute("SELECT id, nama, area FROM donatur WHERE aktif=1 ORDER BY nama").fetchall()
    penerima_list = conn.execute("SELECT * FROM penerima_manfaat WHERE aktif=1 ORDER BY nama").fetchall()
    conn.close()
    return render_template('marketing/catat.html', coa_list=coa_list,
        coa_parents=coa_parents,
        donatur_list=donatur_list, penerima_list=penerima_list,
        hari_ini=date.today().isoformat())

@app.route('/marketing/riwayat')
@login_required
def marketing_riwayat():
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    transaksi = conn.execute('''
        SELECT t.*, c.nama as coa_nama, c.jenis_dana, d.nama as donatur_nama
        FROM transaksi t
        LEFT JOIN chart_of_accounts c ON t.coa_id=c.id
        LEFT JOIN donatur d ON t.donatur_id=d.id
        WHERE t.user_id=? AND strftime('%Y-%m',t.tanggal)=?
        ORDER BY t.tanggal DESC, t.created_at DESC
    ''', (session['user_id'], bulan)).fetchall()
    total = sum(r['jumlah'] for r in transaksi if r['jenis']=='masuk')
    conn.close()
    return render_template('marketing/riwayat.html', transaksi=transaksi, bulan=bulan, total=total)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
