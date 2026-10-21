"""Klien HTTP ke TitipO `POST /sinyal/pedaree-stok` (PDR-DATA-002).

Hanya satu endpoint yang dipanggil: sinyal anjuran restock. Tidak ada jalur
pembuatan pesanan. Kunci layanan hanya dikirim sebagai header `X-Service-Key`
dan tidak pernah masuk log, DLQ, atau repr.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import httpx

from src.dlq import Dlq, DlqBerkas
from src.skema import SinyalStok

PATH_SINYAL = "/sinyal/pedaree-stok"
JEDA_RETRY_DETIK: tuple[int, ...] = (5, 30, 300)  # 3 retry setelah percobaan pertama
TIMEOUT_DETIK = 10.0


class HasilKirim(str, Enum):
    DICATAT = "dicatat_sebagai_anjuran"  # 201
    DUPLIKAT = "duplikat_diabaikan"  # 200
    GAGAL_DLQ = "gagal_dlq"


@dataclass(frozen=True)
class Konfigurasi:
    base_url: str
    service_key: str = field(repr=False)
    dlq_path: str = "dlq-sinyal.jsonl"


def muat_konfigurasi() -> Konfigurasi:
    kunci = os.environ.get("PEDAREE_SERVICE_KEY")
    if not kunci:
        raise RuntimeError("PEDAREE_SERVICE_KEY wajib diisi (jangan commit ke repo)")
    return Konfigurasi(
        base_url=os.environ.get("TITIPO_BASE_URL", "http://localhost:8080"),
        service_key=kunci,
        dlq_path=os.environ.get("PEDAREE_DLQ_PATH", "dlq-sinyal.jsonl"),
    )


class KlienTitipo:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        *,
        dlq: Dlq,
        client: httpx.Client | None = None,
        tidur: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._client = client or httpx.Client(timeout=TIMEOUT_DETIK)
        self._dlq = dlq
        self._tidur = tidur

    def __repr__(self) -> str:
        return f"KlienTitipo(base_url={self._base_url!r})"

    @classmethod
    def dari_konfigurasi(cls, k: Konfigurasi) -> "KlienTitipo":
        return cls(k.base_url, k.service_key, dlq=DlqBerkas(k.dlq_path))

    def kirim(self, sinyal: SinyalStok) -> HasilKirim:
        """Kirim satu sinyal; retry 5/30/300 dtk untuk galat sementara, lalu DLQ."""
        percobaan = 0
        alasan = ""
        while True:
            percobaan += 1
            try:
                r = self._client.post(
                    self._base_url + PATH_SINYAL,
                    json=sinyal.model_dump(mode="json"),
                    headers={"X-Service-Key": self._service_key},
                )
            except httpx.TransportError as e:
                alasan = f"galat jaringan: {type(e).__name__}"
            else:
                if r.status_code == 201:
                    return HasilKirim.DICATAT
                if r.status_code == 200:
                    return HasilKirim.DUPLIKAT
                alasan = f"HTTP {r.status_code}"
                if not (r.status_code >= 500 or r.status_code == 429):
                    return self._ke_dlq(sinyal, alasan, percobaan)  # galat permanen
            if percobaan > len(JEDA_RETRY_DETIK):
                return self._ke_dlq(sinyal, alasan, percobaan)
            self._tidur(JEDA_RETRY_DETIK[percobaan - 1])

    def _ke_dlq(self, sinyal: SinyalStok, alasan: str, percobaan: int) -> HasilKirim:
        self._dlq.tambah(sinyal, alasan, percobaan)
        return HasilKirim.GAGAL_DLQ
