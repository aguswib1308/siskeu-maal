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
