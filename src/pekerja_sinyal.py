"""Pekerja sinyal: sinyal stok Pedaree -> dedup 24 jam -> TitipO (anjuran saja).

Masukan CLI: JSON Lines `SinyalStok` di stdin (`python -m src.pekerja_sinyal < sinyal.jsonl`).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from enum import Enum

from src.dedup import DedupProdusen
from src.klien_titipo import HasilKirim, KlienTitipo, muat_konfigurasi
from src.skema import SinyalStok


class HasilProses(str, Enum):
    DICATAT = "dicatat"
    DUPLIKAT_KONSUMEN = "duplikat_konsumen"
    DITAHAN_DEDUP = "ditahan_dedup"
    GAGAL_DLQ = "gagal_dlq"


def saring_sinyal(
    sinyal: SinyalStok, dedup: DedupProdusen, sekarang: datetime
) -> SinyalStok | None:
    """Kembalikan sinyal bila lolos dedup 24 jam, selain itu None. Tidak mencatat."""
    return sinyal if dedup.boleh_kirim(sinyal, sekarang) else None


def proses_sinyal(
    sinyal: SinyalStok, dedup: DedupProdusen, klien: KlienTitipo, sekarang: datetime
) -> HasilProses:
    """Dedup, kirim, lalu catat dedup hanya bila TitipO menerima (201/200)."""
    if saring_sinyal(sinyal, dedup, sekarang) is None:
        return HasilProses.DITAHAN_DEDUP
    hasil = klien.kirim(sinyal)
    if hasil is HasilKirim.GAGAL_DLQ:
        return HasilProses.GAGAL_DLQ
    dedup.catat(sinyal, sekarang)
    return HasilProses.DICATAT if hasil is HasilKirim.DICATAT else HasilProses.DUPLIKAT_KONSUMEN


def main() -> int:
    klien = KlienTitipo.dari_konfigurasi(muat_konfigurasi())
    dedup = DedupProdusen()
    for baris in sys.stdin:
        if not baris.strip():
            continue
        sinyal = SinyalStok.model_validate_json(baris)
        hasil = proses_sinyal(sinyal, dedup, klien, datetime.now(timezone.utc))
        print(f"{sinyal.item_id} {sinyal.jenis.value} {hasil.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
