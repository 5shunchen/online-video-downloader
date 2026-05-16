# 在线视频下载器 (ovd)

面向 7080.wang 等影视站点用户的本地视频搜索与批量下载工具。

## 功能特性

### 核心功能
- **🔍 搜索**: 关键词搜索影视资源，支持 5 个采集源（光速/量子/暴风云/非凡/金鹰）
- **📋 分集列表**: 查看视频的所有集数，自动识别清晰度（1080P/720P/高清）
- **⬇️ 单集下载**: 点击即下载，自动转封装为 MP4
- **🚀 批量下载**: 多选集数，排队并行下载（默认 3 个并发）
- **⚡ 极速下载**: 8 并发拉取 TS 分片 + 本地内存快速合并，**速度是 ffmpeg 直接拉流的 20 倍以上**
- **🔐 AES-128 解密**: 自动处理 HLS 加密流
- **🌐 Web UI**: 浏览器操作，无需命令行

### 高级功能
- **📤 浏览器下载**: 服务器下载完成后，支持一键下载到本地，自动删除服务器文件
- **⭐ 收藏功能**: 喜欢的剧集一键收藏，下次直接观看
- **📝 搜索历史**: 自动记录搜索关键词，支持删除和清空
- **🌓 暗黑模式**: 支持明暗主题切换
- **🔧 数据源管理**: 设置页面支持添加/编辑/删除自定义采集源
- **📂 打开目录**: 已下载文件一键打开所在文件夹

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

## Linux 部署指南

### 系统要求

- Linux x86_64 (Ubuntu 20.04+, Debian 11+, CentOS 8+, etc.)
- Python 3.10+
- ffmpeg 4.4+

### 1. 安装系统依赖

#### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg git
```

#### CentOS / RHEL / Rocky Linux
```bash
sudo dnf install -y python3 python3-pip ffmpeg git
# 若 ffmpeg 找不到，先启用 EPEL 和 RPM Fusion 源
sudo dnf install -y epel-release
sudo dnf install -y --nogpgcheck https://download1.rpmfusion.org/free/el/rpmfusion-free-release-9.noarch.rpm
sudo dnf install -y ffmpeg
```

### 2. 获取源码并安装

```bash
# 克隆仓库
git clone https://github.com/5shunchen/online-video-downloader.git
cd online-video-downloader

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 运行方式

#### 方式一：直接运行（测试用）
```bash
# 激活虚拟环境
source venv/bin/activate

# 启动服务（监听所有网卡，用于远程访问）
python -m ovd --host 0.0.0.0 --port 8787
```

访问 `http://服务器IP:8787` 即可使用。

#### 方式二：后台运行（nohup）
```bash
source venv/bin/activate
nohup python -m ovd --host 0.0.0.0 --port 8787 --no-browser > ovd.log 2>&1 &

# 查看日志
tail -f ovd.log

# 停止服务
pkill -f "python -m ovd"
```

#### 方式三：Systemd 服务（生产环境推荐）

创建服务文件 `/etc/systemd/system/ovd.service`：
```ini
[Unit]
Description=Online Video Downloader
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/online-video-downloader
Environment="PATH=/opt/online-video-downloader/venv/bin"
ExecStart=/opt/online-video-downloader/venv/bin/python -m ovd --host 0.0.0.0 --port 8787 --no-browser
Restart=always
RestartSec=10
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
```

启动并启用服务：
```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start ovd

# 设置开机自启
sudo systemctl enable ovd

# 查看状态
sudo systemctl status ovd

# 查看日志
sudo journalctl -u ovd -f
```

### 4. 防火墙配置

#### Ubuntu / Debian (ufw)
```bash
sudo ufw allow 8787/tcp
sudo ufw reload
```

#### CentOS / RHEL (firewalld)
```bash
sudo firewall-cmd --permanent --add-port=8787/tcp
sudo firewall-cmd --reload
```

### 5. Nginx 反向代理（可选）

用于配置域名、HTTPS、负载均衡等场景：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 允许上传的文件大小（按需调整）
    client_max_body_size 10G;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持（若使用）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时设置
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

配置 HTTPS（使用 Let's Encrypt）：
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 6. Docker 部署

创建 `Dockerfile`：
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 暴露端口
EXPOSE 8787

