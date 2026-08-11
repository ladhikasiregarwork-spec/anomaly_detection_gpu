"""Smoke test cepat untuk jalur cepat (tanpa OCR/LLM) - pastikan modul inti
(format detection, text extraction, pattern matching, normalizer) berfungsi
sebelum uji coba lewat UI. Jalankan: .venv\\Scripts\\python.exe scripts\\smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # PyMuPDF

from app.pipeline.format_detection import detect_format
from app.pipeline.text_extraction import extract_text_from_pdf
from app.pipeline.normalizer import normalize_fields
from app.pipeline.pattern_matcher import apply_pattern, find_matching_pattern
from app.storage.pattern_store import init_db, save_pattern

SAMPLE_TEXT = """PEMERINTAH KABUPATEN CONTOH
SURAT KEPUTUSAN
Nomor : 800/123/SK/2026

Tentang Pengangkatan Pegawai

Nama         : Budi Santoso
NIP.         : 198501012010011001
Jabatan      : Staff Administrasi
Unit Kerja   : Dinas Pendidikan Kabupaten Contoh
Tanggal SK   : 5 Januari 2026
TMT          : 1 Februari 2026

Ditetapkan di Contoh pada tanggal 5 Januari 2026.
Demikian surat keputusan ini dibuat untuk dilaksanakan sebagaimana mestinya
oleh pihak-pihak yang berkepentingan sesuai dengan ketentuan yang berlaku
di lingkungan pemerintah kabupaten.
"""

def make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def main():
    print("1) Format Detection...")
    pdf_bytes = make_pdf_bytes(SAMPLE_TEXT)
    fmt = detect_format("test_sk.pdf", pdf_bytes)
    assert fmt == "pdf", fmt
    print("   OK ->", fmt)

    print("2) Text Extraction (PyMuPDF)...")
    text = extract_text_from_pdf(pdf_bytes)
    print(f"   OK -> {len(text)} karakter")
    assert len(text) > 50

    print("3) Init pattern DB + simpan pola contoh...")
    init_db()
    pattern = save_pattern(
        name="SK Pengangkatan Kab. Contoh",
        signature_regex=r"SURAT KEPUTUSAN",
        field_regex={
            "nomor_sk": r"Nomor\s*:\s*(.+)",
            "nama": r"Nama\s*:\s*(.+)",
            "nip": r"NIP\.?\s*:\s*(\d+)",
            "jabatan": r"Jabatan\s*:\s*(.+)",
            "unit_kerja": r"Unit Kerja\s*:\s*(.+)",
            "tanggal_sk": r"Tanggal SK\s*:\s*(.+)",
            "tmt": r"TMT\s*:\s*(.+)",
        },
    )
    print("   OK -> pattern id", pattern.id)

    print("4) Pattern Matching...")
    found = find_matching_pattern(text)
    assert found is not None, "Pola seharusnya ketemu!"
    print("   OK -> pola ditemukan:", found.name)

    print("5) Apply pattern + Normalizer...")
    raw = apply_pattern(text, found)
    print("   raw:", raw)
    fields, missing = normalize_fields(raw)
    for f in fields:
        print(f"   - {f.label}: {f.value!r} (present={f.is_present})")
    print("   missing:", missing)

    assert not missing, f"Ada field wajib yang hilang: {missing}"
    print("\nSEMUA TEST JALUR CEPAT (CPU-only) LULUS.")


if __name__ == "__main__":
    main()
