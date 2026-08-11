"""
Kontrol konkurensi resource GPU.

VRAM GTX 1050 Ti cuma 4GB, jadi HANYA satu job GPU (LLM) boleh berjalan di
satu waktu (lihat PLAN §4.2). OCR sengaja dijalankan di CPU (lihat
ocr_engine.py) supaya tidak berebut VRAM dengan LLM sama sekali - tapi
semaphore di sini tetap disiapkan sebagai pengaman terpusat kalau suatu
saat OCR-GPU (PaddleOCR) diaktifkan juga.
"""
import asyncio

from app.config import settings

llm_semaphore = asyncio.Semaphore(settings.llm_max_concurrent_jobs)
