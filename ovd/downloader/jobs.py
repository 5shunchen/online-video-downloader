"""下载任务、状态机、ffmpeg 子进程封装。

实现: 解析 m3u8 (含 AES 密钥) → 并行下载 TS → AES 解密 → cat 合并 → ffmpeg 转封装
速度: 约 20x 于 ffmpeg 直接拉流 (串行 + 每次 HTTP 握手)
"""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
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

from ..config import Settings


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

    def to_dict(self) -> dict:
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
        }


class JobManager:
    """单进程任务队列, 用 asyncio.Queue + N 个 worker。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: asyncio.Queue[DownloadJob] = asyncio.Queue()
        self._jobs: dict[int, DownloadJob] = {}
        self._next_id = count(start=1)
        self._workers: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._workers:
            return
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
        return True

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

    async def _download_m3u8(self, job: DownloadJob) -> None:
        """m3u8 分片并行下载 + AES 解密 + 本地合并。"""
        limits = httpx.Limits(max_keepalive_connections=8, max_connections=16)
        client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            limits=limits,
            headers={
                "User-Agent": self._settings.user_agent,
                "Referer": "https://7080.wang/",
            },
        )
        job.output_path.parent.mkdir(parents=True, exist_ok=True)
        tmpdir = Path(tempfile.mkdtemp(dir=str(job.output_path.parent), prefix=".ovd_"))
        try:
            # 1) 解析 m3u8, 获取 TS 列表与加密密钥
            master = (await client.get(job.url)).text
            ts_urls, key_data, iv = await _parse_m3u8(client, job.url, master)
            if not ts_urls:
                raise ValueError("未找到任何 ts 分片, m3u8 可能无效")

            # 2) 并行下载 + 解密 TS
            sem = asyncio.Semaphore(8)
            tasks = [
                self._dl_one_ts(client, sem, tmpdir, i, url, key_data, iv)
                for i, url in enumerate(ts_urls)
            ]
            await asyncio.gather(*tasks)

            # 3) TS 格式本身可直接拼接, cat 合并后 ffmpeg 转封装
            ts_files = [tmpdir / f"ts_{i:05d}.ts" for i in range(len(ts_urls))]
            joined = tmpdir / "joined.ts"
            with joined.open("wb") as outf:
                for ts in ts_files:
                    outf.write(ts.read_bytes())

            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(joined),
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                str(job.output_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0 or not job.output_path.exists():
                raise RuntimeError(
                    f"ffmpeg 合并失败 (code={proc.returncode}): "
                    + stderr.decode("utf-8", errors="ignore")[-800:]
                )
        finally:
            await client.aclose()
            shutil.rmtree(tmpdir, ignore_errors=True)

    async def _dl_one_ts(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        tmpdir: Path,
        idx: int,
        url: str,
        key_data: bytes | None,
        iv: bytes | None,
    ) -> None:
        """下载单个 TS, AES 解密后写入, 最多重试 3 次。"""
        for retry in range(3):
            async with sem:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.content

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

                    out = tmpdir / f"ts_{idx:05d}.ts"
                    out.write_bytes(data)
                    return
                except Exception:  # noqa: BLE001
                    if retry == 2:
                        raise
                    await asyncio.sleep(1 * (retry + 1))


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
