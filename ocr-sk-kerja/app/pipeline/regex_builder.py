"""
Pembangun regex deterministik dari hasil LLM.

Kenapa modul ini ada: awalnya LLM (gemma2:2b) diminta menulis regex-nya
SENDIRI untuk tiap field + signature template. Dalam pengujian, model
sekecil ini sering menulis regex yang salah secara sintaks/semantik (mis.
salah menaruh `\n` dalam lookbehind) sehingga pola gagal dipakai ulang di
dokumen berikutnya dengan template sama.

Solusi: LLM hanya diminta menunjuk teks LABEL dan FRASA verbatim yang ada
di dokumen (tugas yang jauh lebih mudah & reliable untuk model kecil).
Regex-nya sendiri dibangun & divalidasi di sini dengan `re.escape`, lalu
diuji harus benar-benar cocok ke teks dokumen saat ini sebelum disimpan -
jadi pola yang tersimpan sudah pasti valid untuk minimal 1 dokumen.
"""
from __future__ import annotations

import re


def _line_bounds(text: str, index: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, index)
    start = 0 if start == -1 else start + 1
    end = text.find("\n", index)
    end = len(text) if end == -1 else end
    return start, end


def build_field_regex(text: str, value: str | None, label_hint: str | None) -> str | None:
    """Bangun regex 1-capture-group untuk satu field, tervalidasi terhadap
    `text`. Kembalikan None kalau tidak berhasil dibangun (field itu nanti
    tetap terisi untuk dokumen SAAT INI dari nilai LLM langsung - hanya
    dokumen template sama berikutnya yang tidak akan otomatis dapat field
    ini lewat regex)."""

    if not value:
        return None

    candidates: list[str] = []

    if label_hint and label_hint.strip():
        candidates.append(re.escape(label_hint.strip()) + r"\s*[:\-]?\s*(.+)")

    idx = text.find(value)
    if idx != -1:
        start, _ = _line_bounds(text, idx)
        label_part = text[start:idx].strip(" :.-\t")
        if label_part:
            candidates.append(re.escape(label_part) + r"\s*[:\-]?\s*(.+)")

    for pattern in candidates:
        try:
            m = re.search(pattern, text, flags=re.IGNORECASE)
        except re.error:
            continue
        if m and m.groups() and value.strip() in m.group(1):
            return pattern

    return None


def build_signature_regex(text: str, signature_phrase: str | None) -> str:
    """Bangun regex penanda template, tervalidasi harus match ke `text`."""

    if signature_phrase and signature_phrase.strip() in text:
        return re.escape(signature_phrase.strip())

    # Fallback: baris non-kosong pertama biasanya kop/judul dokumen -
    # cukup unik untuk jadi penanda template.
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 5:
            return re.escape(line)

    return re.escape(text.strip()[:40]) if text.strip() else r"(?!)"  # (?!) = tidak pernah match
