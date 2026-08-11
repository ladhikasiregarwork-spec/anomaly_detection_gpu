"""
Tahap 1 diagram: "Format Detection".

Beban: sangat ringan (cek beberapa byte pertama file / ekstensi).
Resource: CPU, praktis instan - tidak perlu optimasi khusus.
"""
from __future__ import annotations

SUPPORTED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
SUPPORTED_PDF_EXT = {".pdf"}


class UnsupportedFormatError(Exception):
    pass


def detect_format(filename: str, content: bytes) -> str:
    """Kembalikan "pdf" atau "image" berdasarkan magic-bytes (bukan cuma
    ekstensi, supaya lebih tahan terhadap file yang salah nama)."""

    head = content[:8]

    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "image"  # JPEG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"  # PNG

    # Fallback ke ekstensi kalau magic-bytes tidak dikenali (mis. file hasil
    # convert yang headernya tidak standar).
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in SUPPORTED_PDF_EXT:
        return "pdf"
    if ext in SUPPORTED_IMAGE_EXT:
        return "image"

    raise UnsupportedFormatError(
        f"Format file '{filename}' tidak didukung. Gunakan PDF, JPG, atau PNG."
    )
