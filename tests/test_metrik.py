"""Uji agregat stockoutRate, waste, median jam (PDR-DATA-004; metrik/10 bab 2)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from src.metrik import (
    WIB,
    Buang,
    ItemStatus,
    Transisi,
    hitung_waste,
    median_jam_menipis_ke_habis,
    stockout_rate,
    waktu_hitung_stockout,
)

UTC = timezone.utc


def wib(*a):
    return datetime(*a, tzinfo=WIB)


# --- stockoutRate ---

def test_stockout_rate_rumus():
    items = [ItemStatus(f"i{n}", aktif=True, habis=(n < 2)) for n in range(10)]
    assert stockout_rate(items) == 20.0


def test_stockout_rate_abaikan_item_diarsip():
    items = [
        ItemStatus("a", aktif=True, habis=True),
        ItemStatus("b", aktif=True, habis=False),
        ItemStatus("c", aktif=False, habis=True),  # arsip tidak dihitung
    ]
    assert stockout_rate(items) == 50.0


def test_stockout_rate_tanpa_item_aktif_nol():
    assert stockout_rate([]) == 0.0
    assert stockout_rate([ItemStatus("a", aktif=False, habis=True)]) == 0.0


def test_stockout_rate_tidak_dibulatkan_diam_diam():
    items = [ItemStatus("a", True, True)] + [ItemStatus(f"x{i}", True, False) for i in range(2)]
    assert stockout_rate(items) == pytest.approx(100 / 3)


def test_waktu_hitung_harian_2359_wib():
    w = waktu_hitung_stockout(date(2026, 10, 14))
    assert w == wib(2026, 10, 14, 23, 59)
    assert w.astimezone(UTC) == datetime(2026, 10, 14, 16, 59, tzinfo=UTC)


# --- waste ---

def b(household="hh_1", komoditas="Bayam", jumlah=1, satuan="ikat", waktu=None, **kw):
    return Buang(household, komoditas, jumlah, satuan, waktu or wib(2026, 10, 5, 10, 0), **kw)


def test_waste_gram_konversi_satuan():
    hasil = hitung_waste([
        b(komoditas="Beras", jumlah=1, satuan="kg"),       # 1000 g
        b(komoditas="Minyak", jumlah=3, satuan="sdm"),     # 45 ml
        b(komoditas="Bayam", jumlah=2, satuan="ikat"),     # 400 g (bobot acuan)
        b(komoditas="Tomat", jumlah=6, satuan="buah"),     # 480 g
        b(komoditas="Gula", jumlah=2, satuan="sdt"),       # 10 ml
        b(komoditas="Minyak", jumlah=0.5, satuan="liter"),  # 500 ml
    ])
    r = hasil[("hh_1", "2026-10")]
    assert r.waste_gram == 1000 + 45 + 400 + 480 + 10 + 500


def test_waste_rupiah_harga_acuan_br302():
    hasil = hitung_waste([
        b(komoditas="Beras", jumlah=500, satuan="gram"),       # 0,5 kg x 12.000 = 6.000
        b(komoditas="Telur", jumlah=2, satuan="pcs"),          # 5.000
        b(komoditas="Cabai Merah", jumlah=100, satuan="gram"),  # 6.000
        b(komoditas="Bayam", jumlah=2, satuan="ikat"),         # 6.000
        b(komoditas="Minyak", jumlah=250, satuan="ml"),        # 0,25 L x 22.000 = 5.500
        b(komoditas="Kangkung", jumlah=100, satuan="gram"),    # 0,5 ikat x 3.000 = 1.500
    ])
    assert hasil[("hh_1", "2026-10")].waste_rupiah == 6000 + 5000 + 6000 + 6000 + 5500 + 1500


def test_waste_rupiah_pakai_harga_parcel_titipo_bila_ada():
    # beli 2 kg seharga Rp30.000; buang 500 g -> 7.500 (bukan acuan Rp12.000/kg = 6.000)
    hasil = hitung_waste([
        b(komoditas="Beras", jumlah=500, satuan="gram",
          beli_jumlah=2, beli_satuan="kg", beli_harga=30000),
    ])
    assert hasil[("hh_1", "2026-10")].waste_rupiah == 7500


def test_waste_rupiah_komoditas_tanpa_harga_dicatat_bukan_dikarang():
    hasil = hitung_waste([b(komoditas="Kemangi", jumlah=1, satuan="ikat")])
    r = hasil[("hh_1", "2026-10")]
    assert r.waste_rupiah == 0
    assert r.baris_tanpa_harga == 1
    assert r.waste_gram == 50


def test_waste_pcs_tanpa_bobot_tidak_masuk_gram_tapi_dicatat():
    hasil = hitung_waste([b(komoditas="Telur", jumlah=2, satuan="pcs")])
    r = hasil[("hh_1", "2026-10")]
    assert r.waste_gram == 0
    assert r.baris_tak_terkonversi == 1
    assert r.waste_rupiah == 5000


def test_waste_bulanan_wib_batas_bulan():
    # 2026-10-31 17:30 UTC = 2026-11-01 00:30 WIB -> masuk November
    di_utc = datetime(2026, 10, 31, 17, 30, tzinfo=UTC)
    # 2026-10-31 16:59 UTC = 2026-10-31 23:59 WIB -> masih Oktober
    akhir_okt = datetime(2026, 10, 31, 16, 59, tzinfo=UTC)
    hasil = hitung_waste([
        b(komoditas="Beras", jumlah=100, satuan="gram", waktu=di_utc),
        b(komoditas="Beras", jumlah=200, satuan="gram", waktu=akhir_okt),
    ])
    assert hasil[("hh_1", "2026-11")].waste_gram == 100
    assert hasil[("hh_1", "2026-10")].waste_gram == 200


def test_waste_per_rumah_tangga():
    hasil = hitung_waste([
        b(household="hh_1", komoditas="Beras", jumlah=100, satuan="gram"),
        b(household="hh_2", komoditas="Beras", jumlah=300, satuan="gram"),
    ])
    assert hasil[("hh_1", "2026-10")].waste_gram == 100
    assert hasil[("hh_2", "2026-10")].waste_gram == 300


def test_waste_pembulatan_setengah_ke_atas_1_desimal_dan_rupiah_bulat():
    hasil = hitung_waste([b(komoditas="Beras", jumlah=0.25, satuan="gram")])  # 0.25 -> 0.3
    r = hasil[("hh_1", "2026-10")]
    assert r.waste_gram == 0.3
    assert isinstance(r.waste_rupiah, int)


def test_waste_waktu_naive_ditolak():
    with pytest.raises(ValueError):
        hitung_waste([Buang("hh", "Beras", 1, "kg", datetime(2026, 10, 5))])


def test_waste_satuan_tak_dikenal_ditolak():
    with pytest.raises(ValueError):
        hitung_waste([b(satuan="butir")])


# --- median jam MENIPIS -> HABIS ---

def test_median_jam_menipis_ke_habis():
    t = wib(2026, 10, 1, 8, 0)
    transisi = [
        Transisi("i1", "MENIPIS", t),
        Transisi("i1", "HABIS", t + timedelta(hours=10)),
        Transisi("i1", "MENIPIS", t + timedelta(days=2)),
        Transisi("i1", "HABIS", t + timedelta(days=2, hours=30)),
        Transisi("i1", "MENIPIS", t + timedelta(days=5)),
        Transisi("i1", "HABIS", t + timedelta(days=5, hours=20)),
    ]
    assert median_jam_menipis_ke_habis(transisi)[("i1", "2026-10")] == 20.0


def test_median_genap_rata_rata_dua_tengah():
    t = wib(2026, 10, 1, 8, 0)
    transisi = [
        Transisi("i1", "MENIPIS", t), Transisi("i1", "HABIS", t + timedelta(hours=10)),
        Transisi("i1", "MENIPIS", t + timedelta(days=1)),
        Transisi("i1", "HABIS", t + timedelta(days=1, hours=20)),
    ]
    assert median_jam_menipis_ke_habis(transisi)[("i1", "2026-10")] == 15.0


def test_median_per_item_dan_urutan_masukan_bebas():
    t = wib(2026, 10, 1, 8, 0)
    transisi = [
        Transisi("i2", "HABIS", t + timedelta(hours=5)),
        Transisi("i1", "HABIS", t + timedelta(hours=7)),
        Transisi("i2", "MENIPIS", t),
        Transisi("i1", "MENIPIS", t),
    ]
    hasil = median_jam_menipis_ke_habis(transisi)
    assert hasil[("i1", "2026-10")] == 7.0
    assert hasil[("i2", "2026-10")] == 5.0


def test_median_habis_tanpa_menipis_dan_menipis_pulih_diabaikan():
    t = wib(2026, 10, 1, 8, 0)
    transisi = [
        Transisi("i1", "HABIS", t),                       # tanpa MENIPIS sebelumnya
        Transisi("i2", "MENIPIS", t),
        Transisi("i2", "AMAN", t + timedelta(hours=3)),   # pulih sebelum habis
        Transisi("i2", "HABIS", t + timedelta(hours=9)),  # tidak berpasangan
    ]
    assert median_jam_menipis_ke_habis(transisi) == {}


def test_median_bulan_mengikuti_waktu_habis_wib():
    t = wib(2026, 10, 31, 20, 0)
    transisi = [Transisi("i1", "MENIPIS", t), Transisi("i1", "HABIS", t + timedelta(hours=6))]
    assert ("i1", "2026-11") in median_jam_menipis_ke_habis(transisi)
