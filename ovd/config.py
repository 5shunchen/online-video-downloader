"""配置加载: 数据源列表、下载目录、并发数。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Source:
    """单个 MacCMS V10 采集站。"""

    name: str
    api: str  # 形如 https://example.com/api.php/provide/vod


# 默认数据源 (MacCMS V10 标准接口, 与 7080.wang 同类资源)
# 按稳定性排序，推荐优先使用靠前的源
DEFAULT_SOURCES: tuple[Source, ...] = (
    Source(name="光速资源", api="https://api.guangsuapi.com/api.php/provide/vod"),
    Source(name="量子资源", api="https://cj.lziapi.com/api.php/provide/vod"),
    Source(name="暴风云资源", api="https://bfzyapi.com/api.php/provide/vod"),
)


@dataclass(frozen=True)
class Settings:
    download_dir: Path
    sources: tuple[Source, ...] = field(default_factory=lambda: DEFAULT_SOURCES)
    concurrency: int = 3  # 同时下载集数 (每集内部 8 并发拉 TS)
    request_timeout: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    @classmethod
    def load(cls) -> "Settings":
        download_dir = Path(
            os.environ.get("OVD_DOWNLOAD_DIR", "./downloads")
        ).expanduser().resolve()
        download_dir.mkdir(parents=True, exist_ok=True)

        concurrency = int(os.environ.get("OVD_CONCURRENCY", "1"))
        return cls(
            download_dir=download_dir,
            sources=DEFAULT_SOURCES,
            concurrency=max(1, concurrency),
        )
