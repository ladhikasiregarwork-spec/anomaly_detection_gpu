"""
Tahap "OCR (PaddleOCR v6 / RapidOCR)" pada diagram - kotak kuning "GPU Resource".

Keputusan desain (lihat PLAN-OCR-SERVICE-SK-KERJA.md §4.1):
    GTX 1050 Ti (4GB VRAM) SENGAJA TIDAK dipakai untuk OCR. RapidOCR
    (backend ONNXRuntime) dijalankan di CPU:
      - model deteksi + rekognisi kecil (~10-20MB), cepat di CPU i7 gen 8
      - tidak perlu setup CUDA/cuDNN yang rewel untuk GPU Pascal setua ini
      - VRAM 4GB jadi sepenuhnya tersedia untuk tahap LLM (lihat llm_engine.py)

Optimasi resource CPU:
      - model dimuat SEKALI (singleton, lazy-loaded) dan dipakai ulang di
        semua request - reload model onnx per request bisa makan >1 detik.
      - jumlah thread ONNXRuntime dibatasi (`settings.ocr_num_threads`,
        default core - 2) supaya tidak merebut semua core dari proses lain.
      - dibatasi dengan semaphore (`settings.ocr_max_concurrent_jobs`,
        default 1) supaya beberapa request besar tidak menumpuk RAM
        sekaligus di mesin 16GB.
"""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np
from PIL import Image

from app.config import settings

_engine = None
_engine_lock = threading.Lock()
_job_semaphore = threading.Semaphore(settings.ocr_max_concurrent_jobs)


def _get_engine():
    """Lazy singleton - RapidOCR baru dimuat saat dipakai pertama kali,
    lalu tetap ada di memori (dipakai ulang) sepanjang proses server hidup."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:  # double-checked locking
                from rapidocr_onnxruntime import RapidOCR

                _engine = RapidOCR(
                    det_use_cuda=False,
                    cls_use_cuda=False,
                    rec_use_cuda=False,
                    intra_op_num_threads=settings.ocr_num_threads,
                    inter_op_num_threads=1,
                )
    return _engine


def ocr_image(image: Image.Image) -> str:
    """OCR satu gambar (PIL) -> teks gabungan hasil bacaan, urut top-to-bottom."""
    engine = _get_engine()
    arr = np.array(image.convert("RGB"))

    with _job_semaphore:  # batasi konkurensi supaya CPU/RAM tidak overload
        result, _elapse = engine(arr)

    if not result:
        return ""

    # `result` berbentuk list[[box, text, score], ...] - urutkan dari atas
    # ke bawah berdasarkan posisi box supaya urutan baca masuk akal.
    result_sorted = sorted(result, key=lambda item: min(pt[1] for pt in item[0]))
    return "\n".join(item[1] for item in result_sorted)


def ocr_images(images: list[Image.Image]) -> str:
    """OCR beberapa halaman sekaligus (dipanggil berurutan, bukan paralel -
    supaya konkurensi tetap terkendali di semaphore) lalu digabung jadi satu
    'Result Text' seperti pada diagram."""
    texts = [ocr_image(img) for img in images]
    return "\n\n".join(t for t in texts if t)


def is_model_loaded() -> bool:
    return _engine is not None


def warmup() -> None:
    """Muat model di awal (startup FastAPI) supaya request pertama dari user
    tidak kena cold-start beberapa detik saat demo di UI."""
    _get_engine()
