"""Uji skema event pedaree.stok.v1 (PDR-DATA-003)."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.skema import SATUAN_BAKU, JenisSinyal, SinyalStok

SKEMA_JSON = Path(__file__).parent.parent / "schemas" / "event-stok-v1.json"

SATUAN_13 = {
    "gram", "kg", "ml", "liter", "sdm", "sdt", "pcs",
    "siung", "buah", "ikat", "batang", "bonggol", "lembar",
}


def contoh(**ubah):
    data = {
        "jenis": "stok.menipis",
        "item_id": "itm_01J9ZZ",
        "tanggal": "2026-10-14",
        "item": "Cabai merah",
        "sisa": 150,
        "satuan": "gram",
        "kedaluwarsa": "2026-10-17",
        "recipe_id": None,
    }
    data.update(ubah)
    return data


def test_tiga_jenis_terkunci():
    assert {j.value for j in JenisSinyal} == {"stok.menipis", "stok.habis", "kedaluwarsa.dekat"}


def test_satuan_baku_tepat_13():
    assert set(SATUAN_BAKU) == SATUAN_13
    assert len(SATUAN_BAKU) == 13


def test_payload_valid_diterima():
    s = SinyalStok.model_validate(contoh())
    assert s.jenis is JenisSinyal.STOK_MENIPIS
    assert s.recipe_id is None


def test_recipe_id_boleh_dihilangkan():
    data = contoh()
    del data["recipe_id"]
    assert SinyalStok.model_validate(data).recipe_id is None


@pytest.mark.parametrize("wajib", ["jenis", "item_id", "tanggal", "item", "sisa", "satuan", "kedaluwarsa"])
def test_field_wajib(wajib):
    data = contoh()
    del data[wajib]
    with pytest.raises(ValidationError):
        SinyalStok.model_validate(data)


@pytest.mark.parametrize("ubah", [
    {"jenis": "stok.rusak"},
    {"jenis": "pesanan.dibuat"},
    {"satuan": "butir"},
    {"satuan": "g"},
    {"sisa": -1},
    {"tanggal": "14-10-2026"},
    {"item_id": ""},
    {"item": ""},
])
def test_nilai_tak_valid_ditolak(ubah):
    with pytest.raises(ValidationError):
        SinyalStok.model_validate(contoh(**ubah))


def test_field_lama_event_ditolak():
    data = contoh()
    data["event"] = data.pop("jenis")
    with pytest.raises(ValidationError):
        SinyalStok.model_validate(data)


def test_kunci_idempoten_item_id_jenis_tanggal():
    s = SinyalStok.model_validate(contoh())
    assert s.kunci_idempoten == f"itm_01J9ZZ|{s.jenis.value}|2026-10-14"


def test_kunci_idempoten_berbeda_untuk_jenis_berbeda():
    a = SinyalStok.model_validate({**contoh(), "jenis": "stok.menipis"})
    b = SinyalStok.model_validate({**contoh(), "jenis": "stok.habis"})
    assert a.kunci_idempoten != b.kunci_idempoten


def test_payload_wire_cocok_openapi_titipo():
    wire = SinyalStok.model_validate(contoh()).model_dump(mode="json")
    assert set(wire) == {
        "jenis", "item_id", "tanggal", "item", "sisa", "satuan", "kedaluwarsa", "recipe_id",
    }
    assert wire["tanggal"] == "2026-10-14"
    assert wire["jenis"] == "stok.menipis"


def test_skema_json_selaras_model():
    skema = json.loads(SKEMA_JSON.read_text())
    props = skema["properties"]
    assert set(skema["required"]) == {
        "jenis", "item_id", "tanggal", "item", "sisa", "satuan", "kedaluwarsa",
    }
    assert set(props) == set(SinyalStok.model_fields)
    assert set(props["jenis"]["enum"]) == {j.value for j in JenisSinyal}
    assert set(props["satuan"]["enum"]) == SATUAN_13
    assert props["recipe_id"]["type"] == ["string", "null"]
    assert skema["additionalProperties"] is False
    assert "48 jam" in skema["description"]
