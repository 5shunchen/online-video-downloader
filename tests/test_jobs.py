"""单元测试: 文件名 / 任务管理。"""

from pathlib import Path

import pytest

from ovd.config import Settings
from ovd.downloader.jobs import JobManager, JobStatus, safe_filename


def test_safe_filename_strips_bad_chars():
    assert safe_filename('遮天/第01集') == '遮天_第01集'
    assert safe_filename('a:b*c?d"e<f>g|h') == 'a_b_c_d_e_f_g_h'
    assert safe_filename('   ') == 'untitled'


@pytest.mark.asyncio
async def test_enqueue_and_cancel(tmp_path: Path):
    settings = Settings(download_dir=tmp_path, concurrency=1)
    mgr = JobManager(settings)
    job = mgr.enqueue(
        video_name='测试剧',
        episode_name='第01集',
        url='https://example.com/x.m3u8',
    )
    assert job.id == 1
    assert job.status == JobStatus.QUEUED
    assert job.output_path.parent == tmp_path / '测试剧'
    assert job.output_path.name == '第01集.mp4'
    assert mgr.cancel(job.id) is True
    assert mgr.get(job.id).status == JobStatus.CANCELED
