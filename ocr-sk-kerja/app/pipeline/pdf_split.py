"""
Tahap "Split PDF Pages" pada diagram (jalur PDF hasil scan, teks < 300 char).

Beban: render halaman PDF -> raster image. CPU only (PyMuPDF), tidak
menyentuh GPU sama sekali.

Optimasi resource:
- DPI dibatasi (default 180, lihat app/config.py) - cukup untuk akurasi
  OCR tapi tidak membengkakkan RAM.
- Halaman di-render satu per satu lewat *generator* (bukan list penuh di
  memori) supaya PDF dengan banyak halaman tidak membuat RAM 16GB penuh
  sekaligus - tiap halaman diproses OCR lalu langsung dilepas.
"""
from __future__ import annotations

from typing import Iterator

import fitz  # PyMuPDF
from PIL import Image

from app.config import settings


def iter_pdf_pages_as_images(content: bytes, dpi: int | None = None) -> Iterator[Image.Image]:
    """Yield gambar PIL per halaman PDF. Generator - halaman berikutnya baru
    dirender setelah halaman sebelumnya selesai dipakai (hemat RAM)."""

    dpi = dpi or settings.pdf_render_dpi
    zoom = dpi / 72.0  # PyMuPDF default 72 DPI -> skala ke DPI target
    matrix = fitz.Matrix(zoom, zoom)

    doc = fitz.open(stream=content, filetype="pdf")
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            yield img
            del pix, img  # lepas referensi secepat mungkin
    finally:
        doc.close()
