from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import hashlib
import os
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

LABEL_DANA = {
    'zakat': 'Zakat', 'infak_sedekah': 'Infak/Sedekah',
    'amil': 'Amil', 'wakaf': 'Wakaf', 'umum': 'Umum'
}
LABEL_ASNAF = {
    'fakir': 'Fakir', 'miskin': 'Miskin', 'amil': 'Amil', 'muallaf': 'Muallaf',
    'riqab': 'Riqab', 'gharim': 'Gharim', 'fisabilillah': 'Fisabilillah', 'ibnu_sabil': 'Ibnu Sabil'
}
app.jinja_env.globals['LABEL_DANA'] = LABEL_DANA
app.jinja_env.globals['LABEL_ASNAF'] = LABEL_ASNAF

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard') if session['role'] == 'admin' else url_for('marketing_dashboard'))
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
            session.update({'user_id': user['id'], 'username': user['username'],
                            'nama': user['nama'], 'role': user['role']})
            return redirect(url_for('admin_dashboard') if user['role'] == 'admin' else url_for('marketing_dashboard'))
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

    total_masuk = conn.execute(
        "SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE jenis='masuk' AND strftime('%Y-%m',tanggal)=?", (bulan,)
    ).fetchone()[0]
    total_keluar = conn.execute(
        "SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE jenis='keluar' AND strftime('%Y-%m',tanggal)=?", (bulan,)
    ).fetchone()[0]
    saldo = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN jenis='masuk' THEN jumlah ELSE -jumlah END),0) FROM transaksi"
    ).fetchone()[0]

    transaksi_terakhir = conn.execute('''
        SELECT t.*, c.nama as coa_nama, c.jenis_dana, d.nama as donatur_nama, u.nama as petugas
        FROM transaksi t
        LEFT JOIN chart_of_accounts c ON t.coa_id=c.id
        LEFT JOIN donatur d ON t.donatur_id=d.id
        LEFT JOIN users u ON t.user_id=u.id
        ORDER BY t.created_at DESC LIMIT 10
    ''').fetchall()

    rekap_dana = conn.execute('''
        SELECT jenis_dana, jenis, SUM(jumlah) as total
        FROM transaksi
        WHERE strftime('%Y-%m',tanggal)=? AND jenis_dana IS NOT NULL
        GROUP BY jenis_dana, jenis ORDER BY jenis_dana
    ''', (bulan,)).fetchall()

    conn.close()
    return render_template('admin/dashboard.html',
        total_masuk=total_masuk, total_keluar=total_keluar, saldo=saldo,
        transaksi_terakhir=transaksi_terakhir, rekap_dana=rekap_dana, bulan=bulan)

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
        WHERE strftime('%Y-%m',t.tanggal)=?
    '''
    params = [bulan]
    if jenis in ('masuk', 'keluar'):
        query += ' AND t.jenis=?'
        params.append(jenis)
    if jenis_dana:
        query += ' AND t.jenis_dana=?'
        params.append(jenis_dana)
    query += ' ORDER BY t.tanggal DESC, t.created_at DESC'

    transaksi = conn.execute(query, params).fetchall()
    coa_list = conn.execute(
        "SELECT * FROM chart_of_accounts WHERE jenis_transaksi IS NOT NULL AND aktif=1 ORDER BY kode"
    ).fetchall()
    donatur_list = conn.execute("SELECT * FROM donatur WHERE aktif=1 ORDER BY nama").fetchall()
    penerima_list = conn.execute("SELECT * FROM penerima_manfaat WHERE aktif=1 ORDER BY nama").fetchall()
    conn.close()
    return render_template('admin/transaksi.html',
        transaksi=transaksi, coa_list=coa_list, donatur_list=donatur_list,
        penerima_list=penerima_list, bulan=bulan, jenis=jenis, jenis_dana=jenis_dana)

@app.route('/admin/transaksi/tambah', methods=['POST'])
@admin_required
def tambah_transaksi():
    data = request.form
    conn = get_db()
    coa_id = data.get('coa_id') or None
    jenis_dana = None
    if coa_id:
        row = conn.execute("SELECT jenis_dana FROM chart_of_accounts WHERE id=?", (coa_id,)).fetchone()
        if row:
            jenis_dana = row['jenis_dana']
    conn.execute('''
        INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,donatur_id,penerima_id,jumlah,keterangan,user_id)
        VALUES (?,?,?,?,?,?,?,?,?)
    ''', (
        data['tanggal'], data['jenis'], jenis_dana, coa_id,
        data.get('donatur_id') or None,
        data.get('penerima_id') or None,
        float(data['jumlah'].replace('.', '').replace(',', '')),
        data.get('keterangan', ''), session['user_id']
    ))
    conn.commit()
    conn.close()
    flash('Transaksi berhasil dicatat.', 'success')
    return redirect(url_for('admin_transaksi'))

@app.route('/admin/transaksi/hapus/<int:id>', methods=['POST'])
@admin_required
def hapus_transaksi(id):
    conn = get_db()
    conn.execute("DELETE FROM transaksi WHERE id=?", (id,))
    conn.commit()
    conn.close()
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

    total_masuk = sum(r['total'] for r in rekap if r['jenis'] == 'masuk')
    total_keluar = sum(r['total'] for r in rekap if r['jenis'] == 'keluar')

    rekap_per_dana = {}
    for r in rekap:
        dana = r['jenis_dana'] or 'umum'
        if dana not in rekap_per_dana:
            rekap_per_dana[dana] = {'masuk': 0, 'keluar': 0, 'items': []}
        rekap_per_dana[dana][r['jenis']] += r['total']
        rekap_per_dana[dana]['items'].append(r)

    conn.close()
    return render_template('admin/laporan.html',
        rekap=rekap, total_masuk=total_masuk, total_keluar=total_keluar,
        rekap_per_dana=rekap_per_dana, bulan=bulan)

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
                     (data['username'], hash_pw(data['password']), data['nama'], data['role'], data.get('no_hp','')))
        conn.commit()
        flash('User berhasil ditambahkan.', 'success')
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
                     (data['nama'], data['role'], data.get('no_hp',''), hash_pw(data['password']), id))
    else:
        conn.execute("UPDATE users SET nama=?,role=?,no_hp=? WHERE id=?",
                     (data['nama'], data['role'], data.get('no_hp',''), id))
    conn.commit()
    conn.close()
    flash('User diperbarui.', 'success')
    return redirect(url_for('master_users'))

@app.route('/admin/master/users/toggle/<int:id>', methods=['POST'])
@admin_required
def master_users_toggle(id):
    conn = get_db()
    conn.execute("UPDATE users SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('master_users'))

# ── Master: Chart of Accounts ─────────────────────────────────────────────────

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
            (kode,nama,kelompok,jenis_dana,parent_kode,jenis_transaksi)
            VALUES (?,?,?,?,?,?)''',
            (data['kode'].strip(), data['nama'].strip(), data['kelompok'],
             data.get('jenis_dana') or None, data.get('parent_kode') or None,
             data.get('jenis_transaksi') or None))
        conn.commit()
        flash('Akun berhasil ditambahkan.', 'success')
    except sqlite3.IntegrityError:
        flash('Kode akun sudah ada.', 'danger')
    conn.close()
    return redirect(url_for('master_coa'))

