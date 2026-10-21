# Changelog — pedaree-data-pipeline

Format mengikuti Keep a Changelog; versi mengikuti TownHall.

## [Belum dirilis]

### Ditambahkan
- PDR-DATA-002: `KlienTitipo` (`POST /sinyal/pedaree-stok`, `X-Service-Key`, 201/200, retry 5/30/300 dtk, DLQ JSONL), `proses_sinyal`, CLI stdin, ADR-0003.
- PDR-DATA-003: model `SinyalStok`, dedup produsen 24 jam, penyaring sinyal, dokumen `docs/SKEMA-EVENT-STOK-V1.md`, ADR-0002.
- Fondasi AI-dev v1.0.0: `AGENTS.md`, `CLAUDE.md`, ADR-0001, `docs/ARSITEKTUR-AI-DEV.md` (2026-10-14).

### Diubah
- PDR-DATA-003: `schemas/event-stok-v1.json` memakai `jenis`, `item_id`, `tanggal` (selaras TitipO), `additionalProperties: false`; relevansi 48 jam dicatat.
- `requirements.txt`: hapus `confluent-kafka`, perbaiki `ruff` ke 0.8.6 (0.8.9 tidak ada di PyPI).
- PDR-DATA-002: README/ARSITEKTUR tidak lagi menyebut Kafka dan webhook `/sinyal-permintaan`.
