# Plan: OCR Service SK Kerja

> Dokumen perencanaan teknis untuk sistem ekstraksi field dari dokumen SK Kerja (PDF/JPG/PNG) → JSON, berdasarkan diagram alur yang diberikan. Disesuaikan dengan hardware yang tersedia saat ini.

**Tanggal dibuat:** 10 Agustus 2026
**Hardware target:** CPU Intel i7 Gen 8, GPU NVIDIA GTX 1050 Ti (4GB VRAM), RAM 16GB

---

## 1. Ringkasan Sistem

Sistem menerima dokumen SK Kerja dalam format PDF atau gambar (JPG/PNG), lalu:

1. Mendeteksi format file.
2. Mengekstrak teks — langsung (PDF native text) atau via OCR (gambar/PDF hasil scan).
3. Mencocokkan teks hasil ekstraksi dengan pola (regex) yang sudah pernah dipelajari.
4. Jika polanya belum dikenal, memakai LLM untuk mempelajari struktur dokumen baru sekali, lalu menyimpannya sebagai regex agar dokumen sejenis berikutnya **tidak perlu LLM lagi**.
5. Menormalisasi dan mengekstrak field wajib → mengembalikan JSON.

**Insight penting untuk perencanaan resource:** LLM hanya dipanggil ketika ada **pola dokumen baru** (jalur "No" pada "Have Existing Pattern?"). Untuk dokumen dengan template yang sudah pernah dilihat, jalur cukup lewat regex matching yang sangat ringan (CPU, milidetik). Ini berarti beban GPU/LLM **tidak proporsional dengan jumlah dokumen**, melainkan dengan jumlah **variasi template baru** — jauh lebih jarang. Ini yang membuat spesifikasi hardware Anda saat ini realistis dipakai.

---

## 2. Breakdown Pipeline & Kebutuhan Resource per Tahap

| # | Tahap | Jenis Beban | Butuh GPU? | Rekomendasi untuk hardware Anda |
|---|-------|-------------|:---:|---|
| 1 | Format Detection | Logic ringan (cek ekstensi/mime) | Tidak | CPU, instan |
| 2 | Text Extraction (PyMuPDF) | Parsing PDF | Tidak | CPU, cepat (<1 detik/dokumen) |
| 3 | Cek "Text > 300 char?" | Logic ringan | Tidak | CPU, instan |
| 4 | Split PDF Pages | Render PDF → image | Tidak | CPU, ringan (PyMuPDF `get_pixmap`) |
| 5 | **OCR** (PaddleOCR/RapidOCR) | Inference model CV kecil | **Opsional** | **CPU cukup** — pakai RapidOCR (ONNXRuntime), lihat §3 |
| 6 | Pattern Matching (Regex) | Regex matching | Tidak | CPU, instan |
| 7 | Cek "Have Existing Pattern?" | Lookup DB/dict | Tidak | CPU, instan |
| 8 | **LLM** (Gemma/GPT) | Inference LLM | **Disarankan pakai GPU kecil / cloud API** | Model kecil + kuantisasi, lihat §3 — hanya trigger saat pola baru |
| 9 | Store New Pattern Regex | Simpan ke DB/file | Tidak | CPU, instan |
| 10 | Normalizer | Logic mapping field | Tidak | CPU, instan |
| 11 | Extract Field | Logic mapping field | Tidak | CPU, instan |
| 12 | JSON Response | Serialisasi | Tidak | CPU, instan |

**Kesimpulan cepat:** dari 12 tahap, hanya **2 tahap** (OCR dan LLM) yang relevan dengan GPU — dan keduanya bisa dijalankan dengan konfigurasi yang cocok untuk GTX 1050 Ti 4GB, asal memilih model/engine yang tepat (bukan model besar default).

---

## 3. Analisis Hardware yang Tersedia

| Komponen | Spesifikasi | Catatan |
|---|---|---|
| GPU | GTX 1050 Ti, 4GB VRAM, arsitektur Pascal, 768 CUDA core, **tanpa Tensor Core** | GPU ini kelas entry-level 2016. Cukup untuk inference model CV kecil dan LLM **kecil terkuantisasi** (Q4), tapi **tidak cukup** untuk model 7B+ tanpa kuantisasi berat, dan tidak akan memberi speed-up besar untuk FP16 (karena tidak ada Tensor Core). |
| CPU | Intel i7 Gen 8 (Coffee Lake, umumnya 6 core/12 thread untuk varian desktop) | Cukup kuat untuk inference ONNXRuntime (OCR) dan llama.cpp (LLM CPU) multi-thread. |
| RAM | 16GB | Cukup untuk 1 proses OCR + 1 proses LLM kecil (Q4, 2–4GB model) berjalan bergantian. Jangan jalankan banyak worker paralel bersamaan tanpa batas. |

