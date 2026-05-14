"""FastAPI 入口。

提供:
- GET /                   首页 (静态)
- GET /api/search?wd=…    搜索
- GET /api/detail?…       获取分集
- POST /api/download      入队下载 (单集 or 批量)
- GET /api/jobs           列出所有任务
- POST /api/jobs/{id}/cancel  取消队列中的任务
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__
from ..api import MacCMSClient
from ..config import Settings
from ..downloader import JobManager

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class EpisodeIn(BaseModel):
    name: str
    url: str


class DownloadIn(BaseModel):
    video_name: str = Field(..., min_length=1)
    episodes: list[EpisodeIn] = Field(..., min_length=1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.load()
    client = MacCMSClient(settings)
    manager = JobManager(settings)
    await manager.start()
    app.state.settings = settings
    app.state.client = client
    app.state.manager = manager
    try:
        yield
    finally:
        await manager.stop()
        await client.aclose()


app = FastAPI(title="online-video-downloader", version=__version__, lifespan=lifespan)


# --- 页面 ---------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- API ----------------------------------------------------------------

@app.get("/api/version")
async def api_version() -> dict:
    settings: Settings = app.state.settings
    return {
        "version": __version__,
        "download_dir": str(settings.download_dir),
        "sources": [{"name": s.name, "api": s.api} for s in settings.sources],
    }


@app.get("/api/search")
async def api_search(wd: str) -> dict:
    client: MacCMSClient = app.state.client
    items = await client.search(wd)
    return {
        "keyword": wd,
        "count": len(items),
        "items": [
            {
                "source_name": v.source_name,
                "vod_id": v.vod_id,
                "name": v.name,
                "pic": v.pic,
                "remarks": v.remarks,
                "year": v.year,
                "area": v.area,
                "type_name": v.type_name,
            }
            for v in items
        ],
    }


@app.get("/api/detail")
async def api_detail(source_name: str, vod_id: int) -> dict:
    client: MacCMSClient = app.state.client
    detail = await client.detail(source_name, vod_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="未找到该剧集")
    best = detail.best_m3u8_source()
    return {
        "summary": {
            "source_name": detail.summary.source_name,
            "vod_id": detail.summary.vod_id,
            "name": detail.summary.name,
            "pic": detail.summary.pic,
            "remarks": detail.summary.remarks,
            "year": detail.summary.year,
            "area": detail.summary.area,
            "type_name": detail.summary.type_name,
        },
        "play_sources": [
            {
                "flag": s.flag,
                "is_m3u8": s.is_m3u8,
                "is_recommended": (best is not None and s is best),
                "episodes": [{"name": e.name, "url": e.url} for e in s.episodes],
            }
            for s in detail.play_sources
        ],
    }


@app.post("/api/download")
async def api_download(payload: DownloadIn) -> dict:
    manager: JobManager = app.state.manager
    jobs = manager.enqueue_many(
        video_name=payload.video_name,
        episodes=[(e.name, e.url) for e in payload.episodes],
    )
    return {"queued": len(jobs), "jobs": [j.to_dict() for j in jobs]}


@app.get("/api/jobs")
async def api_jobs() -> dict:
    manager: JobManager = app.state.manager
    return {"jobs": [j.to_dict() for j in manager.list_jobs()]}


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel(job_id: int) -> dict:
    manager: JobManager = app.state.manager
    ok = manager.cancel(job_id)
    if not ok:
        raise HTTPException(
            status_code=400, detail="只能取消尚未开始的队列任务"
        )
    return {"id": job_id, "status": "canceled"}