# 启动命令
CMD ["python", "-m", "ovd", "--host", "0.0.0.0", "--port", "8787", "--no-browser"]
```

构建并运行：
```bash
docker build -t ovd .
docker run -d -p 8787:8787 -v /path/to/downloads:/app/downloads --name ovd ovd
```

### 7. 远程使用流程

1. 确保服务已启动并监听 `0.0.0.0:8787`
2. 本地浏览器访问：`http://服务器IP:8787`（或域名）
3. 搜索并下载视频到服务器
4. 服务器下载完成后，点击任务右侧的「⬇️ 下载」按钮
5. 文件自动下载到本地，同时服务器端文件自动删除，节省磁盘空间

### 8. 常见问题排查

#### 问题：无法访问 Web UI
```bash
# 检查端口是否在监听
netstat -tlnp | grep 8787

# 检查防火墙状态
sudo ufw status
# 或
sudo firewall-cmd --list-ports
```

#### 问题：下载失败，提示 ffmpeg 未找到
```bash
# 检查 ffmpeg 是否安装
which ffmpeg
ffmpeg -version

# 若不存在，重新安装
sudo apt install -y ffmpeg
```

#### 问题：提示权限不足无法写入文件
```bash
# 检查下载目录权限
ls -la /path/to/downloads

# 修正权限
sudo chown -R www-data:www-data /path/to/downloads
sudo chmod -R 755 /path/to/downloads
```

#### 问题：Systemd 服务启动失败
```bash
# 查看详细错误日志
sudo journalctl -u ovd -n 50 --no-pager

# 检查 WorkingDirectory 和 ExecStart 路径是否正确
```

## 远程服务器部署

将程序部署在远程服务器上使用：

1. 在服务器上启动程序：`python -m ovd --host 0.0.0.0`
2. 浏览器访问 `http://服务器IP:8787`
3. 服务器下载完成后，点击任务右侧的「⬇️ 下载」按钮
4. 文件自动下载到本地，同时服务器端文件自动删除，节省磁盘空间

## 技术架构

- **后端**: Python + FastAPI + httpx + asyncio
- **下载引擎**: 8 并发拉取 TS 分片，AES-128 自动解密，内存二进制拼接后 ffmpeg 转封装
- **前端**: 原生 HTML + Bootstrap 5 + JavaScript (无构建链)
- **打包**: PyInstaller 单文件 exe（内置 ffmpeg）
- **配置持久化**: JSON 文件存储自定义数据源、搜索历史、收藏列表

## 版本历史

### v0.6.0 (2026-05-16)
- 🔧 **数据源管理后台** - 支持添加/编辑/删除自定义采集源
- 📤 **浏览器下载功能** - 一键下载到本地，自动删除服务器文件
- 🏷️ **导出状态标记** - 已导出的任务显示蓝色徽章
- 📁 **默认源扩展至 5 个** - 光速/量子/暴风云/非凡/金鹰资源

### v0.5.0 (2026-05-16)
- ⭐ **收藏功能** - 一键收藏喜欢的剧集
- 📝 **搜索历史** - 自动记录，支持删除和清空
- 🌓 **暗黑模式** - 支持明暗主题切换
- 🎨 **UI 优化** - 更好的视觉效果和交互体验

### v0.4.0 (2026-05-16)
- 🎯 **画质选择** - 自动识别 1080P/720P/高清并标注
- 🔄 **断点续传** - 任务持久化，重启程序后恢复下载队列
- 📊 **下载统计** - 实时显示下载速度、文件大小、耗时

### v0.3.0 (2026-05-15)
- ⚡ **性能优化** - 并发调优，内存合并，速度提升 30%
- 📈 **速度平滑计算** - 更准确的实时下载速度显示
- 🗑️ **批量删除** - 支持多选删除下载记录

### v0.2.0 (2026-05-15)
- 🪟 **Windows 单文件 exe 发布** - 无需安装，双击即用
- ✅ 内置 ffmpeg，自动检测路径
- ✅ 启动后自动打开浏览器
- ✅ 新增"暴风云资源"数据源
- ✅ 数据源下拉选择功能

### v0.1.0 (2026-05-15)
- 🎉 首个版本发布
- ✅ 搜索功能（多数据源）
- ✅ 分集列表 + 批量下载
- ✅ 下载任务队列（进度、速度、耗时）
- ✅ Web UI（Bootstrap 5）
- ✅ 20x 极速下载引擎（8 并发分片）
- ✅ AES-128 自动解密
