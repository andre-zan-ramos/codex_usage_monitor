from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .parser import SessionMonitor


monitor = SessionMonitor(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    monitor.scan()
    yield


app = FastAPI(title="Codex Usage Monitor", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5177", "http://localhost:5177"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def api_health():
    return {"status": "ok", "read_only": True, "sessions_dir_exists": settings.sessions_dir.exists()}


@app.get("/api/dashboard")
def api_dashboard():
    monitor.scan()
    return monitor.dashboard()


@app.get("/api/threads/{thread_id}")
def api_thread(thread_id: str):
    monitor.scan()
    result = monitor.thread(thread_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Thread não encontrada")
    return result


dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
