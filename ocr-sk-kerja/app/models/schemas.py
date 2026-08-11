"""Skema data (Pydantic) yang dipakai di seluruh pipeline & response API."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class StageTrace(BaseModel):
    """Satu langkah dalam pipeline - dipakai UI untuk menampilkan 'jejak proses'
    persis seperti alur pada diagram, lengkap dengan resource yang dipakai."""

    stage: str
    detail: str = ""
    resource: str = "cpu"          # "cpu" | "gpu" | "none"
    duration_ms: float = 0.0


class FieldResult(BaseModel):
    key: str
    label: str
    value: Optional[str] = None
    is_present: bool = False


class ExtractionResponse(BaseModel):
    filename: str
    format_detected: str                     # "pdf" | "image"
    used_ocr: bool = False
    used_llm: bool = False
    pattern_source: str                      # "existing_pattern" | "new_pattern_llm"
    pattern_id: Optional[int] = None
    pattern_name: Optional[str] = None
    fields: list[FieldResult] = Field(default_factory=list)
    missing_mandatory_fields: list[str] = Field(default_factory=list)
    raw_text_preview: str = ""
    stage_trace: list[StageTrace] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    warning: Optional[str] = None


class PatternInfo(BaseModel):
    id: int
    name: str
    signature_regex: str
    hit_count: int
    created_at: str


class HealthResponse(BaseModel):
    status: str
    cpu_cores: int
    ocr_backend: str
    ocr_threads: int
    llm_backend: str
    llm_model: str
    ollama_reachable: bool
    patterns_learned: int
