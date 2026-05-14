"""单元测试: MacCMS 解析。"""

from ovd.api.maccms import _parse_play, _summary_from_item
from ovd.config import Source


def test_parse_play_two_sources():
    flag = "gsyun$$$gsm3u8"
    url = (
        "第01集$https://x/play/aaa#第02集$https://x/play/bbb"
        "$$$"
        "第01集$https://x/play/aaa/index.m3u8#第02集$https://x/play/bbb/index.m3u8"
    )
    sources = _parse_play(flag, url)
    assert len(sources) == 2
    assert sources[0].flag == "gsyun"
    assert len(sources[0].episodes) == 2
    assert sources[0].episodes[0].name == "第01集"
    assert sources[1].is_m3u8 is True
    assert sources[0].is_m3u8 is False


def test_parse_play_robust_to_blanks():
    sources = _parse_play("a$$$b", "ep1$u1#$$$ep1$u2")
    assert len(sources) == 2
    # 跳过空 / 没有 $ 的项
    assert all(len(s.episodes) >= 1 for s in sources)


def test_summary_safe_with_missing_fields():
    src = Source(name="测试源", api="https://example/api")
    s = _summary_from_item(src, {"vod_id": "42", "vod_name": "片名"})
    assert s.vod_id == 42
    assert s.name == "片名"
    assert s.area == ""
    assert s.source_name == "测试源"
