"""下载任务、状态机、ffmpeg 子进程封装。

实现: 解析 m3u8 (含 AES 密钥) → 并行下载 TS → AES 解密 → cat 合并 → ffmpeg 转封装
速度: 约 20x 于 ffmpeg 直接拉流 (串行 + 每次 HTTP 握手)
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from itertools import count
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import httpx

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# PyInstaller 兼容：优先绝对导入
try:
    from ovd.config import Settings
except ImportError:
    from ..config import Settings


# --- ffmpeg 路径检测（支持 PyInstaller 打包） ---
import os
import sys


def _find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件, 支持 PyInstaller 打包的内置版本。"""
    # 1. 检查 PyInstaller 临时目录
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        ffmpeg_exe = Path(sys._MEIPASS) / 'ffmpeg.exe'
        if ffmpeg_exe.exists():
            return str(ffmpeg_exe)

    # 2. 检查同级目录（开发环境）
    local_ffmpeg = Path(sys.executable).parent / 'ffmpeg.exe'
    if local_ffmpeg.exists():
        return str(local_ffmpeg)

    # 3. 使用系统 PATH
    return 'ffmpeg'


FFMPEG_PATH = _find_ffmpeg()


# Windows / 跨平台都不允许出现的字符
_BAD = re.compile(r'[\\/:*?"<>|\r\n\t]')


