# Panduan Penggunaan — OCR Service SK Kerja

Panduan praktis langkah demi langkah. Untuk detail arsitektur & alasan desain, lihat [README.md](README.md) dan [`PLAN-OCR-SERVICE-SK-KERJA.md`](PLAN-OCR-SERVICE-SK-KERJA.md).

> **Ringkas:** Ollama jalan → `run.py` → buka `http://127.0.0.1:8000` → upload dokumen.

---

## A. Setiap Kali Mau Pakai (rutin)

### 1. Pastikan Ollama aktif
Ollama biasanya otomatis jalan sebagai background service setelah Windows menyala (cek ikon di system tray dekat jam). Kalau tidak ada:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

Biarkan jendela ini terbuka, atau jalankan lewat shortcut Ollama di Start Menu.

### 2. Jalankan service OCR SK Kerja
Buka PowerShell baru:

```powershell
cd D:\NILAM\ocr-sk-kerja
.\.venv\Scripts\python.exe run.py
```

Tunggu sampai muncul baris terakhir:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Biarkan jendela terminal ini **tetap terbuka** selama service dipakai. Untuk menghentikan: tekan `Ctrl+C`.

### 3. Buka UI di browser
Kunjungi **http://127.0.0.1:8000**

Cek status bar di bagian atas halaman:
- 🟢 titik hijau di "Server aktif" dan "Ollama" → siap dipakai
- 🔴 titik merah di "Ollama" → tahap LLM (pola baru) akan gagal sampai Ollama dinyalakan (lihat langkah 1)

### 4. Upload & proses dokumen
1. Klik kotak upload (atau drag-and-drop file langsung ke sana)
2. Pilih file **PDF, JPG, atau PNG** (maks 20MB)
3. Klik tombol **"Proses Dokumen"**
4. Tunggu:
   - **Template sudah dikenal** → hasil keluar dalam hitungan milidetik–detik (murni CPU)
   - **Template baru** (dokumen pertama dengan format ini) → lebih lama, ±30–60 detik (LLM bekerja di GPU untuk mempelajari pola), sekali saja per template

### 5. Baca hasilnya
Di panel "Hasil Ekstraksi":
- **Badge ringkasan** di atas: format file, apakah OCR/LLM dipakai, nama pola, total waktu
- **Tabel field**: tiap field wajib (Nomor SK, Nama, NIP, dst) + status ✓ **Terisi** / ✗ **Hilang**
- **Jejak Proses Pipeline** (klik untuk buka): urutan tahap yang dilewati, resource CPU/GPU tiap tahap, dan durasinya — berguna untuk memastikan dokumen dengan pola yang sudah dikenal benar-benar tidak menyentuh GPU
- **Cuplikan Teks Mentah** (klik untuk buka): teks hasil ekstraksi/OCR mentah, berguna kalau ada field yang salah/hilang untuk mengecek apa yang sebenarnya terbaca dari dokumen

### 6. Cek daftar pola yang sudah dipelajari
Di bagian bawah halaman ada tabel **"Pola Dokumen yang Sudah Dipelajari"** — semua template yang pernah dikenali LLM, beserta berapa kali sudah dipakai ulang. Dokumen baru dengan template yang cocok salah satu baris di sini akan otomatis lewat jalur cepat (tanpa LLM).

---

## B. Kalau Hasil Ekstraksi Kurang Tepat

| Gejala | Kemungkinan penyebab | Yang bisa dicoba |
|---|---|---|
| Field tertentu selalu "Hilang" utk template yang sama | Regex pola tersimpan tidak pas dengan posisi label field itu | Buka `data/patterns/patterns.db` (lihat §C) atau biarkan LLM belajar ulang dengan menghapus pola lama |
| Field terbaca tapi isinya salah/terpotong | Hasil OCR kurang bersih (dokumen scan kualitas rendah) | Cek "Cuplikan Teks Mentah" untuk lihat teks aslinya; naikkan `pdf_render_dpi` di `app/config.py` kalau dokumen hasil scan |
| Field wajib yang dicari tidak sesuai kebutuhan Anda | Daftar field masih default (contoh) | Edit `data/field_config.json` (lihat §D) |
| LLM gagal / error saat pola baru | Ollama belum jalan / model belum ter-pull | Cek §A langkah 1, atau `ollama list` untuk pastikan `gemma2:2b` ada |

---

## C. Mengelola Pola yang Sudah Dipelajari

- Lihat daftar: buka `http://127.0.0.1:8000/api/patterns` di browser, atau lihat tabel di UI.
- Hapus semua pola (mulai dari nol lagi, semua dokumen berikutnya akan lewat LLM sekali per template): hentikan service, lalu hapus file:
  ```powershell
  Remove-Item D:\NILAM\ocr-sk-kerja\data\patterns\patterns.db
  ```
- Restart service, pattern DB otomatis dibuat ulang kosong.

## D. Mengubah Field Wajib yang Diekstrak

Edit `data/field_config.json`, format tiap entri:

```json
{ "key": "nama_field", "label": "Label yang Ditampilkan", "type": "string" }
```

- `type`: `"string"` (teks biasa) atau `"date"` (dinormalisasi ke `YYYY-MM-DD`)
- Restart service setelah menyimpan perubahan
- Pola lama yang sudah tersimpan **tidak otomatis** punya regex untuk field baru — dokumen berikutnya dengan template lama akan memicu LLM lagi untuk mempelajari field tambahan tersebut

---

## E. Uji Coba Cepat Tanpa Upload Manual

Tersedia script contoh di `scripts/` untuk menguji pipeline tanpa perlu dokumen asli:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py       # uji jalur cepat (CPU-only)
.\.venv\Scripts\python.exe scripts\make_test_pdf.py     # buat contoh PDF SK Kerja
.\.venv\Scripts\python.exe scripts\make_test_image.py   # buat contoh gambar SK Kerja (utk uji OCR)
```

File contoh yang dihasilkan akan tersimpan di `data/uploads/` — upload lewat UI seperti dokumen biasa.

---

## Ringkasan Perintah

```powershell
# Jalankan service
cd D:\NILAM\ocr-sk-kerja
.\.venv\Scripts\python.exe run.py

# Buka di browser
http://127.0.0.1:8000

# Cek status/kesehatan server
http://127.0.0.1:8000/api/health

# Hentikan
Ctrl+C  (di jendela terminal yang menjalankan run.py)
```
