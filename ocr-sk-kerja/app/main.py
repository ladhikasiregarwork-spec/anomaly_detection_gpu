"""
FastAPI service - membungkus seluruh pipeline (app/pipeline/orchestrator.py)
jadi HTTP API + UI, sesuai kotak terakhir diagram: "JSON Response".

Catatan resource (lihat PLAN-OCR-SERVICE-SK-KERJA.md §6):
    Jalankan dengan SATU worker saja (`uvicorn ... --workers 1`, ini sudah
    default di run.py). Menambah worker akan mengalikan pemakaian RAM
    (tiap worker punya salinan model OCR sendiri) dan berisiko dua proses
    berebut VRAM 4GB lewat Ollama secara bersamaan.
"""
from __future__ import annotations

import logging
import multiprocessing
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.schemas import HealthResponse, PatternInfo
from app.pipeline import ocr_engine
from app.pipeline.orchestrator import PipelineError, process_document
from app.storage.pattern_store import count_patterns, get_all_patterns, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ocr-sk-kerja")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Pattern DB siap (%d pola tersimpan).", count_patterns())

    logger.info("Memuat model OCR (RapidOCR, CPU, %d thread)...", settings.ocr_num_threads)
    ocr_engine.warmup()
    logger.info("Model OCR siap.")

    ok = await _check_ollama()
    if ok:
        logger.info("Ollama terdeteksi di %s (model LLM: %s).", settings.ollama_host, settings.llm_model)
    else:
        logger.warning(
            "Ollama TIDAK terdeteksi di %s - tahap LLM (pola dokumen baru) akan gagal "
            "sampai Ollama dijalankan / model %s selesai di-pull.",
            settings.ollama_host,
            settings.llm_model,
        )

    yield  # -- aplikasi berjalan --


async def _check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


app = FastAPI(title="OCR Service SK Kerja", lifespan=lifespan)

WEB_DIR = settings.data_dir.parent / "app" / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/")
async def index():
    return FileResponse(str(WEB_DIR / "static" / "index.html"))


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        cpu_cores=multiprocessing.cpu_count(),
        ocr_backend=f"RapidOCR (CPU, {settings.ocr_num_threads} thread)",
        ocr_threads=settings.ocr_num_threads,
        llm_backend=f"Ollama ({settings.llm_model})",
        llm_model=settings.llm_model,
        ollama_reachable=await _check_ollama(),
        patterns_learned=count_patterns(),
    )


@app.get("/api/patterns", response_model=list[PatternInfo])
async def list_patterns():
    return [
        PatternInfo(
            id=p.id,
            name=p.name,
            signature_regex=p.signature_regex,
            hit_count=p.hit_count,
            created_at=p.created_at,
        )
        for p in get_all_patterns()
    ]


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    content = await file.read()

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(413, f"File terlalu besar (maks {settings.max_upload_mb}MB).")

    try:
        result = await process_document(file.filename or "upload", content)
    except PipelineError as e:
        return JSONResponse(
            status_code=422,
            content={"error": e.message, "stage_trace": [s.model_dump() for s in e.stage_trace]},
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Pipeline gagal tak terduga")
        raise HTTPException(500, f"Terjadi kesalahan internal: {e}") from e

    return result
