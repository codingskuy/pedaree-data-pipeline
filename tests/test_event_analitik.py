"""Uji 5 event analitik (metrik/10 bab 4)."""
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.dedup import DedupProdusen
from src.event_analitik import (
    NAMA_EVENT,
    PenerbitJsonl,
    PenerbitMemori,
    StatusKirim,
    buang_catat,
    pakai_dari_resep,
    sinyal_titipo,
    stok_habis,
    stok_menipis,
)
from src.klien_titipo import HasilKirim
from src.pekerja_sinyal import HasilProses, proses_sinyal
from src.skema import JenisSinyal, SinyalStok

T0 = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)


def test_lima_nama_event_terkunci():
    assert set(NAMA_EVENT) == {
        "stok_menipis", "stok_habis", "buang_catat", "sinyal_titipo", "pakai_dari_resep",
    }


def test_properti_sesuai_tabel():
    assert stok_menipis("itm_1", 150, 250, T0).properti == {"itemId": "itm_1", "sisa": 150, "minimum": 250}
    assert stok_habis("itm_1", 36.5, T0).properti == {"itemId": "itm_1", "jamSejakMenipis": 36.5}
    assert buang_catat("btc_1", 120, "kedaluwarsa", T0).properti == {
        "batchId": "btc_1", "jumlah": 120, "alasan": "kedaluwarsa",
    }
    assert sinyal_titipo("itm_1", JenisSinyal.STOK_HABIS, StatusKirim.DICATAT, T0).properti == {
        "itemId": "itm_1", "jenis": "stok.habis", "statusKirim": "dicatat",
    }
    assert pakai_dari_resep("rsp_1", ["itm_1", "itm_2"], T0).properti == {
        "resepId": "rsp_1", "itemIds": ["itm_1", "itm_2"],
    }


def test_nama_dan_waktu_rfc3339_utc():
    e = stok_menipis("itm_1", 1, 2, T0)
    assert e.nama == "stok_menipis"
    assert e.model_dump(mode="json")["waktu"] == "2026-10-14T08:00:00Z"


def test_validasi_ketat():
    with pytest.raises(ValidationError):
        stok_menipis("", 1, 2, T0)
    with pytest.raises(ValidationError):
        stok_menipis("itm_1", -1, 2, T0)
    with pytest.raises(ValidationError):
        stok_habis("itm_1", -3, T0)
    with pytest.raises(ValidationError):
        buang_catat("btc_1", 0, "x", T0)
    with pytest.raises(ValidationError):
        pakai_dari_resep("rsp_1", [], T0)
    with pytest.raises(ValueError):
        stok_menipis("itm_1", 1, 2, datetime(2026, 10, 14, 8, 0))


def test_penerbit_jsonl_dan_memori(tmp_path):
    p = PenerbitJsonl(tmp_path / "analitik.jsonl")
    m = PenerbitMemori()
    for pen in (p, m):
        pen.terbitkan(stok_menipis("itm_1", 1, 2, T0))
        pen.terbitkan(stok_habis("itm_1", 4, T0))
    baris = [json.loads(x) for x in (tmp_path / "analitik.jsonl").read_text().splitlines()]
    assert [x["nama"] for x in baris] == ["stok_menipis", "stok_habis"]
    assert [e.nama for e in m.events] == ["stok_menipis", "stok_habis"]


def sinyal():
    return SinyalStok.model_validate({
        "jenis": "stok.menipis", "item_id": "itm_1", "tanggal": "2026-10-14", "item": "Cabai",
        "sisa": 10, "satuan": "gram", "kedaluwarsa": "2026-10-20",
    })


class KlienPalsu:
    def __init__(self, hasil):
        self.hasil = hasil

    def kirim(self, s):
        return self.hasil


@pytest.mark.parametrize("hasil,status", [
    (HasilKirim.DICATAT, "dicatat"),
    (HasilKirim.DUPLIKAT, "duplikat"),
    (HasilKirim.GAGAL_DLQ, "gagal"),
])
def test_pekerja_menerbitkan_sinyal_titipo_dengan_status_kirim(hasil, status):
    m = PenerbitMemori()
    proses_sinyal(sinyal(), DedupProdusen(), KlienPalsu(hasil), T0, penerbit=m)
    assert [e.properti["statusKirim"] for e in m.events] == [status]
    assert m.events[0].nama == "sinyal_titipo"


def test_pekerja_tidak_menerbitkan_saat_ditahan_dedup():
    m = PenerbitMemori()
    d = DedupProdusen()
    d.catat(sinyal(), T0)
    assert proses_sinyal(sinyal(), d, KlienPalsu(HasilKirim.DICATAT), T0, penerbit=m) is HasilProses.DITAHAN_DEDUP
    assert m.events == []
