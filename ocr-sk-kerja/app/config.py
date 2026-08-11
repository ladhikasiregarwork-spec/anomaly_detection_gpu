"""
Konfigurasi global aplikasi.

Semua nilai bisa di-override lewat environment variable atau file `.env`
tanpa mengubah kode - termasuk pengaturan resource (CPU/GPU) supaya
mudah disesuaikan kalau hardware berubah di kemudian hari
(lihat PLAN-OCR-SERVICE-SK-KERJA.md §8 - jalur upgrade).
"""
import os
import multiprocessing
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    # --- Paths ---
    data_dir: Path = BASE_DIR / "data"
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    pattern_db_path: Path = BASE_DIR / "data" / "patterns" / "patterns.db"
    field_config_path: Path = BASE_DIR / "data" / "field_config.json"

    # --- Pipeline thresholds (sesuai diagram) ---
    min_text_length: int = 300          # "Text Exists 300 char?"
    pdf_render_dpi: int = 180           # resolusi render halaman PDF -> gambar sebelum OCR
    #  180 DPI = titik seimbang: cukup tajam untuk OCR, tapi tidak membebani RAM
    #  di mesin 16GB saat memproses PDF banyak halaman. Naikkan ke 220-300 hanya
    #  kalau akurasi OCR dokumen scan kurang bagus.

    # --- OCR resource settings (CPU by default, lihat PLAN §4.1) ---
    ocr_use_gpu: bool = False           # GTX 1050 Ti sengaja tidak dipakai untuk OCR
                                         # supaya VRAM 4GB penuh tersedia untuk LLM.
    ocr_num_threads: int = max(1, (os.cpu_count() or 4) - 2)
                                         # sisakan headroom 2 core untuk OS + web server
    ocr_max_concurrent_jobs: int = 1    # kunci konkurensi: model OCR dipakai bergiliran
                                         # supaya tidak ada lonjakan RAM dari job paralel

    # --- LLM resource settings (GPU kecil via Ollama, lihat PLAN §4.2) ---
    llm_backend: str = "ollama"         # "ollama" (lokal) atau "cloud" (lihat llm_engine.py)
    llm_model: str = "gemma2:2b"        # muat nyaman di VRAM 4GB (kuantisasi Q4 bawaan Ollama)
    ollama_host: str = "http://127.0.0.1:11434"
    llm_max_concurrent_jobs: int = 1    # WAJIB 1: GPU 4GB tidak boleh menjalankan >1 request
                                         # LLM bersamaan (lihat PLAN §4.2 - hindari OOM VRAM)
    llm_num_ctx: int = 2048             # context window dipangkas (bukan default 8k+) supaya
                                         # jejak VRAM lebih kecil - cukup untuk 1-2 halaman SK
    llm_keep_alive: str = "5m"          # auto-unload model dari VRAM setelah idle 5 menit,
                                         # supaya GPU tidak terus menahan memori saat tidak dipakai
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2

    # Cloud fallback API (opsional - dipakai kalau llm_backend="cloud" atau lokal gagal)
    cloud_llm_api_key: str = ""
    cloud_llm_base_url: str = "https://api.openai.com/v1"
    cloud_llm_model: str = "gpt-4o-mini"

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000
    max_upload_mb: int = 20


settings = Settings()

# Pastikan direktori yang dibutuhkan selalu ada.
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.pattern_db_path.parent.mkdir(parents=True, exist_ok=True)
