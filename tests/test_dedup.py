"""Uji dedup produsen: maks 1 sinyal per item per jenis per 24 jam (BR-301)."""
from datetime import datetime, timedelta, timezone

from src.dedup import DedupProdusen
from src.skema import JenisSinyal, SinyalStok

T0 = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)


def sinyal(item_id="itm_1", jenis="stok.menipis", tanggal="2026-10-14"):
    return SinyalStok.model_validate({
        "jenis": jenis, "item_id": item_id, "tanggal": tanggal, "item": "Cabai",
        "sisa": 10, "satuan": "gram", "kedaluwarsa": "2026-10-20",
    })


def test_sinyal_pertama_boleh_kirim():
    assert DedupProdusen().boleh_kirim(sinyal(), T0)


def test_duplikat_dalam_24_jam_ditahan():
    d = DedupProdusen()
    d.catat(sinyal(), T0)
    assert not d.boleh_kirim(sinyal(), T0 + timedelta(hours=23, minutes=59))


def test_tepat_24_jam_boleh_lagi():
    d = DedupProdusen()
    d.catat(sinyal(), T0)
    assert d.boleh_kirim(sinyal(), T0 + timedelta(hours=24))


def test_item_berbeda_independen():
    d = DedupProdusen()
    d.catat(sinyal("itm_1"), T0)
    assert d.boleh_kirim(sinyal("itm_2"), T0 + timedelta(hours=1))


def test_menipis_lalu_habis_masing_masing_1_per_24_jam():
    d = DedupProdusen()
    d.catat(sinyal(jenis="stok.menipis"), T0)
    assert d.boleh_kirim(sinyal(jenis="stok.habis"), T0 + timedelta(hours=2))
    d.catat(sinyal(jenis="stok.habis"), T0 + timedelta(hours=2))
    assert not d.boleh_kirim(sinyal(jenis="stok.habis"), T0 + timedelta(hours=3))


def test_hanya_catat_tidak_memajukan_jendela_saat_ditahan():
    d = DedupProdusen()
    d.catat(sinyal(), T0)
    assert not d.boleh_kirim(sinyal(), T0 + timedelta(hours=20))
    # penahanan tidak memperpanjang jendela: 24 jam dihitung dari sinyal terkirim terakhir
    assert d.boleh_kirim(sinyal(), T0 + timedelta(hours=24))


def test_waktu_naive_ditolak():
    import pytest
    with pytest.raises(ValueError):
        DedupProdusen().boleh_kirim(sinyal(), datetime(2026, 10, 14, 8, 0))


def test_relevansi_48_jam():
    from src.skema import RELEVANSI_JAM, masih_relevan
    assert RELEVANSI_JAM == 48
    s = sinyal()
    assert masih_relevan(T0, T0 + timedelta(hours=48))
    assert not masih_relevan(T0, T0 + timedelta(hours=48, seconds=1))
    assert s.jenis is JenisSinyal.STOK_MENIPIS


def test_saring_sinyal_meneruskan_lalu_menahan():
    from src.pekerja_sinyal import saring_sinyal
    d = DedupProdusen()
    s = sinyal()
    assert saring_sinyal(s, d, T0) is s
    d.catat(s, T0)
    assert saring_sinyal(s, d, T0 + timedelta(hours=1)) is None


def test_menipis_0800_lalu_habis_1900_dua_sinyal_dengan_kunci_berbeda():
    d = DedupProdusen()
    menipis = sinyal(jenis="stok.menipis")
    habis = sinyal(jenis="stok.habis")
    assert d.boleh_kirim(menipis, T0)
    d.catat(menipis, T0)
    sore = T0.replace(hour=19)
    assert d.boleh_kirim(habis, sore)
    d.catat(habis, sore)
    assert menipis.kunci_idempoten != habis.kunci_idempoten


def test_jenis_sama_dalam_24_jam_tetap_ditekan():
    d = DedupProdusen()
    d.catat(sinyal(jenis="stok.habis"), T0)
    assert not d.boleh_kirim(sinyal(jenis="stok.habis"), T0.replace(hour=19))
    assert not d.boleh_kirim(sinyal(jenis="stok.habis"), T0 + timedelta(hours=23))
