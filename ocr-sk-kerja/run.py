"""
Entry point untuk menjalankan service.

SENGAJA workers=1 (lihat catatan resource di app/main.py) - jangan naikkan
tanpa mempertimbangkan RAM/VRAM yang tersedia.
"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=1,
        log_level="info",
    )
