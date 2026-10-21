"""Uji klien TitipO POST /sinyal/pedaree-stok (PDR-DATA-002)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from src.dedup import DedupProdusen
from src.dlq import DlqBerkas
from src.klien_titipo import JEDA_RETRY_DETIK, HasilKirim, KlienTitipo, muat_konfigurasi
from src.pekerja_sinyal import HasilProses, proses_sinyal
from src.skema import SinyalStok

KUNCI = "kunci-rahasia-uji"
T0 = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)


def sinyal(item_id="itm_1", jenis="stok.menipis"):
    return SinyalStok.model_validate({
        "jenis": jenis, "item_id": item_id, "tanggal": "2026-10-14", "item": "Cabai merah",
        "sisa": 150, "satuan": "gram", "kedaluwarsa": "2026-10-17", "recipe_id": "rsp_9",
    })


class Rekam:
    """Transport tiruan: jawaban berurutan, merekam semua permintaan."""

    def __init__(self, *jawaban):
        self.jawaban = list(jawaban)
        self.permintaan: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.permintaan.append(request)
        j = self.jawaban.pop(0) if len(self.jawaban) > 1 else self.jawaban[0]
        if isinstance(j, Exception):
            raise j
        return j


def klien(rekam, tmp_path, tidur=None):
    tidur_list = [] if tidur is None else tidur
    dlq = DlqBerkas(tmp_path / "dlq.jsonl")
    c = KlienTitipo(
        "https://titipo.example", KUNCI,
        client=httpx.Client(transport=httpx.MockTransport(rekam)),
        dlq=dlq, tidur=tidur_list.append,
    )
    return c, dlq, tidur_list


def resp(kode, status=None):
    return httpx.Response(kode, json={"status": status} if status else {"kode": "X", "pesan": "x"})


def test_201_dicatat_sebagai_anjuran(tmp_path):
    rekam = Rekam(resp(201, "dicatat_sebagai_anjuran"))
    c, dlq, tidur = klien(rekam, tmp_path)
    assert c.kirim(sinyal()) is HasilKirim.DICATAT
    assert tidur == [] and dlq.baca() == []


def test_200_duplikat_diabaikan_bukan_galat(tmp_path):
    rekam = Rekam(resp(200, "duplikat_diabaikan"))
    c, dlq, tidur = klien(rekam, tmp_path)
    assert c.kirim(sinyal()) is HasilKirim.DUPLIKAT
    assert len(rekam.permintaan) == 1 and dlq.baca() == []


def test_request_header_metode_path_dan_body(tmp_path):
    rekam = Rekam(resp(201, "dicatat_sebagai_anjuran"))
    c, _, _ = klien(rekam, tmp_path)
    c.kirim(sinyal())
    r = rekam.permintaan[0]
    assert r.method == "POST"
    assert str(r.url) == "https://titipo.example/sinyal/pedaree-stok"
    assert r.headers["X-Service-Key"] == KUNCI
    assert "authorization" not in r.headers
    assert r.headers["X-Idempotency-Key"] == "itm_1|stok.menipis|2026-10-14"
    body = json.loads(r.content)
    assert body == {
        "jenis": "stok.menipis", "item_id": "itm_1", "tanggal": "2026-10-14",
        "item": "Cabai merah", "sisa": 150.0, "satuan": "gram",
        "kedaluwarsa": "2026-10-17", "recipe_id": "rsp_9",
    }


@pytest.mark.parametrize("jenis", ["stok.menipis", "stok.habis", "kedaluwarsa.dekat"])
def test_tiga_jenis_terkirim(tmp_path, jenis):
    rekam = Rekam(resp(201, "dicatat_sebagai_anjuran"))
    c, _, _ = klien(rekam, tmp_path)
    assert c.kirim(sinyal(jenis=jenis)) is HasilKirim.DICATAT
    assert json.loads(rekam.permintaan[0].content)["jenis"] == jenis


def test_jeda_retry_5_30_300():
    assert JEDA_RETRY_DETIK == (5, 30, 300)


def test_retry_3x_lalu_sukses(tmp_path):
    rekam = Rekam(resp(500), httpx.ConnectError("putus"), resp(503), resp(201, "dicatat_sebagai_anjuran"))
    c, dlq, tidur = klien(rekam, tmp_path)
    assert c.kirim(sinyal()) is HasilKirim.DICATAT
    assert len(rekam.permintaan) == 4
    assert tidur == [5, 30, 300]
    assert dlq.baca() == []


def test_gagal_terus_masuk_dlq_setelah_3_retry(tmp_path):
    rekam = Rekam(resp(500))
    c, dlq, tidur = klien(rekam, tmp_path)
    assert c.kirim(sinyal()) is HasilKirim.GAGAL_DLQ
    assert len(rekam.permintaan) == 4  # 1 awal + 3 retry
    assert tidur == [5, 30, 300]
    isi = dlq.baca()
    assert len(isi) == 1
    assert isi[0]["sinyal"]["item_id"] == "itm_1"
    assert isi[0]["percobaan"] == 4
    assert "500" in isi[0]["alasan"]


def test_429_dan_timeout_diretry(tmp_path):
    rekam = Rekam(resp(429), httpx.ReadTimeout("lambat"), resp(200, "duplikat_diabaikan"))
    c, _, tidur = klien(rekam, tmp_path)
    assert c.kirim(sinyal()) is HasilKirim.DUPLIKAT
    assert tidur == [5, 30]


@pytest.mark.parametrize("kode", [400, 401, 403, 422])
def test_galat_klien_tidak_diretry_langsung_dlq(tmp_path, kode):
    rekam = Rekam(resp(kode))
    c, dlq, tidur = klien(rekam, tmp_path)
    assert c.kirim(sinyal()) is HasilKirim.GAGAL_DLQ
    assert len(rekam.permintaan) == 1 and tidur == []
    assert str(kode) in dlq.baca()[0]["alasan"]


def test_kunci_layanan_tidak_bocor_ke_dlq_atau_repr(tmp_path):
    rekam = Rekam(resp(401))
    c, dlq, _ = klien(rekam, tmp_path)
    c.kirim(sinyal())
    assert KUNCI not in (tmp_path / "dlq.jsonl").read_text()
    assert KUNCI not in repr(c)


def test_hanya_satu_endpoint_dan_tidak_ada_jalur_pesanan(tmp_path):
    rekam = Rekam(resp(201, "dicatat_sebagai_anjuran"))
    c, _, _ = klien(rekam, tmp_path)
    c.kirim(sinyal())
    assert {(r.method, r.url.path) for r in rekam.permintaan} == {("POST", "/sinyal/pedaree-stok")}
    for berkas in (Path("src").glob("*.py")):
        teks = berkas.read_text().lower()
        assert "/pesanan" not in teks and "/orders" not in teks, berkas


def test_muat_konfigurasi_wajib_kunci(monkeypatch):
    monkeypatch.delenv("PEDAREE_SERVICE_KEY", raising=False)
    monkeypatch.setenv("TITIPO_BASE_URL", "https://titipo.example")
    with pytest.raises(RuntimeError):
        muat_konfigurasi()
    monkeypatch.setenv("PEDAREE_SERVICE_KEY", KUNCI)
    k = muat_konfigurasi()
    assert k.base_url == "https://titipo.example" and k.service_key == KUNCI
    assert KUNCI not in repr(k)


# --- integrasi pekerja: dedup + kirim ---

def test_proses_sinyal_kirim_lalu_tahan_duplikat_24_jam(tmp_path):
    rekam = Rekam(resp(201, "dicatat_sebagai_anjuran"))
    c, _, _ = klien(rekam, tmp_path)
    d = DedupProdusen()
    assert proses_sinyal(sinyal(), d, c, T0) is HasilProses.DICATAT
    assert proses_sinyal(sinyal(), d, c, T0.replace(hour=20)) is HasilProses.DITAHAN_DEDUP
    assert len(rekam.permintaan) == 1


def test_proses_sinyal_gagal_tidak_mengunci_dedup(tmp_path):
    rekam = Rekam(resp(500))
    c, _, _ = klien(rekam, tmp_path)
    d = DedupProdusen()
    assert proses_sinyal(sinyal(), d, c, T0) is HasilProses.GAGAL_DLQ
    assert d.boleh_kirim(sinyal(), T0)


def test_proses_sinyal_duplikat_konsumen_tetap_dicatat_dedup(tmp_path):
    rekam = Rekam(resp(200, "duplikat_diabaikan"))
    c, _, _ = klien(rekam, tmp_path)
    d = DedupProdusen()
    assert proses_sinyal(sinyal(), d, c, T0) is HasilProses.DUPLIKAT_KONSUMEN
    assert not d.boleh_kirim(sinyal(), T0.replace(hour=9))


def test_kunci_idempoten_header_berbeda_untuk_jenis_berbeda(tmp_path):
    rekam = Rekam(resp(201, "dicatat_sebagai_anjuran"), resp(201, "dicatat_sebagai_anjuran"))
    c, _, _ = klien(rekam, tmp_path)
    c.kirim(sinyal(jenis="stok.menipis"))
    c.kirim(sinyal(jenis="stok.habis"))
    k = [r.headers["X-Idempotency-Key"] for r in rekam.permintaan]
    assert k[0] != k[1] and k[1].endswith("|2026-10-14") and "stok.habis" in k[1]
