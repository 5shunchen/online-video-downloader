"""ovd.api 子包: 第三方数据源访问。"""

from .maccms import (
    Episode,
    MacCMSClient,
    PlaySource,
    VideoDetail,
    VideoSummary,
)

__all__ = [
    "Episode",
    "MacCMSClient",
    "PlaySource",
    "VideoDetail",
    "VideoSummary",
]
