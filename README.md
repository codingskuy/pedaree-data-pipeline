# pedaree-data-pipeline — Event Stok menjadi Sinyal Permintaan TitipO

Divisi **Pedaree (Smart Pantry)**, org **Coding-Skuy**. Opsi A.

TownHall: https://github.com/Coding-Skuy/Pedaree-TownHall

## Ringkasan

Pipeline yang mengubah event stok Pedaree (stok menipis, kedaluwarsa dekat)
menjadi sinyal permintaan untuk TitipO (modul titip belanja). TitipO memakai
sinyal ini untuk menawarkan jasa titip belanja bahan pengganti.

## Modul pantry-resep

Kontrak lintas divisi (detail: `docs/MODUL-PANTRY-RESEP.md`):

- **Pemilik modul:** Pawonee.
- **Konsumen modul:** Pedaree (pipeline menyertakan `recipe_id` Pawonee pada
  sinyal agar TitipO tahu bahan pengganti dipakai untuk resep apa).
- Pipeline tidak mengubah definisi resep; hanya meneruskan rujukan.

## Aliran data

```text
backend pedaree (SinyalStok pedaree.stok.v1, JSON Lines)
  -> pekerja sinyal (python, dedup 24 jam)
  -> POST TitipO /sinyal/pedaree-stok (header X-Service-Key + X-Idempotency-Key; retry 5/30/300 dtk, lalu DLQ berkas)
```

## Teknologi (versi dikunci)

- Python 3.12.8
- httpx 0.28.1 (klien HTTP ke TitipO)
- pydantic 2.10.6
- PostgreSQL 16.6 (sumber baca)

Lihat `requirements.txt` sebagai sumber kebenaran versi Python.

## Cara jalan

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TITIPO_BASE_URL=https://titipo.example PEDAREE_SERVICE_KEY=...   # jangan commit kunci
python -m src.pekerja_sinyal < sinyal.jsonl
python -m pytest -q
```

## CI

Workflow `.github/workflows/ci.yml` menjalankan lint dan uji skema event.
