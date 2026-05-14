"""MacCMS V10 客户端: 搜索、获取详情、解析分集 m3u8。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable

import httpx

# PyInstaller 兼容：优先绝对导入
try:
    from ovd.config import Settings, Source
except ImportError:
    from ..config import Settings, Source


@dataclass(frozen=True)
class Episode:
    """一集视频 (来自单一播放源)."""

    name: str  # "第01集"
    url: str  # m3u8 直链或网页播放地址


@dataclass(frozen=True)
class PlaySource:
    """单个剧集的某个播放源 (一个视频可能有多个源, 选 m3u8 直链优先)."""

    flag: str  # MacCMS 的 vod_play_from, 例如 "gsm3u8"
    episodes: tuple[Episode, ...]

    @property
    def is_m3u8(self) -> bool:
        # 启发式: 直链 m3u8 / flag 含 m3u8 / 第一集 url 以 .m3u8 结尾
        if not self.episodes:
            return False
        first = self.episodes[0].url.lower()
        return first.endswith(".m3u8") or "m3u8" in self.flag.lower()


@dataclass(frozen=True)
class VideoSummary:
    """搜索结果摘要。"""

    source_name: str  # 数据源 (光速资源/量子资源 等)
    vod_id: int
    name: str
    pic: str
    remarks: str  # "第162集" 之类
    year: str
    area: str
    type_name: str


@dataclass(frozen=True)
class VideoDetail:
    summary: VideoSummary
    play_sources: tuple[PlaySource, ...]

    def best_m3u8_source(self) -> PlaySource | None:
        for s in self.play_sources:
            if s.is_m3u8:
                return s
        return self.play_sources[0] if self.play_sources else None


def _split(value: str, sep: str) -> list[str]:
    return [p for p in value.split(sep) if p != ""]


def _parse_play(vod_play_from: str, vod_play_url: str) -> tuple[PlaySource, ...]:
    flags = _split(vod_play_from or "", "$$$")
    groups = _split(vod_play_url or "", "$$$")
    out: list[PlaySource] = []
    # 个别站点 flags 与 groups 长度可能不一致, 取最短安全切。
    for flag, group in zip(flags, groups):
        eps: list[Episode] = []
        for item in _split(group, "#"):
            if "$" not in item:
                continue
            name, _, url = item.partition("$")
            name = name.strip()
            url = url.strip()
            if not url:
                continue
            eps.append(Episode(name=name or url, url=url))
        if eps:
            out.append(PlaySource(flag=flag, episodes=tuple(eps)))
    return tuple(out)


def _summary_from_item(source: Source, item: dict) -> VideoSummary:
    return VideoSummary(
        source_name=source.name,
        vod_id=int(item.get("vod_id") or 0),
        name=str(item.get("vod_name") or ""),
        pic=str(item.get("vod_pic") or ""),
        remarks=str(item.get("vod_remarks") or ""),
        year=str(item.get("vod_year") or ""),
        area=str(item.get("vod_area") or ""),
        type_name=str(item.get("vod_class") or item.get("type_name") or ""),
    )


class MacCMSClient:
    """异步客户端, 复用 httpx.AsyncClient。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            timeout=settings.request_timeout,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def sources(self) -> Iterable[Source]:
        return self._settings.sources

    async def search_one(self, source: Source, keyword: str) -> list[VideoSummary]:
        params = {"ac": "list", "wd": keyword}
        try:
            r = await self._client.get(source.api, params=params)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return []
        items = data.get("list") or []
        return [_summary_from_item(source, x) for x in items if x.get("vod_id")]

    async def search(self, keyword: str) -> list[VideoSummary]:
        keyword = (keyword or "").strip()
        if not keyword:
            return []
        results = await asyncio.gather(
            *(self.search_one(s, keyword) for s in self._settings.sources)
        )
        merged: list[VideoSummary] = []
        for batch in results:
            merged.extend(batch)
        return merged

    async def detail(self, source_name: str, vod_id: int) -> VideoDetail | None:
        source = next(
            (s for s in self._settings.sources if s.name == source_name), None
        )
        if source is None:
            return None
        params = {"ac": "videolist", "ids": str(vod_id)}
        try:
            r = await self._client.get(source.api, params=params)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return None
        items = data.get("list") or []
        if not items:
            return None
        item = items[0]
        return VideoDetail(
            summary=_summary_from_item(source, item),
            play_sources=_parse_play(
                item.get("vod_play_from", ""), item.get("vod_play_url", "")
            ),
        )
