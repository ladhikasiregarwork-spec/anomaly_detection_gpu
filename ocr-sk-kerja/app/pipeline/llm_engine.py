"""
Tahap "LLM (Gemma/GPT)" pada diagram - kotak kuning "GPU Resource".

Keputusan desain (lihat PLAN-OCR-SERVICE-SK-KERJA.md §4.2):
    - Hanya dipanggil saat "Have Existing Pattern?" = No, yaitu dokumen
      dengan TEMPLATE BARU yang belum pernah dilihat. Ini jarang terjadi
      dibanding total dokumen, jadi model kecil + latensi beberapa detik
      masih sangat wajar dipakai.
    - Model default: gemma2:2b terkuantisasi (lewat Ollama) - muat nyaman
      di VRAM 4GB GTX 1050 Ti. JANGAN pakai model 7B+ di GPU ini.
    - Konkurensi GPU dibatasi ketat (semaphore = 1, lihat app/utils/concurrency.py)
      supaya tidak ada 2 request LLM berebut VRAM 4GB secara bersamaan.
    - `keep_alive` pendek (default 5 menit) supaya Ollama otomatis
      melepas model dari VRAM saat idle - GPU tidak terus "disandera".
    - Fallback opsional ke cloud API (lihat settings.cloud_llm_api_key) kalau
      Ollama tidak tersedia / gagal - tanpa perlu upgrade hardware.
"""
from __future__ import annotations

import json
import re

import httpx

from app.config import settings
from app.pipeline.field_config import get_mandatory_fields
from app.utils.concurrency import llm_semaphore


class LLMUnavailableError(Exception):
    pass


class LLMParseError(Exception):
    pass


def _build_prompt(text: str) -> str:
    fields = get_mandatory_fields()
    field_list = "\n".join(f'  - "{f["key"]}": {f["label"]}' for f in fields)
    field_keys = [f["key"] for f in fields]

    # Catatan desain: LLM SENGAJA tidak diminta menulis regex sendiri - model
    # kecil (2B) terbukti tidak reliable menulis sintaks regex yang benar.
    # LLM cukup menunjuk teks label/frasa VERBATIM; regex dibangun & divalidasi
    # secara deterministik di app/pipeline/regex_builder.py.
    return f"""Anda adalah asisten ekstraksi data dokumen SK Kerja (Surat Keputusan) Indonesia.
Diberikan teks hasil OCR/ekstraksi dari sebuah dokumen. Tugas Anda:

1. Baca teks dan cari nilai untuk field-field wajib berikut:
{field_list}

2. Untuk setiap field, salin PERSIS (verbatim, apa adanya dari teks) dua hal:
   - "value": nilai field tersebut di dokumen ini
   - "label_hint": teks label yang muncul TEPAT SEBELUM nilai itu pada baris
     yang sama (contoh: "Nomor :", "NIP.", "Jabatan"). Jangan mengarang atau
     mengubah ejaan, salin persis dari dokumen.

3. Salin juga "signature_phrase": satu potongan teks verbatim (satu baris
   atau frasa pendek) dari bagian judul/kop dokumen yang pasti selalu ada di
   SEMUA dokumen dengan template yang sama (bukan nilai yang berubah-ubah per
   dokumen, misalnya JANGAN pakai nomor surat atau nama orang).

4. Beri "pattern_name": nama singkat untuk template ini.

Balas HANYA dengan JSON valid, tanpa teks lain, dengan struktur persis:
{{
  "pattern_name": "...",
  "signature_phrase": "...",
  "fields": {{
    "field_key": {{"value": "...", "label_hint": "..."}},
    ...
  }}
}}

Field keys yang WAJIB ada di "fields": {field_keys}

=== TEKS DOKUMEN ===
{text[:6000]}
=== AKHIR TEKS ===
"""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Model kadang menambahkan teks di luar JSON walau sudah diminta - ambil
    # blok {...} pertama yang valid sebagai fallback.
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise LLMParseError(f"Gagal parse JSON dari LLM: {e}") from e
    raise LLMParseError("Respons LLM tidak mengandung JSON yang valid.")


async def _call_ollama(prompt: str) -> str:
    url = f"{settings.ollama_host}/api/generate"
    payload = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": settings.llm_keep_alive,
        "options": {
            "temperature": 0,
            "num_ctx": settings.llm_num_ctx,
        },
    }
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        for attempt in range(settings.llm_max_retries + 1):
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()["response"]
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                raise LLMUnavailableError(
                    f"Tidak bisa terhubung ke Ollama di {settings.ollama_host}. "
                    "Pastikan aplikasi Ollama sedang berjalan."
                ) from e
            except Exception as e:  # noqa: BLE001 - retry lalu lempar ulang
                last_error = e
    raise LLMUnavailableError(f"Ollama gagal merespons setelah beberapa percobaan: {last_error}")


async def _call_cloud(prompt: str) -> str:
    if not settings.cloud_llm_api_key:
        raise LLMUnavailableError("Cloud LLM fallback belum dikonfigurasi (cloud_llm_api_key kosong).")

    url = f"{settings.cloud_llm_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.cloud_llm_api_key}"}
    payload = {
        "model": settings.cloud_llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def learn_pattern_from_text(text: str) -> dict:
    """Panggil LLM untuk mempelajari template dokumen baru: nilai field +
    regex untuk dipakai ulang. Dilindungi semaphore supaya GPU 4GB tidak
    dipakai >1 request LLM sekaligus."""

    prompt = _build_prompt(text)

    async with llm_semaphore:
        try:
            raw = await _call_ollama(prompt)
        except LLMUnavailableError:
            if settings.cloud_llm_api_key:
                raw = await _call_cloud(prompt)
            else:
                raise

    data = _extract_json(raw)

    if "fields" not in data or "signature_phrase" not in data:
        raise LLMParseError("Respons LLM tidak lengkap (field 'fields'/'signature_phrase' hilang).")

    return data
