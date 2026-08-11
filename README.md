# anomaly_detection_gpu

Dua project di satu repo, sama-sama dijalankan/dikembangkan di mesin dengan **CPU Intel i7 Gen 8
(tanpa AVX-512) + GPU NVIDIA GTX 1050 Ti (4GB VRAM)**:

| Folder | Apa isinya | Status |
|---|---|---|
| [`anomaly_detection/`](anomaly_detection/) | Fork dari [haswinpratamawork/anomaly_detection](https://github.com/haswinpratamawork/anomaly_detection) — 2 notebook Jupyter deteksi anomali dokumen (layout-based & text-based), sudah dikonfigurasi jalan di GPU lokal | GPU aktif & terverifikasi |
| [`ocr-sk-kerja/`](ocr-sk-kerja/) | Service ekstraksi field dari dokumen SK Kerja (PDF/JPG/PNG → JSON), OCR di CPU + LLM pola-baru di GPU, lengkap dengan UI web | Selesai & teruji end-to-end |

## anomaly_detection

Deteksi dokumen mencurigakan (bank statement, KTP, slip gaji, surat keterangan kerja) dengan
membandingkan tiap dokumen ke kumpulan contoh **genuine** — tanpa perlu contoh dokumen palsu.
Lihat [`anomaly_detection/README.md`](anomaly_detection/README.md) untuk detail lengkap & cara pakai.

**Setup GPU di mesin ini** — beberapa versi package harus dikunci karena versi terbaru gagal jalan
di hardware ini (CPU tanpa AVX-512 + driver GPU yang tadinya sangat lawas). Semua alasannya
didokumentasikan di [`anomaly_detection/README.md` § Setup GPU](anomaly_detection/README.md#setup-gpu--version-pins-and-why-oldermixed-hardware).

```bash
cd anomaly_detection
python -m venv .venv-gpu
.venv-gpu\Scripts\pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cu118
.venv-gpu\Scripts\pip install -r requirements.txt
.venv-gpu\Scripts\python -m ipykernel install --user --name anomaly-detection-gpu --display-name "Anomaly Detection (GPU-ready)"
```

## ocr-sk-kerja

Upload SK Kerja (PDF/JPG/PNG) → sistem mendeteksi format, OCR kalau perlu, cocokkan ke pola yang
sudah dikenal (regex, secepat milidetik) atau pelajari pola baru pakai LLM lokal (Gemma via Ollama,
di GPU) sekali per template dokumen baru — lalu keluarkan JSON field yang sudah dinormalisasi.
Lihat [`ocr-sk-kerja/README.md`](ocr-sk-kerja/README.md) dan
[`ocr-sk-kerja/PANDUAN-PENGGUNAAN.md`](ocr-sk-kerja/PANDUAN-PENGGUNAAN.md) untuk cara pakai
langkah-demi-langkah.

```bash
cd ocr-sk-kerja
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
# buka http://127.0.0.1:8000
```

## Privasi

- `anomaly_detection/reference/`, `data/`, `result/` — dokumen asli (rekening bank, KTP, dll) —
  **sengaja tidak ada di repo ini**. Buat foldernya sendiri secara lokal, jangan pernah di-commit.
  Notebook di sini juga disimpan **tanpa output sel** (dibersihkan sebelum commit) karena output bisa
  memuat cuplikan teks/gambar dokumen asli.
- `ocr-sk-kerja/data/uploads/` dan `data/patterns/*.db` — upload & pola hasil pembelajaran dari
  dokumen asli pengguna — juga tidak ikut di-commit (lihat `.gitignore`).
