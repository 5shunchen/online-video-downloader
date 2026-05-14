# 在线视频下载器 (ovd)

面向 7080.wang 等影视站点用户的本地视频搜索与批量下载工具。

## 功能特性

- **🔍 搜索**: 关键词搜索影视资源，支持多个采集源
- **📋 分集列表**: 查看视频的所有集数，自动识别清晰度
- **⬇️ 单集下载**: 点击即下载，自动转封装为 MP4
- **🚀 批量下载**: 多选集数，排队并行下载
- **⚡ 极速下载**: 8 并发拉取 TS 分片 + 本地快速合并，**速度是 ffmpeg 直接拉流的 20 倍以上**
- **🔐 AES-128 解密**: 自动处理 HLS 加密流
- **🌐 Web UI**: 浏览器操作，无需命令行

## 安装

### Windows 用户（推荐）

直接下载 `ovd.exe`，双击即可使用，无需安装任何依赖。

下载地址: https://github.com/5shunchen/online-video-downloader/releases

### 开发者 / Linux / macOS 用户

```bash
# 安装依赖
pip install -r requirements.txt

# 或安装为包
pip install -e .
```

依赖 `ffmpeg`:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## 使用

```bash
# 启动 Web UI (默认 http://127.0.0.1:8787)
python -m ovd

# 指定端口和下载目录
python -m ovd --port 8888 --download-dir ./videos
```

Windows exe 用户直接双击运行即可，会自动打开浏览器。

## 命令行选项

```
--host 127.0.0.1   监听地址
--port 8787        监听端口
--download-dir     下载目录 (默认 ./downloads)
--no-browser       不自动打开浏览器
```

## 技术架构

- **后端**: Python + FastAPI + httpx + asyncio
- **下载引擎**: 8 并发拉取 TS 分片，AES-128 自动解密，二进制拼接后 ffmpeg 转封装
- **前端**: 原生 HTML + Bootstrap 5 + JavaScript (无构建链)
- **打包**: PyInstaller 单文件 exe（内置 ffmpeg）

## 版本历史

### v0.2.0 (规划中)
- 🪟 Windows 单文件 exe 发布
- ✅ 内置 ffmpeg
- ✅ 双击即用，自动打开浏览器

### v0.1.0 (2026-05-15)
- 🎉 首个版本发布
- ✅ 搜索功能
- ✅ 分集列表
- ✅ 单集/批量下载
- ✅ 下载任务队列
- ✅ Web UI
- ✅ 20x 极速下载引擎