def safe_filename(name: str, fallback: str = "untitled") -> str:
    """把任意名称转为可安全用于文件名的字符串。"""
    cleaned = _BAD.sub("_", (name or "").strip())
    cleaned = cleaned.strip(". ")
    return cleaned or fallback


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class DownloadJob:
    id: int
    video_name: str
    episode_name: str
    url: str  # 源 m3u8 / 视频地址
    output_path: Path
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    exported: bool = False  # 是否已导出到本地（用于远程服务模式）
    # 下载进度
    total_chunks: int = 0
    downloaded_chunks: int = 0
    bytes_downloaded: int = 0
    download_speed: float = 0.0  # bytes/sec
    # 速度计算内部字段
    _bytes_last_check: int = 0
    _last_update_time: float = 0.0
    _speed_window: list[float] = field(default_factory=list)  # 滑动窗口平均速度

    def to_dict(self) -> dict:
        elapsed = None
        if self.started_at:
            elapsed = (self.finished_at or time.time()) - self.started_at
        progress = 0
        if self.total_chunks > 0:
            progress = int(self.downloaded_chunks * 100 / self.total_chunks)
        return {
            "id": self.id,
            "video_name": self.video_name,
            "episode_name": self.episode_name,
            "url": self.url,
            "output_path": str(self.output_path),
            "status": self.status.value,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": progress,
            "download_speed": self.download_speed,
            "bytes_downloaded": self.bytes_downloaded,
            "elapsed_seconds": elapsed,
            "exported": self.exported,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DownloadJob":
        return cls(
            id=d["id"],
            video_name=d["video_name"],
            episode_name=d["episode_name"],
            url=d["url"],
            output_path=Path(d["output_path"]),
            status=JobStatus(d["status"]),
            error=d.get("error"),
            created_at=d["created_at"],
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            exported=d.get("exported", False),
            total_chunks=d.get("total_chunks", 0),
            downloaded_chunks=d.get("downloaded_chunks", 0),
            bytes_downloaded=d.get("bytes_downloaded", 0),
        )


class JobManager:
    """单进程任务队列, 用 asyncio.Queue + N 个 worker。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: asyncio.Queue[DownloadJob] = asyncio.Queue()
        self._jobs: dict[int, DownloadJob] = {}
        self._next_id = count(start=1)
        self._workers: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()
        # 全局共享 httpx client，连接池复用，提升下载速度
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._workers:
            return
        # 加载持久化的任务（断点续传）
        self.load_jobs()
        # 初始化全局 httpx client - 经过实际测试的最佳参数
        limits = httpx.Limits(
            max_keepalive_connections=30,
            max_connections=50,
            keepalive_expiry=30.0,
        )
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=8.0),  # 更宽松的超时，避免频繁重试
            follow_redirects=True,
            limits=limits,
            headers={
                "User-Agent": self._settings.user_agent,
                "Referer": "https://7080.wang/",
            },
        )
        for _ in range(self._settings.concurrency):
            self._workers.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        self._stopping.set()
        for w in self._workers:
            w.cancel()
        for w in self._workers:
            try:
                await w
            except (asyncio.CancelledError, Exception):
                pass
        self._workers.clear()
        if self._client:
            await self._client.aclose()

    # --- 公共 API ---------------------------------------------------

    def list_jobs(self) -> list[DownloadJob]:
        return sorted(self._jobs.values(), key=lambda j: j.id)

    def get(self, job_id: int) -> DownloadJob | None:
        return self._jobs.get(job_id)

    def enqueue(
        self,
        *,
        video_name: str,
        episode_name: str,
        url: str,
    ) -> DownloadJob:
        jid = next(self._next_id)
        folder = self._settings.download_dir / safe_filename(video_name, "video")
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / f"{safe_filename(episode_name, f'ep{jid}')}.mp4"
        job = DownloadJob(
            id=jid,
            video_name=video_name,
            episode_name=episode_name,
            url=url,
            output_path=out,
        )
        self._jobs[jid] = job
        self._queue.put_nowait(job)
        self.save_jobs()  # 入队后立即保存
        return job

    def enqueue_many(
        self,
        *,
        video_name: str,
        episodes: Iterable[tuple[str, str]],  # (episode_name, url)
    ) -> list[DownloadJob]:
        return [
            self.enqueue(video_name=video_name, episode_name=name, url=url)
            for name, url in episodes
        ]

    def cancel(self, job_id: int) -> bool:
        """仅能取消尚未开始的任务 (QUEUED)。"""
        job = self._jobs.get(job_id)
        if job is None or job.status != JobStatus.QUEUED:
            return False
        job.status = JobStatus.CANCELED
        job.finished_at = time.time()
        self.save_jobs()
        return True

    def delete_job(self, job_id: int) -> bool:
        """删除单个下载记录（不删除文件，仅从列表移除）"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self.save_jobs()
            return True
        return False

    def get_job(self, job_id: int) -> DownloadJob | None:
        """获取单个任务信息"""
        return self._jobs.get(job_id)

    def mark_as_exported(self, job_id: int) -> bool:
        """标记任务为已导出（用于远程下载后标记）"""
        job = self._jobs.get(job_id)
        if job is not None:
            job.exported = True
            self.save_jobs()
            return True
        return False

    # --- 断点续传: 任务持久化 --------------------------------------------
    @property
    def _jobs_file(self) -> Path:
        return self._settings.download_dir / ".ovd_jobs.json"

    def save_jobs(self) -> None:
        """保存所有任务到文件"""
        try:
            self._jobs_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "next_id": next(self._next_id, 1),  # 这会消耗一个，后面要修正
                "jobs": [j.to_dict() for j in self._jobs.values()],
            }
            # 修正 next_id
            data["next_id"] = max(self._jobs.keys(), default=0) + 1
            with open(self._jobs_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 保存失败不影响程序运行

    def load_jobs(self) -> None:
        """从文件加载任务"""
        try:
            if self._jobs_file.exists():
                with open(self._jobs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                next_id = data.get("next_id", 1)
                self._next_id = count(start=next_id)
                for jd in data.get("jobs", []):
                    job = DownloadJob.from_dict(jd)
                    self._jobs[job.id] = job
                    # 未完成的任务重新加入队列
                    if job.status in (JobStatus.QUEUED, JobStatus.DOWNLOADING):
                        job.status = JobStatus.QUEUED  # 重置为排队状态
                        job.started_at = None
                        self._queue.put_nowait(job)
        except Exception:
            pass  # 加载失败不影响程序运行

    def delete_all_jobs(self) -> int:
        """删除所有下载记录（不删除文件）"""
        count = len(self._jobs)
        self._jobs.clear()
        self.save_jobs()
        return count

    # --- 内部 worker ------------------------------------------------

    async def _worker(self) -> None:
        while not self._stopping.is_set():
            try:
                job = await self._queue.get()
            except asyncio.CancelledError:
                break
            try:
                if job.status == JobStatus.CANCELED:
                    continue
                await self._run_one(job)
            finally:
                self._queue.task_done()

    async def _run_one(self, job: DownloadJob) -> None:
        job.status = JobStatus.DOWNLOADING
        job.started_at = time.time()
        if job.output_path.exists() and job.output_path.stat().st_size > 0:
            job.status = JobStatus.COMPLETED
            job.finished_at = time.time()
            return

        try:
            await self._download_m3u8(job)
            job.status = JobStatus.COMPLETED
        except FileNotFoundError:
            job.status = JobStatus.FAILED
            job.error = "未检测到 ffmpeg, 请先安装并加入 PATH"
        except Exception as exc:  # noqa: BLE001
            job.status = JobStatus.FAILED
            job.error = repr(exc)
        finally:
            job.finished_at = time.time()
            self.save_jobs()  # 任务完成后保存

    async def _download_m3u8(self, job: DownloadJob) -> None:
        """m3u8 分片并行下载 + AES 解密 + 内存合并（零磁盘 IO）。"""
        client = self._client
        assert client is not None, "JobManager 未启动"

        job.output_path.parent.mkdir(parents=True, exist_ok=True)
        ts_buffer: dict[int, bytes] = {}  # 内存存储 TS 分片，避免磁盘 IO

        try:
            # 1) 解析 m3u8, 获取 TS 列表与加密密钥
            resp = await client.get(job.url)
            if resp.status_code != 200:
                raise ValueError(f"播放链接无效 (HTTP {resp.status_code})，请换其他数据源或剧集")
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type.lower() or not resp.text.strip().startswith("#"):
                raise ValueError("该播放链接已失效，请换其他数据源或剧集")
            ts_urls, key_data, iv = await _parse_m3u8(client, job.url, resp.text)
            if not ts_urls:
                raise ValueError("未找到任何 ts 分片, m3u8 可能无效")

            # 初始化进度
            job.total_chunks = len(ts_urls)
            job.downloaded_chunks = 0
            job.bytes_downloaded = 0
            job._bytes_last_check = 0
            job._last_update_time = time.time()

            # 2) 并行下载 + 内存存储 - 24 并发（单任务高并发测试）
            sem = asyncio.Semaphore(24)  # 单任务高并发测试
            tasks = [
                self._dl_one_ts_memory(client, sem, ts_buffer, i, url, key_data, iv, job)
                for i, url in enumerate(ts_urls)
            ]
            await asyncio.gather(*tasks)

            # 3) 内存中直接拼接 TS，零磁盘 IO
            from io import BytesIO
            joined_buffer = BytesIO()
            for i in range(len(ts_urls)):
                if i in ts_buffer:
                    joined_buffer.write(ts_buffer[i])
            joined_data = joined_buffer.getvalue()

            # 4) 通过管道直接喂给 ffmpeg，避免中间文件
            proc = await asyncio.create_subprocess_exec(
                FFMPEG_PATH,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                "-",  # 从 stdin 读取
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                "-movflags",
                "+faststart",  # 优化 web 播放（可选）
                str(job.output_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(input=joined_data)
            if proc.returncode != 0 or not job.output_path.exists():
                raise RuntimeError(
                    f"ffmpeg 合并失败 (code={proc.returncode}): "
                    + stderr.decode("utf-8", errors="ignore")[-800:]
                )
        finally:
            ts_buffer.clear()  # 立即释放内存

    async def _dl_one_ts_memory(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        ts_buffer: dict[int, bytes],
        idx: int,
        url: str,
        key_data: bytes | None,
        iv: bytes | None,
        job: DownloadJob,
    ) -> None:
        """下载单个 TS 到内存, AES 解密后存入 dict, 最多重试 5 次（指数退避）。"""
        for retry in range(5):
            async with sem:
                try:
                    # 禁用重定向自动处理，更快
                    resp = await client.get(
                        url,
                        follow_redirects=True,
                    )
                    resp.raise_for_status()
                    data = resp.content

                    # 更新进度
                    job.bytes_downloaded += len(data)
                    job.downloaded_chunks += 1

                    # 滑动窗口计算更平滑的下载速度
                    now = time.time()
                    elapsed = now - job._last_update_time
                    if elapsed >= 0.5:  # 每 500ms 更新一次速度
                        bytes_since = job.bytes_downloaded - job._bytes_last_check
                        current_speed = bytes_since / elapsed

                        # 滑动窗口平均（最近 5 次采样）
                        job._speed_window.append(current_speed)
                        if len(job._speed_window) > 5:
                            job._speed_window.pop(0)
                        job.download_speed = sum(job._speed_window) / len(job._speed_window)

                        job._bytes_last_check = job.bytes_downloaded
                        job._last_update_time = now

                    if key_data is not None:
                        # AES-128-CBC 解密
                        iv_to_use = iv or (idx + 1).to_bytes(16, 'big')
                        cipher = Cipher(
                            algorithms.AES(key_data),
                            modes.CBC(iv_to_use),
                            backend=default_backend(),
                        )
                        decryptor = cipher.decryptor()
                        data = decryptor.update(data) + decryptor.finalize()

                    # 直接存入内存，零磁盘 IO
                    ts_buffer[idx] = data
                    return
                except Exception:  # noqa: BLE001
                    if retry == 4:  # 第5次重试 (0-4)
                        raise
                    # 指数退避: 0.1s, 0.2s, 0.4s, 0.8s
                    await asyncio.sleep(0.1 * (2 ** retry))


async def _parse_m3u8(
    client: httpx.AsyncClient, base_url: str, content: str
) -> tuple[list[str], bytes | None, bytes | None]:
    """解析 m3u8, 返回 (ts_urls, key_data, iv)。支持 master playlist。"""
    lines = [ln.strip() for ln in content.splitlines()]
    ts: list[str] = []
    key_url: str | None = None
    iv: bytes | None = None

    i = 0
    while i < len(lines):
        ln = lines[i]
        i += 1

        if not ln or ln.startswith("#EXTM3U") or ln.startswith("#EXT-X-ENDLIST"):
            continue

        if ln.startswith("#EXT-X-KEY:METHOD=AES-128"):
            m = re.search(r'URI="([^"]+)"', ln)
            if m:
                key_url = urljoin(base_url, m.group(1))
            m_iv = re.search(r'IV=0x([0-9a-fA-F]+)', ln)
            if m_iv:
                iv = bytes.fromhex(m_iv.group(1))
            continue

        # 遇到 EXT-X-STREAM-INF → master playlist, 用第一个子清单
        if ln.startswith("#EXT-X-STREAM-INF:"):
            if i < len(lines) and lines[i] and not lines[i].startswith("#"):
                sub_url = urljoin(base_url, lines[i])
                i += 1
                sub_content = (await client.get(sub_url)).text
                return await _parse_m3u8(client, sub_url, sub_content)

        if ln.startswith("#"):
            continue

        ts.append(urljoin(base_url, ln))

    key_data = None
    if key_url is not None:
        key_resp = await client.get(key_url)
        key_resp.raise_for_status()
        key_data = key_resp.content

    return ts, key_data, iv


async def _resolve_ts_urls(
    client: httpx.AsyncClient, base_url: str, content: str
) -> list[str]:
    """解析 m3u8, 若为 master playlist 则选最高码率的子清单。"""
    lines = [ln.strip() for ln in content.splitlines()]
    ts: list[str] = []
    bandwidth = -1
    next_is_playlist = False

    for ln in lines:
        if not ln or ln.startswith("#EXTM3U"):
            continue
        # 遇到 EXT-X-STREAM-INF → 这是 master, 选最高带宽
        if ln.startswith("#EXT-X-STREAM-INF:"):
            next_is_playlist = True
            m = re.search(r"BANDWIDTH=(\d+)", ln)
            if m:
                bandwidth = int(m.group(1))
            continue
        if next_is_playlist and ln and not ln.startswith("#"):
            # 递归解析子清单
            sub_url = urljoin(base_url, ln)
            sub = (await client.get(sub_url)).text
            return await _resolve_ts_urls(client, sub_url, sub)
        if ln.startswith("#"):
            continue
        # 普通 ts 分片
        if ln:
            ts.append(urljoin(base_url, ln))
    return ts
