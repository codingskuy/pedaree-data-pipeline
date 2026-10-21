"""5 event analitik Pedaree (PDR-DATA-004), tabel `metrik/10-stockout-dan-waste.md` bab 4.

Properti mengikuti tabel metrik/10 (itemId, sisa, minimum, ...). BRD BR-304 menyebut
daftar properti yang lebih ringkas; tabel metrik/10 dipakai karena lebih rinci.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from src.skema import JenisSinyal

NAMA_EVENT = ("stok_menipis", "stok_habis", "buang_catat", "sinyal_titipo", "pakai_dari_resep")

Teks = Annotated[str, Field(min_length=1)]


class StatusKirim(str, Enum):
    DICATAT = "dicatat"  # TitipO 201
    DUPLIKAT = "duplikat"  # TitipO 200
    GAGAL = "gagal"  # masuk DLQ


class _Properti(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class PropStokMenipis(_Properti):
    itemId: Teks
    sisa: float = Field(ge=0)
    minimum: float = Field(ge=0)


class PropStokHabis(_Properti):
    itemId: Teks
    jamSejakMenipis: float = Field(ge=0)


class PropBuangCatat(_Properti):
    batchId: Teks
    jumlah: float = Field(gt=0)
    alasan: Teks


class PropSinyalTitipo(_Properti):
    itemId: Teks
    jenis: JenisSinyal
    statusKirim: StatusKirim


class PropPakaiDariResep(_Properti):
    resepId: Teks
    itemIds: list[Teks] = Field(min_length=1)


class EventAnalitik(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nama: str
    waktu: datetime
    properti: dict

    @field_validator("nama")
    @classmethod
    def _nama_terkunci(cls, v: str) -> str:
        if v not in NAMA_EVENT:
            raise ValueError(f"nama event tidak dikenal: {v}")
        return v

    @field_validator("waktu")
    @classmethod
    def _waktu_beraware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("waktu harus beraware zona")
        return v

    @field_serializer("waktu")
    def _waktu_rfc3339(self, v: datetime) -> str:
        return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bangun(nama: str, model: _Properti, waktu: datetime) -> EventAnalitik:
    return EventAnalitik(nama=nama, waktu=waktu, properti=model.model_dump(mode="json"))


def stok_menipis(item_id: str, sisa: float, minimum: float, waktu: datetime) -> EventAnalitik:
    return _bangun("stok_menipis", PropStokMenipis(itemId=item_id, sisa=sisa, minimum=minimum), waktu)


def stok_habis(item_id: str, jam_sejak_menipis: float, waktu: datetime) -> EventAnalitik:
    return _bangun("stok_habis", PropStokHabis(itemId=item_id, jamSejakMenipis=jam_sejak_menipis), waktu)


def buang_catat(batch_id: str, jumlah: float, alasan: str, waktu: datetime) -> EventAnalitik:
    return _bangun("buang_catat", PropBuangCatat(batchId=batch_id, jumlah=jumlah, alasan=alasan), waktu)


def sinyal_titipo(
    item_id: str, jenis: JenisSinyal, status_kirim: StatusKirim, waktu: datetime
) -> EventAnalitik:
    return _bangun(
        "sinyal_titipo",
        PropSinyalTitipo(itemId=item_id, jenis=jenis, statusKirim=status_kirim),
        waktu,
    )


def pakai_dari_resep(resep_id: str, item_ids: list[str], waktu: datetime) -> EventAnalitik:
    return _bangun("pakai_dari_resep", PropPakaiDariResep(resepId=resep_id, itemIds=item_ids), waktu)


class Penerbit(Protocol):
    def terbitkan(self, event: EventAnalitik) -> None: ...


class PenerbitMemori:
    def __init__(self) -> None:
        self.events: list[EventAnalitik] = []

    def terbitkan(self, event: EventAnalitik) -> None:
        self.events.append(event)


class PenerbitJsonl:
    """Menulis satu event per baris; tidak mengirim ke layanan eksternal."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def terbitkan(self, event: EventAnalitik) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
