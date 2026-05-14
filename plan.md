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
| **0.2.0** | MINOR | PyInstaller 一键打包 Windows 单文件 exe（内置 ffmpeg） |
| 0.3.0 | MINOR | 多采集源切换 / 失败重试 / 下载队列持久化 |
| 0.4.0 | MINOR | 字幕嵌入、画质选择、断点续传 |
| 0.5.0 | MINOR | 历史记录、收藏、暗黑模式 |
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

- [x] 站点调研 / 确定数据源
- [x] 编写 plan.md
- [x] 实现 0.1.0 代码
  - [x] MacCMS V10 客户端封装
  - [x] m3u8 并行下载引擎（8 并发 + AES 解密）
  - [x] 任务队列（3 并发下载）
  - [x] Web UI（Bootstrap 5 + 原生 JS）
  - [x] 搜索页面 + 结果展示 + 画质标签
  - [x] 分集列表 + 批量下载
  - [x] 下载任务列表（进度、速度、耗时）
  - [x] 下载记录删除（单条/批量/清空）
  - [x] 完成任务打开文件夹按钮
  - [x] 固定端口 8787
- [ ] 测试 + 报告
- [ ] README + 提交 + 发布 v0.1.0
