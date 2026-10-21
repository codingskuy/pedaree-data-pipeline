"""Pekerja sinyal: sinyal stok Pedaree -> penyaringan dedup -> (PDR-DATA-002) TitipO."""
from __future__ import annotations

from datetime import datetime

from src.dedup import DedupProdusen
from src.skema import SinyalStok


def saring_sinyal(
    sinyal: SinyalStok, dedup: DedupProdusen, sekarang: datetime
) -> SinyalStok | None:
    """Kembalikan sinyal bila lolos dedup 24 jam, selain itu None. Tidak mencatat."""
    return sinyal if dedup.boleh_kirim(sinyal, sekarang) else None
