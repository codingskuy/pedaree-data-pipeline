"""Agregat metrik Pedaree (PDR-DATA-004), rumus `metrik/10-stockout-dan-waste.md` bab 2.

Fungsi murni: masukan baris data, keluaran angka. Penjadwalan (harian 23:59 WIB)
dan pembacaan DB `pedaree` (baca-saja) berada di luar modul ini.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

WIB = timezone(timedelta(hours=7))  # WIB tidak mengenal DST

# --- stockoutRate -----------------------------------------------------------


@dataclass(frozen=True)
class ItemStatus:
    item_id: str
    aktif: bool  # False = diarsip, tidak dihitung
    habis: bool  # stokTampil = 0


def stockout_rate(items: list[ItemStatus]) -> float:
    """100 x (item HABIS / total item aktif); 0.0 bila tidak ada item aktif."""
    aktif = [i for i in items if i.aktif]
    if not aktif:
        return 0.0
    return 100 * sum(1 for i in aktif if i.habis) / len(aktif)


def waktu_hitung_stockout(tanggal: date) -> datetime:
    """Saat perhitungan stockoutRate harian: tanggal tersebut pukul 23:59 WIB."""
    return datetime(tanggal.year, tanggal.month, tanggal.day, 23, 59, tzinfo=WIB)


# --- waste ------------------------------------------------------------------

# Konversi ke dasar (inventori/20 bab 2): kg=1000 g; liter=1000 ml; sdm=15 ml; sdt=5 ml.
_MASSA = {"gram": Decimal(1), "kg": Decimal(1000)}
_VOLUME = {"ml": Decimal(1), "liter": Decimal(1000), "sdm": Decimal(15), "sdt": Decimal(5)}
_HITUNG = {"pcs", "siung", "buah", "ikat", "batang", "bonggol", "lembar"}

# Bobot acuan (inventori/20 bab 4): komoditas -> satuan hitung -> gram.
_BOBOT_G: dict[str, dict[str, Decimal]] = {
    "bayam": {"ikat": Decimal(200)},
    "kangkung": {"ikat": Decimal(200)},
    "kemangi": {"ikat": Decimal(50)},
    "daun bawang": {"batang": Decimal(25)},
    "sawi hijau": {"bonggol": Decimal(300)},
    "kol": {"bonggol": Decimal(800)},
    "wortel": {"buah": Decimal(100)},
    "kentang": {"buah": Decimal(150)},
    "tomat": {"buah": Decimal(80)},
    "cabai merah": {"buah": Decimal(5)},
    "bawang merah": {"buah": Decimal(10), "siung": Decimal(10)},
    "bawang putih": {"siung": Decimal(5), "bonggol": Decimal(50)},
    "jagung": {"buah": Decimal(250)},
}

# Harga acuan Varian 1 (BR-302): komoditas -> (rupiah, dasar harga). Dasar: per 1000 g,
# per 1000 ml, per pcs, atau per ikat.
_HARGA_ACUAN: dict[str, tuple[int, str]] = {
    "beras": (12000, "kg"),
    "telur": (2500, "pcs"),
    "cabai": (60000, "kg"),
    "tomat": (20000, "kg"),
    "bawang merah": (40000, "kg"),
    "bawang putih": (45000, "kg"),
    "bayam": (3000, "ikat"),
    "kangkung": (3000, "ikat"),
    "wortel": (18000, "kg"),
    "minyak": (22000, "liter"),
    "gula": (18000, "kg"),
    "garam": (12000, "kg"),
}
_ALIAS_HARGA = {"cabai merah": "cabai"}  # asumsi: cabai merah memakai harga acuan "cabai"


@dataclass(frozen=True)
class Buang:
    """Satu mutasi BUANG (termasuk batch KEDALUWARSA yang dibuang)."""

    household_id: str
    komoditas: str
    jumlah: float
    satuan: str
    waktu: datetime  # beraware zona
    # Harga beli dari parcel TitipO (opsional): beli_jumlah beli_satuan seharga beli_harga (IDR).
    beli_jumlah: float | None = None
    beli_satuan: str | None = None
    beli_harga: int | None = None


@dataclass
class HasilWaste:
    waste_gram: float = 0.0
    waste_rupiah: int = 0
    baris_tanpa_harga: int = 0  # tidak ada harga parcel maupun acuan; tidak dikarang
    baris_tak_terkonversi: int = 0  # satuan hitung tanpa bobot acuan; tidak masuk gram


def bulan_wib(waktu: datetime) -> str:
    if waktu.tzinfo is None:
        raise ValueError("waktu harus beraware zona")
    return waktu.astimezone(WIB).strftime("%Y-%m")


def _norm(nama: str) -> str:
    return " ".join(nama.lower().split())


def _ke_dasar(komoditas: str, jumlah: Decimal, satuan: str) -> tuple[str, Decimal]:
    """Kembalikan (jenis, nilai): 'massa' gram, 'volume' ml, 'pcs'/'hitung' bila tak terkonversi."""
    if satuan in _MASSA:
        return "massa", jumlah * _MASSA[satuan]
    if satuan in _VOLUME:
        return "volume", jumlah * _VOLUME[satuan]
    if satuan in _HITUNG:
        bobot = _BOBOT_G.get(_norm(komoditas), {}).get(satuan)
        if bobot is not None:
            return "massa", jumlah * bobot
        return ("pcs" if satuan == "pcs" else "hitung"), jumlah
    raise ValueError(f"satuan tidak dikenal: {satuan!r}")


def _rupiah_acuan(komoditas: str, jumlah: Decimal, satuan: str) -> Decimal | None:
    nama = _norm(komoditas)
    harga = _HARGA_ACUAN.get(_ALIAS_HARGA.get(nama, nama))
    if harga is None:
        return None
    rupiah, dasar = harga
    jenis, nilai = _ke_dasar(komoditas, jumlah, satuan)
    if dasar in ("kg", "liter"):
        # Asumsi: 1 ml setara 1 g (tanpa data densitas) sehingga massa/volume saling menggantikan.
        return Decimal(rupiah) * nilai / 1000 if jenis in ("massa", "volume") else None
    if dasar == "pcs":
        return Decimal(rupiah) * nilai if jenis == "pcs" else None
    if dasar == "ikat":
        if satuan == "ikat":
            return Decimal(rupiah) * jumlah
        bobot_ikat = _BOBOT_G.get(nama, {}).get("ikat")
        if jenis == "massa" and bobot_ikat:
            return Decimal(rupiah) * nilai / bobot_ikat
    return None


def _rupiah_parcel(b: Buang) -> Decimal | None:
    if not (b.beli_jumlah and b.beli_satuan and b.beli_harga is not None):
        return None
    jenis_b, nilai_b = _ke_dasar(b.komoditas, Decimal(str(b.jumlah)), b.satuan)
    jenis_p, nilai_p = _ke_dasar(b.komoditas, Decimal(str(b.beli_jumlah)), b.beli_satuan)
    if jenis_b != jenis_p or nilai_p == 0 or jenis_b in ("hitung",):
        return None
    return nilai_b / nilai_p * b.beli_harga


def hitung_waste(buangan: list[Buang]) -> dict[tuple[str, str], HasilWaste]:
    """wasteGram dan wasteRupiah per (household_id, 'YYYY-MM' WIB).

    Asumsi (ditandai di PR): ml dijumlahkan bersama gram (1 ml = 1 g); pembulatan
    gram setengah ke atas 1 desimal, rupiah setengah ke atas ke bilangan bulat.
    """
    gram: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    rupiah: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    hasil: dict[tuple[str, str], HasilWaste] = {}
    for b in buangan:
        kunci = (b.household_id, bulan_wib(b.waktu))
        h = hasil.setdefault(kunci, HasilWaste())
        jumlah = Decimal(str(b.jumlah))
        jenis, nilai = _ke_dasar(b.komoditas, jumlah, b.satuan)
        if jenis in ("massa", "volume"):
            gram[kunci] += nilai
        else:
            h.baris_tak_terkonversi += 1
        harga = _rupiah_parcel(b)
        if harga is None:
            harga = _rupiah_acuan(b.komoditas, jumlah, b.satuan)
        if harga is None:
            h.baris_tanpa_harga += 1
        else:
            rupiah[kunci] += harga
    for kunci, h in hasil.items():
        h.waste_gram = float(gram[kunci].quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        h.waste_rupiah = int(rupiah[kunci].quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return hasil


# --- median jam MENIPIS -> HABIS --------------------------------------------


@dataclass(frozen=True)
class Transisi:
    item_id: str
    status: str  # MENIPIS | HABIS | AMAN (selain itu dianggap pulih)
    waktu: datetime


def median_jam_menipis_ke_habis(transisi: list[Transisi]) -> dict[tuple[str, str], float]:
    """Median jam dari MENIPIS ke HABIS per (item_id, 'YYYY-MM' WIB waktu HABIS).

    Pasangan = MENIPIS paling awal yang belum pulih sampai HABIS berikutnya; HABIS
    tanpa MENIPIS, atau MENIPIS yang pulih sebelum habis, diabaikan.
    """
    per_item: dict[str, list[Transisi]] = defaultdict(list)
    for t in transisi:
        per_item[t.item_id].append(t)
    durasi: dict[tuple[str, str], list[float]] = defaultdict(list)
    for item_id, daftar in per_item.items():
        mulai: datetime | None = None
        for t in sorted(daftar, key=lambda x: x.waktu):
            if t.status == "MENIPIS":
                mulai = mulai or t.waktu
            elif t.status == "HABIS":
                if mulai is not None:
                    durasi[(item_id, bulan_wib(t.waktu))].append(
                        (t.waktu - mulai).total_seconds() / 3600
                    )
                mulai = None
            else:
                mulai = None
    return {k: statistics.median(v) for k, v in durasi.items()}
