# ADR-0003 — Transport sinyal HTTP langsung ke TitipO, tanpa Kafka

Status: Diterima | Tanggal: 2026-10-21

## Konteks

Kode awal memuat dependensi `confluent-kafka` dan README menyebut topik Kafka serta webhook `/sinyal-permintaan`. Penerima resmi TitipO adalah
`POST /sinyal/pedaree-stok` dengan header `X-Service-Key` (KONTEKS §3.1; ADR-0001 butir 1 dan Konsekuensi yang meminta transport dipilih lewat ADR). Kafka
menyimpang dari stack terkunci. Tiket PDR-DATA-002 (issue #2).

## Keputusan

1. Pekerja memanggil HTTP langsung (httpx) ke `POST /sinyal/pedaree-stok`; Kafka dan `confluent-kafka` tidak dipakai dan tidak diperluas.
2. Retry 3 kali (jeda 5, 30, 300 detik) untuk galat jaringan, 5xx, dan 429; galat permanen (400/401/403/422) langsung ke DLQ tanpa retry.
3. DLQ berupa berkas JSONL (`PEDAREE_DLQ_PATH`); 201 `dicatat_sebagai_anjuran` dan 200 `duplikat_diabaikan` keduanya sukses. Dedup produsen dicatat hanya setelah penerimaan.
4. Konsumen tercatat: TitipO. Kunci layanan lewat env `PEDAREE_SERVICE_KEY`, tidak masuk log/DLQ/repr.

## Konsekuensi

- Masukan pekerja berupa JSON Lines `SinyalStok` (stdin) sebagai asumsi; sumber sesungguhnya (outbox/DB `pedaree` baca-saja atau push dari backend) menunggu kontrak `pedaree-backend-service`.
- DLQ berkas belum memiliki pemutar ulang otomatis; tindak lanjut bila dibutuhkan.
- Tidak ada jalur pembuatan pesanan: uji memastikan satu-satunya panggilan adalah `POST /sinyal/pedaree-stok`.
