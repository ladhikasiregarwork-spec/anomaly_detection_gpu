"""Loader untuk daftar field wajib (data/field_config.json).

Dipisah dari config.py supaya field bisa diubah oleh pengguna non-teknis
(edit JSON) tanpa menyentuh kode maupun restart proses install.
"""
from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_mandatory_fields() -> list[dict]:
    with open(settings.field_config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["mandatory_fields"]


def get_field_keys() -> list[str]:
    return [f["key"] for f in get_mandatory_fields()]


def get_field_label(key: str) -> str:
    for f in get_mandatory_fields():
        if f["key"] == key:
            return f["label"]
    return key
