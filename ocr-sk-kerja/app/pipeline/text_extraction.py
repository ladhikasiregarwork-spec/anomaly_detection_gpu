"""
Tahap 2 diagram: "Text Extraction (PyMuPDF)".

Beban: parsing teks native PDF (bukan gambar) - sangat ringan, CPU only.
Resource optimal: dokumen dibuka & ditutup per-request (tidak menahan
memori), tanpa render gambar sama sekali di tahap ini.
"""
from __future__ import annotations

import fitz  # PyMuPDF


def extract_text_from_pdf(content: bytes) -> str:
    """Ambil semua teks native dari PDF. Untuk PDF hasil scan murni (tanpa
    layer teks), fungsi ini akan mengembalikan string kosong/pendek - itu
    sinyal bagi orchestrator untuk lanjut ke jalur OCR (lihat §2 PLAN)."""

    text_parts: list[str] = []
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        for page in doc:
            text_parts.append(page.get_text("text"))
    finally:
        doc.close()  # bebaskan memori segera, jangan menunggu garbage collector

    return "\n".join(text_parts).strip()


def count_pdf_pages(content: bytes) -> int:
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()