**Batasan utama = VRAM 4GB.** Strategi di bawah dirancang supaya OCR dan LLM **tidak berebut VRAM di waktu yang sama** (karena keduanya jarang perlu jalan bersamaan pada dokumen yang sama).

---

## 4. Rekomendasi Teknologi (disesuaikan hardware)

### 4.1 OCR — pakai CPU sebagai default, GPU opsional

| Opsi | Rekomendasi | Alasan |
|---|---|---|
| **RapidOCR (ONNXRuntime)** | ✅ **Pilih ini sebagai default** | Model deteksi+rekognisi kecil (~10–20MB), dioptimasi untuk CPU, tidak butuh install CUDA/cuDNN yang rewel untuk GPU tua seperti 1050 Ti. Latensi ~0.5–2 detik/halaman di CPU i7 gen 8 (perkiraan, perlu benchmark). |
| PaddleOCR (mode GPU) | Opsional, aktifkan hanya kalau volume dokumen tinggi & butuh percepatan | PaddleOCR versi GPU butuh CUDA/cuDNN versi spesifik yang cocok dengan driver 1050 Ti (compute capability 6.1) — instalasi lebih rumit, dan speedup-nya tidak akan besar karena tidak ada Tensor Core. |

**Saran:** mulai dengan RapidOCR CPU-only. Baru pertimbangkan GPU kalau setelah benchmark ternyata throughput CPU tidak cukup untuk kebutuhan produksi.

### 4.2 LLM — model kecil terkuantisasi, bukan model besar

Karena LLM hanya jalan saat ada **pola dokumen baru** (jarang), tidak perlu server LLM yang selalu nyala dengan model besar. Dua opsi, bisa dikombinasikan sebagai primary + fallback:

| Opsi | Model | VRAM/RAM | Kapan pakai |
|---|---|---|---|
| **A. Lokal via Ollama** (disarankan untuk mulai) | `gemma2:2b-instruct-q4_K_M` atau `phi3:mini` (Q4) | ~1.5–2.5GB VRAM (muat di 1050 Ti 4GB), atau full CPU ~16GB RAM cukup | Development, testing, dan produksi skala kecil/offline. Latensi ~5–20 detik per ekstraksi pola baru (GPU) — **acceptable karena jarang terjadi**. |
| **B. Cloud API** (fallback/opsional) | GPT-4o-mini / model cloud setara | Tidak butuh resource lokal sama sekali | Kalau butuh akurasi ekstraksi pola lebih tinggi untuk dokumen yang formatnya rumit/ambigu, atau kalau mau menghindari beban GPU lokal sepenuhnya. Biaya kecil karena jarang dipanggil. |

**Hindari:** menjalankan Gemma 7B/9B atau model besar lain secara lokal — tidak akan muat nyaman di VRAM 4GB, dan mode CPU-only untuk model sebesar itu akan terlalu lambat untuk dipakai rutin.

**Penting — hindari rebutan VRAM:** beri **lock/semaphore** di level aplikasi supaya tahap OCR (kalau nanti diaktifkan mode GPU) dan tahap LLM tidak dieksekusi bersamaan di GPU yang sama. Untuk versi awal, cukup jalankan **OCR di CPU** dan **LLM di GPU** — otomatis tidak akan bentrok.

### 4.3 Ringkasan Konfigurasi Awal yang Disarankan

```
OCR      → RapidOCR (ONNXRuntime, CPU)
LLM      → Ollama + gemma2:2b-instruct-q4 (GPU 1050 Ti, offload penuh muat di 4GB)
Fallback → Cloud API (opsional, kalau akurasi lokal kurang di kasus tertentu)
```

Konfigurasi ini **tidak menyentuh batas VRAM 4GB** dalam kondisi normal, dan CPU i7 gen 8 + RAM 16GB cukup menangani OCR serta orkestrasi service.

---

## 5. Rencana Implementasi Bertahap

