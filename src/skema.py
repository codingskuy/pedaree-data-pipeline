"""Skema event `pedaree.stok.v1` (PDR-DATA-003).

Selaras dengan payload penerima TitipO `POST /sinyal/pedaree-stok`
(`titipo-backend-service/docs/api/openapi.yaml`, skema `SinyalPedareeStok`).
Sinyal berupa anjuran restock saja; relevansi 48 jam; tidak pernah membuat
pesanan otomatis.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# Sumber sah 13 satuan baku: inventori/20-satuan-hortikultura.md (Pedaree-TownHall).
SATUAN_BAKU: tuple[str, ...] = (
    "gram", "kg", "ml", "liter", "sdm", "sdt", "pcs",
    "siung", "buah", "ikat", "batang", "bonggol", "lembar",
)

RELEVANSI_JAM = 48
DEDUP_JAM = 24


class JenisSinyal(str, Enum):
    STOK_MENIPIS = "stok.menipis"
    STOK_HABIS = "stok.habis"
    KEDALUWARSA_DEKAT = "kedaluwarsa.dekat"


class Satuan(str, Enum):
    GRAM = "gram"
    KG = "kg"
    ML = "ml"
    LITER = "liter"
    SDM = "sdm"
    SDT = "sdt"
    PCS = "pcs"
    SIUNG = "siung"
    BUAH = "buah"
    IKAT = "ikat"
    BATANG = "batang"
    BONGGOL = "bonggol"
    LEMBAR = "lembar"


class SinyalStok(BaseModel):
    """Payload sinyal stok; urutan field = urutan di kontrak TitipO."""

    model_config = ConfigDict(extra="forbid")

    jenis: JenisSinyal
    item_id: str = Field(min_length=1)
    tanggal: date
    item: str = Field(min_length=1)
    sisa: float = Field(ge=0)
    satuan: Satuan
    kedaluwarsa: date
    recipe_id: str | None = None  # ID resep Pawonee, boleh kosong

    @property
    def kunci_idempoten(self) -> str:
        """Kunci idempoten konsumen TitipO: `item_id + tanggal`."""
        return f"{self.item_id}|{self.tanggal.isoformat()}"


def masih_relevan(waktu_sinyal: datetime, sekarang: datetime) -> bool:
    """Anjuran relevan selama 48 jam sejak sinyal dibuat."""
    return sekarang - waktu_sinyal <= timedelta(hours=RELEVANSI_JAM)
