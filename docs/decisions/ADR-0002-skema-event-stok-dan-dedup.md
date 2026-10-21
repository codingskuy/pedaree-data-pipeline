# ADR-0002 — Skema event `pedaree.stok.v1` dan dedup produsen

Status: Diterima | Tanggal: 2026-10-21

## Konteks

`schemas/event-stok-v1.json` memakai field `event` dan tidak memuat `item_id`/`tanggal` (kunci idempoten TitipO). Penerima TitipO
(`SinyalPedareeStok`) memakai `jenis`, `item_id`, `tanggal`. Tiket PDR-DATA-003 (issue #3). Menindaklanjuti ADR-0001 butir 2-3.

## Keputusan

1. Perubahan nama field `event` menjadi `jenis`, penambahan `item_id` dan `tanggal` wajib, `additionalProperties: false`; satuan dibatasi 13 baku.
2. Dedup produsen per pasangan (`item_id`, `jenis`), jendela 24 jam dihitung dari sinyal tercatat terakhir, penyimpanan dalam memori.
3. Relevansi 48 jam dicatat di `docs/SKEMA-EVENT-STOK-V1.md` dan konstanta `RELEVANSI_JAM`.

## Konsekuensi

- Belum ada produsen/konsumen lain yang memakai field `event` di repo ini, sehingga tidak ada masa dual-read yang perlu dijalankan di sisi repo ini.
- Dedup dalam memori hilang saat proses restart; idempotensi konsumen TitipO tetap menjadi jaring pengaman. Persistensi dedup menjadi tindak lanjut bila pekerja berjalan lintas restart.
- Risiko kunci `item_id + tanggal` vs dedup per jenis dicatat di dokumen skema (perlu keputusan bersama TitipO).
