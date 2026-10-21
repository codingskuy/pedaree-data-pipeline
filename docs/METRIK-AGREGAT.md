> Versi: v1.0.0 (turunan repo, tidak beku) | Status: aktif | Tiket: PDR-DATA-004

# Agregat metrik dan event analitik

Sumber rumus: Pedaree-TownHall `metrik/10-stockout-dan-waste.md` bab 2-4 dan BRD `30-demand-metrik.md` BR-302/BR-304.
Kode: `src/metrik.py` (fungsi murni), `src/event_analitik.py`.

| Metrik | Fungsi | Jadwal |
|---|---|---|
| `stockoutRate` = 100 x item HABIS / item aktif | `stockout_rate` | harian 23:59 WIB (`waktu_hitung_stockout`; = 16:59 UTC) |
| `wasteGram` per rumah tangga per bulan | `hitung_waste` | bulanan kalender WIB |
| `wasteRupiah` (harga parcel TitipO, bila tak ada harga acuan BR-302) | `hitung_waste` | bulanan kalender WIB |
| median jam MENIPIS ke HABIS per item per bulan | `median_jam_menipis_ke_habis` | bulanan WIB (bulan waktu HABIS) |

Penjadwalan (cron `59 16 * * *` UTC) dan pembacaan DB `pedaree` baca-saja belum dibuat di repo ini; fungsi menerima baris data.

## Event analitik (properti sesuai tabel metrik/10 bab 4)

| Event | Properti | Pembangun |
|---|---|---|
| `stok_menipis` | itemId, sisa, minimum | `stok_menipis` |
| `stok_habis` | itemId, jamSejakMenipis | `stok_habis` |
| `buang_catat` | batchId, jumlah, alasan | `buang_catat` |
| `sinyal_titipo` | itemId, jenis, statusKirim (`dicatat`/`duplikat`/`gagal`) | `sinyal_titipo`; diterbitkan otomatis oleh `proses_sinyal(..., penerbit=)` |
| `pakai_dari_resep` | resepId, itemIds | `pakai_dari_resep` |

Amplop: `nama`, `waktu` (RFC3339 UTC), `properti`. Penerbit: `PenerbitJsonl` (berkas) dan `PenerbitMemori`; tidak ada pengiriman ke layanan eksternal.

## Asumsi (tandai untuk peninjauan manusia)

1. 1 ml disamakan dengan 1 g agar `wasteGram` ("dikonversi ke gram/ml") dapat dijumlahkan; tidak ada data densitas.
2. Satuan hitung tanpa bobot acuan (mis. `pcs`) tidak masuk `wasteGram`; dihitung di `baris_tak_terkonversi`.
3. Komoditas tanpa harga parcel dan tanpa harga acuan tidak dikarang: Rp0 dan dicatat di `baris_tanpa_harga`.
4. "Cabai merah" memakai harga acuan "cabai" (Rp60.000/kg); harga parcel dihitung proporsional jumlah buang / jumlah beli.
5. `wasteRupiah` dibulatkan setengah ke atas ke rupiah bulat; `wasteGram` 1 desimal (inventori/20 bab 3); `stockoutRate` tidak dibulatkan.
6. Properti event mengikuti tabel metrik/10 (BR-304 memuat daftar lebih ringkas: item, sisa, minimum, alasan, resep).
7. Pasangan median: MENIPIS paling awal yang belum pulih sampai HABIS berikutnya; HABIS tanpa MENIPIS diabaikan.
