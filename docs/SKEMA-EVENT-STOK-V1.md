> Versi: v1.0.0 (turunan repo, tidak beku) | Status: aktif | Tiket: PDR-DATA-003

# Skema event `pedaree.stok.v1`

Berkas mesin: `schemas/event-stok-v1.json`. Model kode: `src/skema.py` (`SinyalStok`).
Selaras dengan skema `SinyalPedareeStok` di `titipo-backend-service/docs/api/openapi.yaml`.

## Payload

| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `jenis` | enum | ya | `stok.menipis`, `stok.habis`, `kedaluwarsa.dekat` (3 jenis terkunci) |
| `item_id` | string | ya | bagian pertama kunci idempoten (`item_id + jenis + tanggal`) |
| `tanggal` | date `YYYY-MM-DD` | ya | bagian ketiga kunci idempoten |
| `item` | string | ya | nama item |
| `sisa` | number >= 0 | ya | sisa stok dalam `satuan` |
| `satuan` | enum | ya | 13 baku: gram, kg, ml, liter, sdm, sdt, pcs, siung, buah, ikat, batang, bonggol, lembar |
| `kedaluwarsa` | date | ya | tanggal kedaluwarsa batch terdekat |
| `recipe_id` | string atau null | tidak | ID resep Pawonee, hanya untuk tampilan |

Field tak dikenal ditolak (`additionalProperties: false`). Field lama `event` diganti `jenis`.

## Aturan

- **Dedup produsen (BR-301)**: maksimal 1 sinyal per item per jenis per 24 jam; `DedupProdusen` di `src/dedup.py`.
  Penahanan tidak memperpanjang jendela; jendela dihitung dari sinyal yang tercatat terakhir.
- **Idempoten**: kunci `item_id + jenis + tanggal` (`SinyalStok.kunci_idempoten`, ADR-0005); `stok.menipis` dan `stok.habis` pada hari sama punya kunci berbeda sehingga keduanya terkirim; duplikat kunci sama dijawab TitipO `200 duplikat_diabaikan`.
- **Relevansi anjuran 48 jam**: anjuran kedaluwarsa 48 jam setelah sinyal dibuat (`RELEVANSI_JAM`, `masih_relevan`).
- **Anjuran saja**: sinyal TIDAK PERNAH membuat pesanan TitipO otomatis.

## Asumsi (tandai untuk peninjauan manusia)

- Keputusan final (ADR-0005, selaras ADR-0010 backend): dedup per jenis dan kunci idempoten `item_id + jenis + tanggal`.
  Asumsi: penerima TitipO memakai kunci yang sama (sebelumnya `item_id + tanggal`); sebelum itu berlaku, `stok.habis` sehari
  dengan `stok.menipis` masih bisa dijawab `duplikat_diabaikan`. Perlu penyelarasan openapi TitipO.