@app.route('/admin/master/coa/toggle/<int:id>', methods=['POST'])
@admin_required
def master_coa_toggle(id):
    conn = get_db()
    conn.execute("UPDATE chart_of_accounts SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('master_coa'))

# ── Master: Donatur ───────────────────────────────────────────────────────────

@app.route('/admin/master/donatur')
@admin_required
def master_donatur():
    conn = get_db()
    q = request.args.get('q', '')
    if q:
        donatur = conn.execute(
            "SELECT * FROM donatur WHERE nama LIKE ? OR no_hp LIKE ? ORDER BY nama",
            (f'%{q}%', f'%{q}%')
        ).fetchall()
    else:
        donatur = conn.execute("SELECT * FROM donatur ORDER BY nama").fetchall()
    conn.close()
    return render_template('admin/master/donatur.html', donatur=donatur, q=q)

@app.route('/admin/master/donatur/tambah', methods=['POST'])
@admin_required
def master_donatur_tambah():
    data = request.form
    conn = get_db()
    conn.execute("INSERT INTO donatur (nama,nik,no_hp,alamat,jenis) VALUES (?,?,?,?,?)",
                 (data['nama'], data.get('nik',''), data.get('no_hp',''),
                  data.get('alamat',''), data.get('jenis','perorangan')))
    conn.commit()
    conn.close()
    flash('Donatur berhasil ditambahkan.', 'success')
    return redirect(url_for('master_donatur'))

@app.route('/admin/master/donatur/edit/<int:id>', methods=['POST'])
@admin_required
def master_donatur_edit(id):
    data = request.form
    conn = get_db()
    conn.execute("UPDATE donatur SET nama=?,nik=?,no_hp=?,alamat=?,jenis=? WHERE id=?",
                 (data['nama'], data.get('nik',''), data.get('no_hp',''),
                  data.get('alamat',''), data.get('jenis','perorangan'), id))
    conn.commit()
    conn.close()
    flash('Donatur diperbarui.', 'success')
    return redirect(url_for('master_donatur'))

@app.route('/admin/master/donatur/toggle/<int:id>', methods=['POST'])
@admin_required
def master_donatur_toggle(id):
    conn = get_db()
    conn.execute("UPDATE donatur SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('master_donatur'))

# ── Master: Penerima Manfaat ──────────────────────────────────────────────────

@app.route('/admin/master/penerima')
@admin_required
def master_penerima():
    conn = get_db()
    q = request.args.get('q', '')
    asnaf = request.args.get('asnaf', '')
    query = "SELECT * FROM penerima_manfaat WHERE 1=1"
    params = []
    if q:
        query += " AND (nama LIKE ? OR nik LIKE ? OR no_hp LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if asnaf:
        query += " AND asnaf=?"
        params.append(asnaf)
    query += " ORDER BY nama"
    penerima = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin/master/penerima.html', penerima=penerima, q=q, asnaf=asnaf)

@app.route('/admin/master/penerima/tambah', methods=['POST'])
@admin_required
def master_penerima_tambah():
    data = request.form
    conn = get_db()
    conn.execute("INSERT INTO penerima_manfaat (nama,nik,no_hp,alamat,asnaf,keterangan) VALUES (?,?,?,?,?,?)",
                 (data['nama'], data.get('nik',''), data.get('no_hp',''),
                  data.get('alamat',''), data.get('asnaf',''), data.get('keterangan','')))
    conn.commit()
    conn.close()
    flash('Penerima manfaat berhasil ditambahkan.', 'success')
    return redirect(url_for('master_penerima'))

@app.route('/admin/master/penerima/edit/<int:id>', methods=['POST'])
@admin_required
def master_penerima_edit(id):
    data = request.form
    conn = get_db()
    conn.execute("UPDATE penerima_manfaat SET nama=?,nik=?,no_hp=?,alamat=?,asnaf=?,keterangan=? WHERE id=?",
                 (data['nama'], data.get('nik',''), data.get('no_hp',''),
                  data.get('alamat',''), data.get('asnaf',''), data.get('keterangan',''), id))
    conn.commit()
    conn.close()
    flash('Penerima manfaat diperbarui.', 'success')
    return redirect(url_for('master_penerima'))

@app.route('/admin/master/penerima/toggle/<int:id>', methods=['POST'])
@admin_required
def master_penerima_toggle(id):
    conn = get_db()
    conn.execute("UPDATE penerima_manfaat SET aktif = CASE WHEN aktif=1 THEN 0 ELSE 1 END WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('master_penerima'))

# ── Marketing (Mobile) ────────────────────────────────────────────────────────

@app.route('/marketing')
@login_required
def marketing_dashboard():
    conn = get_db()
    bulan = date.today().strftime('%Y-%m')
    total_masuk_bulan = conn.execute(
        "SELECT COALESCE(SUM(jumlah),0) FROM transaksi WHERE jenis='masuk' AND strftime('%Y-%m',tanggal)=? AND user_id=?",
        (bulan, session['user_id'])
    ).fetchone()[0]
    transaksi_hari = conn.execute('''
        SELECT t.*, c.nama as coa_nama, c.jenis_dana, d.nama as donatur_nama
        FROM transaksi t
        LEFT JOIN chart_of_accounts c ON t.coa_id=c.id
        LEFT JOIN donatur d ON t.donatur_id=d.id
        WHERE t.user_id=? AND t.tanggal=?
        ORDER BY t.created_at DESC
    ''', (session['user_id'], date.today().isoformat())).fetchall()
    conn.close()
    return render_template('marketing/dashboard.html',
        total_masuk_bulan=total_masuk_bulan, transaksi_hari=transaksi_hari,
        hari_ini=date.today().strftime('%d %B %Y'))

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
            if row:
                jenis_dana = row['jenis_dana']
        conn.execute('''
            INSERT INTO transaksi (tanggal,jenis,jenis_dana,coa_id,donatur_id,penerima_id,jumlah,keterangan,user_id)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            data['tanggal'], data['jenis'], jenis_dana, coa_id,
            data.get('donatur_id') or None, data.get('penerima_id') or None,
            float(data['jumlah'].replace('.', '').replace(',', '')),
            data.get('keterangan', ''), session['user_id']
        ))
        conn.commit()
        conn.close()
        flash('Transaksi berhasil dicatat!', 'success')
        return redirect(url_for('marketing_dashboard'))

    coa_list = conn.execute(
        "SELECT * FROM chart_of_accounts WHERE jenis_transaksi IS NOT NULL AND aktif=1 ORDER BY kode"
    ).fetchall()
    donatur_list = conn.execute("SELECT * FROM donatur WHERE aktif=1 ORDER BY nama").fetchall()
    penerima_list = conn.execute("SELECT * FROM penerima_manfaat WHERE aktif=1 ORDER BY nama").fetchall()
    conn.close()
    return render_template('marketing/catat.html',
        coa_list=coa_list, donatur_list=donatur_list, penerima_list=penerima_list,
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
    total = sum(r['jumlah'] for r in transaksi if r['jenis'] == 'masuk')
    conn.close()
    return render_template('marketing/riwayat.html', transaksi=transaksi, bulan=bulan, total=total)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
