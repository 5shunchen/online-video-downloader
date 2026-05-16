"""本地存储: 搜索历史、收藏记录。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SearchHistoryItem:
    """搜索历史条目。"""

    keyword: str
    timestamp: float
    count: int = 1  # 搜索次数


@dataclass
class FavoriteItem:
    """收藏条目。"""

    source_name: str
    vod_id: int
    name: str
    pic: str
    remarks: str
    year: str
    area: str
    type_name: str
    added_at: float


class LocalStorage:
    """本地 JSON 存储。"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._search_history: dict[str, SearchHistoryItem] = {}
        self._favorites: dict[tuple[str, int], FavoriteItem] = {}
        self._dark_mode: bool = False
        self._load()

    @property
    def _search_file(self) -> Path:
        return self.data_dir / ".ovd_search.json"

    @property
    def _favorites_file(self) -> Path:
        return self.data_dir / ".ovd_favorites.json"

    @property
    def _settings_file(self) -> Path:
        return self.data_dir / ".ovd_settings.json"

    def _load(self) -> None:
        """加载所有数据。"""
        try:
            if self._search_file.exists():
                with open(self._search_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self._search_history[item["keyword"]] = SearchHistoryItem(
                            keyword=item["keyword"],
                            timestamp=item["timestamp"],
                            count=item.get("count", 1),
                        )
        except Exception:
            pass

        try:
            if self._favorites_file.exists():
                with open(self._favorites_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        key = (item["source_name"], item["vod_id"])
                        self._favorites[key] = FavoriteItem(
                            source_name=item["source_name"],
                            vod_id=item["vod_id"],
                            name=item["name"],
                            pic=item.get("pic", ""),
                            remarks=item.get("remarks", ""),
                            year=item.get("year", ""),
                            area=item.get("area", ""),
                            type_name=item.get("type_name", ""),
                            added_at=item.get("added_at", 0),
                        )
        except Exception:
            pass

        try:
            if self._settings_file.exists():
                with open(self._settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._dark_mode = data.get("dark_mode", False)
        except Exception:
            pass

    def _save_search(self) -> None:
        """保存搜索历史。"""
        try:
            data = [
                {
                    "keyword": item.keyword,
                    "timestamp": item.timestamp,
                    "count": item.count,
                }
                for item in self._search_history.values()
            ]
            with open(self._search_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _save_favorites(self) -> None:
        """保存收藏记录。"""
        try:
            data = [
                {
                    "source_name": item.source_name,
                    "vod_id": item.vod_id,
                    "name": item.name,
                    "pic": item.pic,
                    "remarks": item.remarks,
                    "year": item.year,
                    "area": item.area,
                    "type_name": item.type_name,
                    "added_at": item.added_at,
                }
                for item in self._favorites.values()
            ]
            with open(self._favorites_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _save_settings(self) -> None:
        """保存设置。"""
        try:
            data = {
                "dark_mode": self._dark_mode,
            }
            with open(self._settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # --- 搜索历史 --------------------------------------------------------

    def add_search_history(self, keyword: str) -> None:
        """添加搜索历史。"""
        import time

        keyword = keyword.strip()
        if not keyword:
            return
        if keyword in self._search_history:
            item = self._search_history[keyword]
            item.timestamp = time.time()
            item.count += 1
        else:
            self._search_history[keyword] = SearchHistoryItem(
                keyword=keyword,
                timestamp=time.time(),
                count=1,
            )
        self._save_search()

    def get_search_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """获取搜索历史（按时间倒序）。"""
        items = sorted(
            self._search_history.values(),
            key=lambda x: x.timestamp,
            reverse=True,
        )
        return [
            {
                "keyword": item.keyword,
                "timestamp": item.timestamp,
                "count": item.count,
            }
            for item in items[:limit]
        ]

    def clear_search_history(self) -> None:
        """清空搜索历史。"""
        self._search_history.clear()
        self._save_search()

    def remove_search_history(self, keyword: str) -> None:
        """删除单个搜索历史。"""
        if keyword in self._search_history:
            del self._search_history[keyword]
            self._save_search()

    # --- 收藏 ------------------------------------------------------------

    def add_favorite(
        self,
        *,
        source_name: str,
        vod_id: int,
        name: str,
        pic: str = "",
        remarks: str = "",
        year: str = "",
        area: str = "",
        type_name: str = "",
    ) -> None:
        """添加收藏。"""
        import time

        key = (source_name, vod_id)
        if key in self._favorites:
            return  # 已收藏
        self._favorites[key] = FavoriteItem(
            source_name=source_name,
            vod_id=vod_id,
            name=name,
            pic=pic,
            remarks=remarks,
            year=year,
            area=area,
            type_name=type_name,
            added_at=time.time(),
        )
        self._save_favorites()

    def remove_favorite(self, source_name: str, vod_id: int) -> None:
        """取消收藏。"""
        key = (source_name, vod_id)
        if key in self._favorites:
            del self._favorites[key]
            self._save_favorites()

    def is_favorite(self, source_name: str, vod_id: int) -> bool:
        """检查是否已收藏。"""
        return (source_name, vod_id) in self._favorites

    def get_favorites(self) -> list[dict[str, Any]]:
        """获取所有收藏（按添加时间倒序）。"""
        items = sorted(
            self._favorites.values(),
            key=lambda x: x.added_at,
            reverse=True,
        )
        return [
            {
                "source_name": item.source_name,
                "vod_id": item.vod_id,
                "name": item.name,
                "pic": item.pic,
                "remarks": item.remarks,
                "year": item.year,
                "area": item.area,
                "type_name": item.type_name,
                "added_at": item.added_at,
            }
            for item in items
        ]

    # --- 暗黑模式 --------------------------------------------------------

    @property
    def dark_mode(self) -> bool:
        """是否暗黑模式。"""
        return self._dark_mode

    @dark_mode.setter
    def dark_mode(self, value: bool) -> None:
        """设置暗黑模式。"""
        self._dark_mode = value
        self._save_settings()
