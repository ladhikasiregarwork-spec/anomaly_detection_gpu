"""
Orkestrator: menyambungkan seluruh kotak pada diagram "OCR Service SK Kerja"
jadi satu alur end-to-end, persis urutan pada gambar:

  Format Detection -> (PDF: Text Extraction -> cek 300 char -> [Split Pages -> OCR])
                    -> (JPG/PNG: OCR langsung)
                    -> Pattern Matching -> Have Existing Pattern?
                         -> Ya: Normalizer
                         -> Tidak: LLM -> Store New Pattern Regex -> Normalizer
                    -> Extract Field -> JSON Response

Setiap tahap dicatat di `stage_trace` (nama tahap, resource CPU/GPU, durasi)
supaya UI bisa menampilkan jejak proses yang transparan - termasuk
membuktikan bahwa jalur cepat (template sudah dikenal) tidak pernah
menyentuh GPU sama sekali.
"""
from __future__ import annotations

import io
import time
from contextlib import contextmanager

from PIL import Image

from app.config import settings
from app.models.schemas import ExtractionResponse, StageTrace
from app.pipeline import llm_engine
from app.pipeline.field_config import get_field_keys
from app.pipeline.format_detection import UnsupportedFormatError, detect_format
from app.pipeline.normalizer import normalize_fields
from app.pipeline.ocr_engine import ocr_image, ocr_images
from app.pipeline.pattern_matcher import apply_pattern, find_matching_pattern
from app.pipeline.pdf_split import iter_pdf_pages_as_images
from app.pipeline.regex_builder import build_field_regex, build_signature_regex
from app.pipeline.text_extraction import extract_text_from_pdf
from app.storage.pattern_store import save_pattern


class PipelineError(Exception):
    def __init__(self, message: str, stage_trace: list[StageTrace] | None = None):
        super().__init__(message)
        self.message = message
        self.stage_trace = stage_trace or []


@contextmanager
def _stage(trace: list[StageTrace], name: str, resource: str = "cpu"):
    holder = {"detail": ""}
    t0 = time.perf_counter()
    try:
        yield holder
    finally:
        trace.append(
            StageTrace(
                stage=name,
                detail=holder["detail"],
                resource=resource,
                duration_ms=round((time.perf_counter() - t0) * 1000, 1),
            )
        )


async def process_document(filename: str, content: bytes) -> ExtractionResponse:
    trace: list[StageTrace] = []
    t_start = time.perf_counter()
    used_ocr = False
    used_llm = False
    warning: str | None = None

    # 1) Format Detection --------------------------------------------------
    with _stage(trace, "Format Detection", "cpu") as h:
        try:
            fmt = detect_format(filename, content)
        except UnsupportedFormatError as e:
            raise PipelineError(str(e), trace) from e
        h["detail"] = fmt

    # 2) Ekstraksi teks -------------------------------------------------
    text = ""
    if fmt == "image":
        with _stage(trace, "OCR (RapidOCR - gambar langsung)", "cpu") as h:
            image = Image.open(io.BytesIO(content))
            text = ocr_image(image)
            used_ocr = True
            h["detail"] = f"{len(text)} karakter terbaca"

    else:  # fmt == "pdf"
        with _stage(trace, "Text Extraction (PyMuPDF)", "cpu") as h:
            text = extract_text_from_pdf(content)
            h["detail"] = f"{len(text)} karakter teks native"

        with _stage(trace, f"Cek teks >= {settings.min_text_length} karakter", "cpu") as h:
            has_enough_text = len(text) >= settings.min_text_length
            h["detail"] = "Ya - lewati OCR" if has_enough_text else "Tidak - perlu OCR"

        if not has_enough_text:
            with _stage(trace, "Split PDF Pages", "cpu") as h:
                images = list(iter_pdf_pages_as_images(content))
                h["detail"] = f"{len(images)} halaman di-render @ {settings.pdf_render_dpi} DPI"

            with _stage(trace, "OCR (RapidOCR, CPU)", "cpu") as h:
                text = ocr_images(images)
                used_ocr = True
                h["detail"] = f"{len(images)} halaman -> {len(text)} karakter"

    if not text.strip():
        warning = "Tidak ada teks yang berhasil diekstrak dari dokumen ini."

    # 3) Pattern Matching -------------------------------------------------
    with _stage(trace, "Pattern Matching (Regex Exist)", "cpu") as h:
        pattern = find_matching_pattern(text)
        h["detail"] = pattern.name if pattern else "Tidak ada pola yang cocok"

    with _stage(trace, "Have Existing Pattern?", "cpu") as h:
        h["detail"] = "Ya" if pattern else "Tidak"

    # 4a) Pola sudah dikenal -> langsung terapkan regex tersimpan ----------
    if pattern is not None:
        raw_fields = apply_pattern(text, pattern)
        pattern_source = "existing_pattern"

    # 4b) Pola baru -> LLM mempelajari struktur dokumen + simpan pola -----
    else:
        used_llm = True
        with _stage(trace, "LLM (Gemma via Ollama)", "gpu") as h:
            try:
                llm_result = await llm_engine.learn_pattern_from_text(text)
            except (llm_engine.LLMUnavailableError, llm_engine.LLMParseError) as e:
                raise PipelineError(f"Tahap LLM gagal: {e}", trace) from e
            h["detail"] = llm_result.get("pattern_name", "-")

        raw_fields = {k: v.get("value") for k, v in llm_result.get("fields", {}).items()}

        # Regex dibangun & divalidasi di sini (bukan dipercaya mentah dari
        # LLM) - lihat docstring regex_builder.py untuk alasannya.
        field_regex: dict[str, str] = {}
        unbuilt_fields: list[str] = []
        for key, info in llm_result.get("fields", {}).items():
            regex = build_field_regex(text, info.get("value"), info.get("label_hint"))
            if regex:
                field_regex[key] = regex
            else:
                unbuilt_fields.append(key)

        signature_regex = build_signature_regex(text, llm_result.get("signature_phrase"))

        with _stage(trace, "Store New Pattern Regex", "cpu") as h:
            new_pattern = save_pattern(
                name=llm_result.get("pattern_name", "Pola Baru"),
                signature_regex=signature_regex,
                field_regex=field_regex,
            )
            pattern = new_pattern
            detail = f"Pola '{new_pattern.name}' disimpan (id={new_pattern.id}), {len(field_regex)}/{len(raw_fields)} field regex berhasil dibangun"
            if unbuilt_fields:
                detail += f" (gagal: {', '.join(unbuilt_fields)})"
            h["detail"] = detail

        pattern_source = "new_pattern_llm"

    # 5) Normalizer + Extract Field ---------------------------------------
    with _stage(trace, "Normalizer - Get the mandatory parameter", "cpu") as h:
        fields, missing = normalize_fields(raw_fields)
        h["detail"] = f"{len(get_field_keys()) - len(missing)}/{len(get_field_keys())} field terisi"

    total_duration_ms = round((time.perf_counter() - t_start) * 1000, 1)

    return ExtractionResponse(
        filename=filename,
        format_detected=fmt,
        used_ocr=used_ocr,
        used_llm=used_llm,
        pattern_source=pattern_source,
        pattern_id=pattern.id if pattern else None,
        pattern_name=pattern.name if pattern else None,
        fields=fields,
        missing_mandatory_fields=missing,
        raw_text_preview=text[:500],
        stage_trace=trace,
        total_duration_ms=total_duration_ms,
        warning=warning,
    )
