from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, hashlib, os, re, json
from datetime import datetime, date
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
    donatur_list= conn.execute("SELECT * FROM donatur WHERE aktif=1 ORDER BY nama").fetchall()
    penerima_list=conn.execute("SELECT * FROM penerima_manfaat WHERE aktif=1 ORDER BY nama").fetchall()
    conn.close()
    return render_template('admin/transaksi.html', transaksi=transaksi, coa_list=coa_list,
        donatur_list=donatur_list, penerima_list=penerima_list,
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
    conn = get_db()
    bulan = request.args.get('bulan', date.today().strftime('%Y-%m'))
    rekap = conn.execute('''
        SELECT c.kode, c.nama, c.jenis_dana, t.jenis,
               SUM(t.jumlah) as total, COUNT(*) as jumlah_transaksi
        FROM transaksi t JOIN chart_of_accounts c ON t.coa_id=c.id
        WHERE strftime('%Y-%m',t.tanggal)=?
        GROUP BY c.id ORDER BY c.kode
    ''', (bulan,)).fetchall()
    total_masuk  = sum(r['total'] for r in rekap if r['jenis']=='masuk')
    total_keluar = sum(r['total'] for r in rekap if r['jenis']=='keluar')
    rekap_per_dana = {}
    for r in rekap:
        dana = r['jenis_dana'] or 'umum'
        if dana not in rekap_per_dana:
            rekap_per_dana[dana] = {'masuk':0,'keluar':0,'items':[]}
        rekap_per_dana[dana][r['jenis']] += r['total']
        rekap_per_dana[dana]['items'].append(r)
    conn.close()
    return render_template('admin/laporan.html', rekap=rekap, total_masuk=total_masuk,
        total_keluar=total_keluar, rekap_per_dana=rekap_per_dana, bulan=bulan)

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
    query   = "SELECT * FROM donatur WHERE 1=1"
    params  = []
    if q:
        query += " AND (nama LIKE ? OR no_hp LIKE ? OR lokasi_nama LIKE ?)";
        params += [f'%{q}%',f'%{q}%',f'%{q}%']
    if sumber:
        query += " AND sumber_infaq=?"; params.append(sumber)
    if area:
        query += " AND area=?"; params.append(area)
    query += " ORDER BY sumber_infaq, area, nama"
    donatur = conn.execute(query, params).fetchall()
    areas   = conn.execute("SELECT DISTINCT area FROM donatur WHERE area IS NOT NULL ORDER BY area").fetchall()
    conn.close()
    return render_template('admin/master/donatur.html',
        donatur=donatur, areas=areas, q=q, sumber=sumber, area=area)

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
    conn.execute("""INSERT INTO donatur
        (nama,nik,no_hp,alamat,jenis,sumber_infaq,area,lokasi_nama,lat,lng,aktif_infaq)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (data['nama'], data.get('nik',''), data.get('no_hp',''), data.get('alamat',''),
         data.get('jenis','perorangan'), data.get('sumber_infaq','tunai'),
         data.get('area',''), data.get('lokasi_nama',''),
         lat, lng, 1 if data.get('aktif_infaq') else 0))
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
    conn.execute("""UPDATE donatur SET
        nama=?,nik=?,no_hp=?,alamat=?,jenis=?,sumber_infaq=?,area=?,lokasi_nama=?,lat=?,lng=?,aktif_infaq=?
        WHERE id=?""",
        (data['nama'], data.get('nik',''), data.get('no_hp',''), data.get('alamat',''),
         data.get('jenis','perorangan'), data.get('sumber_infaq','tunai'),
         data.get('area',''), data.get('lokasi_nama',''),
         lat, lng, 1 if data.get('aktif_infaq') else 0, id))
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
    query = '''
        SELECT kb.*, d.nama as donatur_nama, d.sumber_infaq, d.area,
               d.lokasi_nama, d.lat, d.lng, u.nama as marketing_nama
        FROM koleksi_bulanan kb
        JOIN donatur d ON kb.donatur_id=d.id
        LEFT JOIN users u ON kb.marketing_kunjungi_terakhir=u.id
        WHERE kb.bulan=? AND kb.status != 'terkumpul' '''
    params = [bulan]
    if area:
        query += ' AND d.area=?'; params.append(area)
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
        bulan=bulan, area=area, stats=stats)

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
        jumlah = float(request.form.get('jumlah', 0) or 0)
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
    donatur_list  = conn.execute("SELECT * FROM donatur WHERE aktif=1 ORDER BY nama").fetchall()
    penerima_list = conn.execute("SELECT * FROM penerima_manfaat WHERE aktif=1 ORDER BY nama").fetchall()
    # Map parent_kode → nama untuk optgroup label
    parents = conn.execute("SELECT kode, nama FROM chart_of_accounts WHERE jenis_transaksi IS NULL").fetchall()
    coa_group = {p['kode']: p['nama'] for p in parents}
    conn.close()
    return render_template('marketing/catat.html', coa_list=coa_list,
        donatur_list=donatur_list, penerima_list=penerima_list,
        coa_group=coa_group, hari_ini=date.today().isoformat())

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
