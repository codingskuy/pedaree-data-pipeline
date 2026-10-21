"""Dedup produsen: maks 1 sinyal per item per jenis per 24 jam (BR-301)."""
from __future__ import annotations

from datetime import datetime, timedelta

from src.skema import DEDUP_JAM, SinyalStok


class DedupProdusen:
    """Penyimpanan dalam memori; cukup untuk satu proses pekerja.

    Penahanan tidak memajukan jendela: 24 jam dihitung dari sinyal yang
    benar-benar tercatat terakhir (`catat`).
    """

    def __init__(self, jendela_jam: int = DEDUP_JAM) -> None:
        self._jendela = timedelta(hours=jendela_jam)
        self._terakhir: dict[tuple[str, str], datetime] = {}

    @staticmethod
    def _cek_waktu(waktu: datetime) -> None:
        if waktu.tzinfo is None:
            raise ValueError("waktu harus beraware zona (UTC)")

    @staticmethod
    def _kunci(sinyal: SinyalStok) -> tuple[str, str]:
        return (sinyal.item_id, sinyal.jenis.value)

    def boleh_kirim(self, sinyal: SinyalStok, sekarang: datetime) -> bool:
        self._cek_waktu(sekarang)
        terakhir = self._terakhir.get(self._kunci(sinyal))
        return terakhir is None or sekarang - terakhir >= self._jendela

    def catat(self, sinyal: SinyalStok, sekarang: datetime) -> None:
        self._cek_waktu(sekarang)
        self._terakhir[self._kunci(sinyal)] = sekarang
