# OCR Service SK Kerja

Implementasi kerja dari [`PLAN-OCR-SERVICE-SK-KERJA.md`](PLAN-OCR-SERVICE-SK-KERJA.md) — service ekstraksi field dari dokumen SK Kerja (PDF/JPG/PNG) → JSON, dioptimasi untuk hardware **CPU i7 Gen 8 + GPU GTX 1050 Ti (4GB) + RAM 16GB**.

> 👉 Baru pertama pakai? Langsung ke **[PANDUAN-PENGGUNAAN.md](PANDUAN-PENGGUNAAN.md)** untuk langkah-langkah menjalankan & memakai service ini. Dokumen ini (README) fokus ke arsitektur & struktur kode.

## Ringkasan Alur (sesuai diagram)

```
Upload (PDF/JPG/PNG)
  -> Format Detection                       [CPU]
  -> PDF: Text Extraction (PyMuPDF)          [CPU]
       -> teks >= 300 char? -> ya: pakai langsung
                             -> tidak: Split PDF Pages [CPU] -> OCR (RapidOCR) [CPU]
  -> JPG/PNG: OCR (RapidOCR) langsung         [CPU]
  -> Pattern Matching (Regex)                 [CPU]
  -> Ada pola tersimpan?
       -> Ya  : pakai regex tersimpan                                    [CPU]
       -> Tidak: LLM (Gemma2:2b via Ollama) pelajari pola -> simpan      [GPU kecil]
  -> Normalizer + Extract Field               [CPU]
  -> JSON Response
```

Field wajib yang diekstrak bisa diubah di [`data/field_config.json`](data/field_config.json) tanpa mengubah kode.

## Kenapa alokasi resource-nya begini

| Tahap | Resource | Alasan |
|---|---|---|
| Semua logic (deteksi, extract, regex, normalizer) | CPU | Beban ringan, tidak butuh GPU sama sekali |
| OCR (RapidOCR) | **CPU** (sengaja, bukan GPU) | Model kecil, cepat di CPU; membebaskan VRAM 4GB sepenuhnya untuk LLM |
| LLM (Gemma2:2b via Ollama) | **GPU kecil (1050 Ti)** | Hanya jalan saat template dokumen BARU (jarang) - model 2B muat nyaman di 4GB VRAM |

Detail & alternatif ada di `PLAN-OCR-SERVICE-SK-KERJA.md` §3-4.

## Instalasi (sudah dilakukan otomatis di sesi ini)

- Python 3.12 (venv di `.venv/`, terpisah dari conda/global Python)
- Dependency: `pip install -r requirements.txt`
- [Ollama](https://ollama.com) + model `gemma2:2b` (`ollama pull gemma2:2b`)

Kalau perlu setup ulang di mesin lain:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
ollama pull gemma2:2b
```

## Menjalankan

1. Pastikan Ollama berjalan (biasanya otomatis jalan sebagai service setelah install; kalau belum: `ollama serve`).
2. Jalankan service:

   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```

3. Buka **http://127.0.0.1:8000** di browser — UI upload & hasil ekstraksi ada di sana.

Endpoint API:
- `POST /api/extract` (multipart `file=...`) → JSON hasil ekstraksi + jejak resource per tahap
- `GET /api/health` → status server, backend OCR/LLM, apakah Ollama terhubung
- `GET /api/patterns` → daftar pola/template yang sudah pernah dipelajari

## Catatan penggunaan resource saat runtime

- **Jalankan dengan 1 worker saja** (`run.py` sudah diset begitu) — lebih dari 1 worker akan menggandakan pemakaian RAM (model OCR dimuat ulang per worker) dan berisiko rebutan VRAM 4GB di Ollama.
- Dokumen dengan **template yang sudah dikenal** akan selesai murni di CPU (cepat, milidetik-detik) — GPU/Ollama tidak tersentuh sama sekali.
- Dokumen dengan **template baru** akan memicu LLM (beberapa detik–puluhan detik tergantung panjang teks) — ini yang memakai VRAM GPU 1050 Ti. Sekali dipelajari, dokumen sejenis berikutnya lewat jalur cepat.
- Ollama otomatis melepas model dari VRAM setelah idle 5 menit (`llm_keep_alive` di `app/config.py`) supaya GPU tidak terus "disandera".
- Kalau ingin menonaktifkan LLM lokal dan pakai API cloud sebagai gantinya, isi `cloud_llm_api_key` di file `.env` (lihat `.env.example`) — berguna kalau GPU sedang dipakai untuk hal lain.

## Struktur folder

```
app/
  config.py              # semua setting resource (thread OCR, concurrency GPU, dsb)
  main.py                # FastAPI app + endpoint
  models/schemas.py       # skema request/response
  pipeline/
    format_detection.py   # Format Detection
    text_extraction.py     # Text Extraction (PyMuPDF)
    pdf_split.py            # Split PDF Pages
    ocr_engine.py            # OCR (RapidOCR, CPU)
    pattern_matcher.py        # Pattern Matching + Have Existing Pattern?
    llm_engine.py               # LLM (Gemma via Ollama) - GPU kecil
    normalizer.py                 # Normalizer + Extract Field
    orchestrator.py                # menyambungkan semua tahap di atas
  storage/pattern_store.py   # penyimpanan pola (SQLite)
  web/static/index.html        # UI
data/
  field_config.json          # daftar field wajib (bisa diedit)
  patterns/patterns.db         # database pola yang dipelajari (dibuat otomatis)
```

## Menambah / mengubah field wajib

Edit `data/field_config.json`, tambahkan/ubah entri:

```json
{ "key": "nomor_sk", "label": "Nomor SK", "type": "string" }
```

`type` boleh `"string"` atau `"date"` (di-normalisasi ke format `YYYY-MM-DD`). Restart service setelah mengubah file ini.

## Kalau nanti mau upgrade resource

Lihat `PLAN-OCR-SERVICE-SK-KERJA.md` §8 — cukup ubah `ocr_use_gpu=True` (kalau pindah ke PaddleOCR-GPU) atau `llm_model` ke model lebih besar di `app/config.py` / `.env`, tanpa perlu mengubah struktur kode pipeline.
