"""
Tahap "Pattern Matching (Regex Exist)" + "Have Existing Pattern?" pada diagram.

Beban: regex matching murni Python - CPU, instan (mikrodetik-milidetik).
Ini jalur "cepat" yang membuat sebagian besar dokumen TIDAK perlu OCR-GPU
ataupun LLM-GPU sama sekali setelah template-nya pernah dipelajari sekali.
"""
from __future__ import annotations

import re

from app.storage.pattern_store import PatternRecord, get_all_patterns, increment_hit


def find_matching_pattern(text: str) -> PatternRecord | None:
    """Cari pola tersimpan yang "signature"-nya cocok dengan teks dokumen.
    Pola dengan hit_count tertinggi dicoba lebih dulu (get_all_patterns sudah
    urut DESC) supaya template yang paling sering muncul dicek pertama."""

    for pattern in get_all_patterns():
        try:
            if re.search(pattern.signature_regex, text, flags=re.IGNORECASE | re.MULTILINE):
                increment_hit(pattern.id)
                return pattern
        except re.error:
            # Regex rusak (mis. hasil LLM yang tidak valid) - lewati, jangan
            # sampai menjatuhkan seluruh request.
            continue
    return None


def apply_pattern(text: str, pattern: PatternRecord) -> dict[str, str | None]:
    """Terapkan regex per-field dari pola tersimpan ke teks dokumen."""
    raw: dict[str, str | None] = {}
    for field_key, regex in pattern.field_regex.items():
        value = None
        try:
            m = re.search(regex, text, flags=re.IGNORECASE | re.MULTILINE)
            if m:
                value = (m.group(1) if m.groups() else m.group(0)).strip()
        except re.error:
            value = None
        raw[field_key] = value
    return raw