| Fase | Deliverable | Fokus |
|---|---|---|
| **0. Setup Environment** | Python venv, install PyMuPDF, RapidOCR, Ollama + pull model kecil, update driver NVIDIA (pastikan versi driver mendukung CUDA yang dibutuhkan Ollama) | Infrastruktur dasar |
| **1. Format Detection & Text Extraction** | Modul deteksi PDF vs JPG/PNG, ekstraksi teks native PDF via PyMuPDF | Jalur cepat tanpa OCR/LLM |
| **2. OCR Pipeline** | Split PDF → image, integrasi RapidOCR, logic cek `>300 char` | Jalur dokumen hasil scan |
| **3. Pattern Matching Engine** | Penyimpanan regex per tipe dokumen (mulai dari SQLite/JSON, bisa naik ke Postgres nanti), fungsi matching | Reuse pola lama tanpa LLM |
| **4. LLM Fallback + Pattern Learning** | Integrasi Ollama (gemma2:2b), prompt untuk mengidentifikasi field & bikin regex baru, simpan pola baru | Jalur pola baru |
| **5. Normalizer & Field Extraction** | Mapping field wajib (nama, NIP/no. pegawai, tanggal, jabatan, dll — sesuaikan kebutuhan SK Kerja) | Output terstruktur |
| **6. API Service** | Wrapper FastAPI, endpoint upload → JSON response | Service layer |
| **7. Concurrency Control** | Semaphore/queue supaya OCR & LLM tidak rebutan resource, batasi worker paralel sesuai RAM/VRAM | Stabilitas di hardware terbatas |
| **8. Testing & Benchmark** | Ukur latensi tiap tahap di hardware aktual, uji dokumen dengan variasi kualitas scan | Validasi asumsi performa |
| **9. Logging & Monitoring** | Log penggunaan VRAM/CPU, error handling saat OOM, fallback otomatis ke cloud API kalau lokal gagal | Observability |

---

## 6. Arsitektur Deployment yang Disarankan

```
Client → FastAPI (async)
             │
             ├── Fast path (CPU-only): Format Detection → Text Extraction → Regex Match → Normalizer → JSON
             │
             └── Slow path (queue/worker, concurrency=1 untuk tahap GPU):
                     OCR (RapidOCR, CPU) → Regex Match →
                        └── kalau pola baru → LLM (Ollama, GPU) → Simpan Regex Baru
                     → Normalizer → Extract Field → JSON
```

- Gunakan **task queue sederhana** (mis. Python `asyncio` semaphore atau `RQ`/`Celery` + Redis kalau nanti butuh multi-worker) supaya request tidak saling menumpuk memenuhi 4GB VRAM sekaligus.
- Batasi **concurrency tahap LLM = 1** di awal. Ini realistis karena trigger-nya memang jarang (pola baru saja).

---

## 7. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| CUDA Out of Memory saat LLM dan OCR-GPU jalan bersamaan | Jalankan OCR di CPU (default), LLM saja yang pakai GPU |
| Model LLM lokal kurang akurat untuk dokumen kompleks | Sediakan fallback ke cloud API untuk kasus low-confidence |
| Volume dokumen naik drastis → CPU OCR jadi bottleneck | Sudah ada opsi upgrade ke PaddleOCR GPU / tambah worker, lihat §8 |
| Driver NVIDIA lama tidak kompatibel dengan versi CUDA yang dibutuhkan Ollama/PaddleOCR terbaru | Update driver GTX 1050 Ti ke versi terbaru yang masih disupport (Pascal masih disupport driver terbaru NVIDIA) sebelum instalasi |
| RAM habis saat banyak request paralel (PDF besar + OCR + LLM) | Batasi ukuran file upload & jumlah worker paralel sesuai §6 |

---

## 8. Jalur Upgrade ke Depan (kalau kebutuhan naik)

Tidak perlu dilakukan sekarang — hanya referensi kalau nanti volume produksi meningkat:

- **GPU lokal lebih besar** (mis. RTX 3060 12GB / 4060 Ti 16GB) → bisa pakai model LLM lebih besar (7B–8B) dan PaddleOCR GPU penuh untuk throughput tinggi.
- **Cloud GPU / API murni** → kalau volume tidak stabil, lebih hemat pakai API on-demand (OCR & LLM) daripada investasi hardware.
- **Multi-worker horizontal** → begitu ada lebih dari 1 mesin, pisahkan tahap CPU-heavy (OCR) dan GPU-heavy (LLM) jadi service terpisah supaya scaling independen.

---

## 9. Ringkasan Rekomendasi Utama

1. **OCR: pakai RapidOCR di CPU** sebagai default — hindari kerumitan setup CUDA untuk GPU tua, cukup cepat untuk kebutuhan awal.
2. **LLM: pakai model kecil terkuantisasi (Gemma2 2B / Phi-3 mini, Q4) via Ollama di GPU 1050 Ti** — muat nyaman di 4GB VRAM, dan karena hanya trigger saat pola baru, latensi beberapa detik tidak masalah.
3. **Jangan jalankan OCR-GPU dan LLM bersamaan** — beri concurrency control supaya tidak OOM di VRAM 4GB.
4. **Siapkan fallback ke cloud API** untuk kasus dokumen yang gagal diekstrak model lokal, tanpa perlu upgrade hardware dulu.
5. Hardware saat ini (i7 gen 8, 1050 Ti 4GB, RAM 16GB) **cukup untuk pengembangan dan produksi skala kecil–menengah**, dengan catatan volume "pola dokumen baru" tetap rendah dibanding total dokumen yang diproses.
