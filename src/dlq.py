"""Dead-letter queue sederhana berbasis berkas JSONL (tanpa broker)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from src.skema import SinyalStok


class Dlq(Protocol):
    def tambah(self, sinyal: SinyalStok, alasan: str, percobaan: int) -> None: ...


class DlqBerkas:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def tambah(self, sinyal: SinyalStok, alasan: str, percobaan: int) -> None:
        baris = {
            "waktu": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "alasan": alasan,
            "percobaan": percobaan,
            "sinyal": sinyal.model_dump(mode="json"),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(baris, ensure_ascii=False) + "\n")

    def baca(self) -> list[dict]:
        if not self._path.exists():
            return []
        return [json.loads(b) for b in self._path.read_text(encoding="utf-8").splitlines() if b]
