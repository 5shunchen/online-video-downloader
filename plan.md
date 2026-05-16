# 项目规划 plan.md

> 受众: <https://7080.wang> 用户。提供搜索 + 单集/批量下载在线视频的本地工具。
> 形态: Python + FastAPI + 本地 Web UI, 后台用 ffmpeg 合并 m3u8 → mp4。

## 站点调研结论

- 7080.wang 自身只是一个 iframe 壳页面, 把搜索词转给上游解析站 (邦宁/M1907/xymov/wkvip)。
- 上游解析站 JS 全部 `jsjiami.v7` 混淆, 没有公开搜索 API。
- 决定改用 **公共 MacCMS V10 影视采集接口** 作为数据源 (与 7080.wang 同类资源, 但接口干净稳定)。
  - 主源: `https://api.guangsuapi.com/api.php/provide/vod`
  - 备源: `https://cj.lziapi.com/api.php/provide/vod`
- 验证: 关键字 `遮天` 命中 22 条, `vod_play_from` 含 `gsm3u8` 直链通道, 162 集 1080p m3u8 可直接拉流。

## 总体路线图

| 版本 | 类型 | 目标 |
| --- | --- | --- |
| **0.1.0** | MINOR | 首发 MVP: 搜索 + 单集下载 + 批量下载 + 本地 Web UI ✅ |
| **0.2.0** | MINOR | PyInstaller 一键打包 Windows 单文件 exe（内置 ffmpeg）✅ |
| **0.3.0** | MINOR | 性能优化：并发调优 + 内存合并 + 速度平滑计算 ✅ |
| **0.4.0** | MINOR | 画质选择、断点续传 ✅ |
| **0.5.0** | MINOR | 搜索历史、剧集收藏、暗黑模式 ✅ |
| **0.6.0** | MINOR | 系统管理后台：搜索源 CRUD（增删改查）✅ |
| 1.0.0 | MAJOR | 稳定版, 文档完善, 发布到 GitHub Releases |

后续每个版本前先按 `prompt.md` 规则检查 `gh issue list`, 有未关闭 issue 优先发 PATCH。

## 0.1.0 范围 (本次任务)

### 功能需求

1. **搜索**: 用户输入关键字, 调用 MacCMS API 返回剧集卡片列表 (封面、名称、备注、年份、地区、最新集数)。
2. **详情**: 点开剧集后展示分集列表 (源 + 集名 + m3u8)。
3. **单集下载**: 点击集 → 后台 ffmpeg 拉取 m3u8 → 保存为 `{剧名}/{集名}.mp4`。
4. **批量下载**: 全选 / 选中区间 / 选中集合, 排队顺序下载。
5. **下载状态**: Web UI 实时显示进度 (排队/下载中/完成/失败)。
6. **下载目录**: 默认 `./downloads`, 可配置。

### 技术方案

- **后端**: Python 3.10+, FastAPI, httpx, ffmpeg (子进程)。
- **前端**: 单页 HTML + Bootstrap 5 + 原生 JS (轮询 `/api/jobs` 拿状态), 不引入构建链。
- **下载器**: ffmpeg 一行命令: `ffmpeg -i URL -c copy -bsf:a aac_adtstoasc out.mp4`。
- **任务调度**: 单进程 + `asyncio.Queue` + 1~N 并发 worker, 内存态即可 (持久化留 0.2.0)。
- **配置**: `config.toml` 或环境变量, 含数据源列表、下载目录、并发数。

### 目录结构

```
online-video-downloader/
├── ovd/                     # Python 包
│   ├── __init__.py          # __version__ = "0.1.0"
│   ├── api/                 # MacCMS 客户端
│   ├── downloader/          # ffmpeg 任务、队列
│   ├── web/                 # FastAPI 路由
│   └── static/              # 前端 HTML/JS
├── tests/                   # pytest 测试
├── docs/
│   ├── architecture.md      # 架构与数据流
│   ├── api.md               # 接口说明
│   └── test-report-0.1.0.md # 测试报告
├── pyproject.toml
├── requirements.txt
├── README.md
├── plan.md
├── CLAUDE.md
├── prompt.md
└── .gitignore
```

### 验收

- 用 `遮天` 关键字搜出至少 1 条结果。
- 选中前 2 集成功下载为 mp4, ffprobe 可读, 时长大于 0。
- 批量下载 3 集顺序完成, 状态显示正确。
- 测试报告归档到 `docs/test-report-0.1.0.md`。

## 进展

- [x] v0.1.0 MVP: 搜索 + 单集下载 + 批量下载 + 本地 Web UI
- [x] v0.2.0 PyInstaller 一键打包 Windows 单文件 exe（内置 ffmpeg）
- [x] v0.3.0 性能优化：并发调优 + 内存合并 + 速度平滑计算
- [x] v0.4.0 画质选择、断点续传
- [x] v0.5.0 搜索历史、剧集收藏、暗黑模式
- [x] v0.6.0 系统管理后台：搜索源 CRUD（增删改查）
  - [x] 后端 API：GET/POST/PUT/DELETE /api/sources
  - [x] 配置持久化：JSON 存储在下载目录
  - [x] 前端 UI：设置页面 + 模态框编辑
  - [x] 校验：名称冲突检测、至少保留一个源
- [ ] 1.0.0 稳定版，文档完善，发布到 GitHub Releases
