# ADR-0004 — Agregat metrik sebagai fungsi murni, penjadwal di luar kode

Status: Diterima | Tanggal: 2026-10-21

## Konteks

PDR-DATA-004 (issue #4) meminta stockoutRate harian 23:59 WIB, waste bulanan WIB, median jam MENIPIS ke HABIS, dan 5 event analitik. Skema DB `pedaree` dan
kontrak backend untuk membaca mutasi belum terbit; stack tidak memuat broker atau penjadwal (ADR-0003, tanpa Kafka).

## Keputusan

1. Agregat berupa fungsi murni di `src/metrik.py` (masukan: baris data; keluaran: angka) agar dapat diuji deterministik; WIB = UTC+7 tetap.
2. Penjadwalan memakai cron/penjadwal platform (`59 16 * * *` UTC untuk harian); tidak ada penjadwal baru di kode.
3. Event analitik ditulis ke JSONL melalui `Penerbit`; tidak ada pengiriman eksternal.

## Konsekuensi

- Pembaca DB `pedaree` (baca-saja) dan pemetaan baris ke `ItemStatus`/`Buang`/`Transisi` menjadi tindak lanjut setelah kontrak backend terbit.
- Asumsi konversi dan harga dicatat di `docs/METRIK-AGREGAT.md` dan perlu persetujuan manusia.
