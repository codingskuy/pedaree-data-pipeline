# ADR-0005 — Kunci idempoten `item_id + jenis + tanggal` dan dedup per jenis

Status: Diterima | Tanggal: 2026-10-21

## Konteks

ADR-0001/0002 memakai kunci idempoten `item_id + tanggal` sambil menahan dedup per (item, jenis). Akibatnya `stok.habis`
sore hari dapat dijawab `duplikat_diabaikan` karena `stok.menipis` pagi memakai kunci yang sama. Keputusan user (final) dan
ADR-0010 backend (`pedaree-backend-service` PR #11): dedup produsen per jenis, kunci `item_id + jenis + tanggal`.
Memperbarui sebagian ADR-0002 (butir kunci); tidak menghapus isinya.

## Keputusan

1. `stok.menipis` dan `stok.habis` masing-masing terkirim; maks 1 per item per jenis per 24 jam (`DedupProdusen`, tidak berubah).
2. Kunci idempoten `item_id + jenis + tanggal` (`SinyalStok.kunci_idempoten`), dikirim klien sebagai header `X-Idempotency-Key`.

## Konsekuensi

- Skenario 08:00 menipis lalu 19:00 habis menghasilkan dua sinyal dengan kunci berbeda; jenis sama dalam 24 jam tetap ditekan.
- Asumsi: openapi TitipO perlu menerima kunci baru; ditandai untuk peninjauan manusia (tidak mengedit dokumen TitipO dari repo ini).
