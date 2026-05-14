"""下载器子包: ffmpeg 调用 + 异步任务队列。"""

from .jobs import DownloadJob, JobManager, JobStatus

__all__ = ["DownloadJob", "JobManager", "JobStatus"]
