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

import sys
from pathlib import Path

# PyInstaller 兼容：优先绝对导入
try:
    from ovd import __version__
    from ovd.api import MacCMSClient
    from ovd.config import Settings
    from ovd.downloader import JobManager
except ImportError:
    from .. import __version__
    from ..api import MacCMSClient
    from ..config import Settings
    from ..downloader import JobManager

# PyInstaller 兼容：从临时目录加载静态文件
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    STATIC_DIR = Path(sys._MEIPASS) / 'ovd' / 'static'
else:
    STATIC_DIR = Path(__file__).resolve().parent.parent / 'static'


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
async def api_search(wd: str, source: str | None = None) -> dict:
    client: MacCMSClient = app.state.client
    items = await client.search(wd)

    # 按数据源筛选
    if source:
        items = [v for v in items if v.source_name == source]

    return {
        "keyword": wd,
        "source": source,
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
                "quality": _detect_quality(v),
            }
            for v in items
        ],
    }


def _detect_quality(v) -> str:
    """根据源信息推断画质"""
    text = (v.source_name + v.remarks + v.type_name).lower()
    if any(k in text for k in ['1080', '1080p', '蓝光', 'bluray', '4k', '超清']):
        return '1080P'
    if any(k in text for k in ['720', '720p', '高清']):
        return '720P'
    return '高清'


async def _validate_source_url(client, url: str) -> bool:
    """验证播放链接是否有效"""
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return False
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type.lower():
            return False
        # 检查内容是否为 m3u8 格式
        text = resp.text.strip()
        return text.startswith("#")
    except Exception:
        return False


@app.get("/api/detail")
async def api_detail(source_name: str, vod_id: int) -> dict:
    client: MacCMSClient = app.state.client
    detail = await client.detail(source_name, vod_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="未找到该剧集")

    # 验证播放源可用性（验证第1集链接）
    httpx_client = client._client
    valid_sources = []
    for s in detail.play_sources:
        if s.episodes and await _validate_source_url(httpx_client, s.episodes[0].url):
            valid_sources.append(s)

    if not valid_sources:
        raise HTTPException(status_code=404, detail="该剧集所有播放源均已失效，请换其他剧集")

    best = valid_sources[0]
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
                "is_recommended": (s is best),
                "episodes": [{"name": e.name, "url": e.url} for e in s.episodes],
            }
            for s in valid_sources
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


import subprocess
from pathlib import Path

@app.post("/api/open-folder")
async def api_open_folder(path: str) -> dict:
    """打开文件所在目录"""
    try:
        p = Path(path).parent
        if not p.exists():
            return {"success": False, "error": "目录不存在"}

        import platform
        system = platform.system()

        # 检测 WSL 环境
        is_wsl = False
        if system == 'Linux':
            wsl_marker = Path('/proc/sys/fs/binfmt_misc/WSLInterop')
            if wsl_marker.exists() or str(p).startswith('/mnt/'):
                is_wsl = True

        # 转换路径为 Windows 格式
        win_path = str(p)
        if is_wsl and win_path.startswith('/mnt/'):
            # /mnt/c/xxx -> C:\xxx
            drive = win_path[5]
            win_path = drive.upper() + ':' + win_path[6:]
            win_path = win_path.replace('/', '\\')
        elif system == 'Windows':
            win_path = str(p.absolute())

        if system == 'Windows':
            # 原生 Windows
            subprocess.run(['explorer', win_path], shell=True)
            return {"success": True, "path": win_path}
        elif is_wsl:
            # WSL 环境通过 PowerShell 调用 explorer
            ps_paths = [
                '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                '/mnt/d/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            ]
            last_error = None
            for ps_path in ps_paths:
                if Path(ps_path).exists():
                    try:
                        # 直接调用 explorer "路径"，比 Start-Process 更可靠
                        # 使用 shell=True 和正确的引号处理中文路径
                        # 注意：路径中的反斜杠在 shell 命令中需要双重转义
                        shell_path = win_path.replace('\\', '\\\\')
                        cmd = f'{ps_path} -Command "explorer \\"{shell_path}\\""'
                        subprocess.run(cmd, shell=True, check=True)
                        return {"success": True, "path": win_path}
                    except Exception as e:
                        last_error = str(e)
            return {"success": False, "error": last_error or "无法找到 PowerShell"}
        elif system == 'Darwin':  # macOS
            subprocess.run(['open', str(p)], check=True)
            return {"success": True, "path": str(p)}
        else:  # Linux (非 WSL)
            try:
                subprocess.run(['xdg-open', str(p)], check=True)
                return {"success": True, "path": str(p)}
            except Exception:
                return {"success": False, "error": "Linux 桌面环境不支持自动打开，请手动打开目录"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/jobs")
async def api_jobs() -> dict:
    manager: JobManager = app.state.manager
    return {"jobs": [j.to_dict() for j in manager.list_jobs()]}


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel(job_id: int) -> dict:
    manager: JobManager = app.state.manager
    ok = manager.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=400, detail="只能取消尚未开始的队列任务")
    return {"id": job_id, "status": "canceled"}


@app.delete("/api/jobs/{job_id}")
async def api_delete_job(job_id: int) -> dict:
    """删除单个下载记录（不删除文件）"""
    manager: JobManager = app.state.manager
    ok = manager.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"id": job_id, "status": "deleted"}


from pydantic import BaseModel
class DeleteJobsRequest(BaseModel):
    ids: list[int] | None = None  # None = 删除全部


@app.post("/api/jobs/delete")
async def api_delete_jobs(req: DeleteJobsRequest | None = None) -> dict:
    """批量删除下载记录（不删除文件），ids=None 表示删除全部"""
    manager: JobManager = app.state.manager
    if req is None or req.ids is None:
        count = manager.delete_all_jobs()
        return {"deleted_count": count, "action": "all"}
    count = 0
    for job_id in req.ids:
        if manager.delete_job(job_id):
            count += 1
    return {"deleted_count": count, "ids": req.ids}
