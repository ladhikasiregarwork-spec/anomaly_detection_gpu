"""
Tahap "Normalizer - Get the mandatory parameter" + "Extract Field" pada diagram.

Beban: string processing murni Python - CPU, instan.
"""
from __future__ import annotations

import re

from app.models.schemas import FieldResult
from app.pipeline.field_config import get_mandatory_fields

_BULAN_ID = {
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12",
}

_DATE_ID_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_BULAN_ID.keys()) + r")\s+(\d{4})",
    flags=re.IGNORECASE,
)
_DATE_NUMERIC_RE = re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})")


def _normalize_date(raw: str) -> str:
    m = _DATE_ID_RE.search(raw)
    if m:
        day, bulan_name, year = m.groups()
        month = _BULAN_ID[bulan_name.lower()]
        return f"{year}-{month}-{int(day):02d}"

    m = _DATE_NUMERIC_RE.search(raw)
    if m:
        day, month, year = m.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    return raw.strip()


def _normalize_string(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip(" :.-\t\n")


def _normalize_value(raw: str, field_type: str) -> str:
    raw = raw.strip()
    if field_type == "date":
        return _normalize_date(raw)
    return _normalize_string(raw)


def normalize_fields(raw_fields: dict[str, str | None]) -> tuple[list[FieldResult], list[str]]:
    """Normalisasi nilai mentah per field & tentukan field wajib mana yang
    masih hilang (dipakai UI untuk menandai perlu input manual)."""

    results: list[FieldResult] = []
    missing: list[str] = []

    for field in get_mandatory_fields():
        key, label, ftype = field["key"], field["label"], field.get("type", "string")
        raw_value = raw_fields.get(key)

        if raw_value:
            value = _normalize_value(str(raw_value), ftype)
            results.append(FieldResult(key=key, label=label, value=value, is_present=True))
        else:
            results.append(FieldResult(key=key, label=label, value=None, is_present=False))
            missing.append(key)

    return results, missing
