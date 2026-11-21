from fastapi import FastAPI

from app.routers.offers import router as offers_router
from app.routers.streams import router as streams_router
from app.routers.сampaigns import router as campaigns_router
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT
app = FastAPI(title="Keitaro Wrapper")
app.include_router(offers_router)
app.include_router(streams_router)
app.include_router(campaigns_router)

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

frontend_dir = PROJECT_ROOT / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")