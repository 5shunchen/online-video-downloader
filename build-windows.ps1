# Windows 打包脚本
# 用法: 在 PowerShell 中运行: .\build-windows.ps1

Write-Host "=== 在线视频下载器 Windows 打包脚本 ===" -ForegroundColor Cyan

# 检查 Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    exit 1
}

# 创建虚拟环境
if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境..."
    python -m venv .venv
}

# 激活虚拟环境
Write-Host "激活虚拟环境..."
& ".venv\Scripts\Activate.ps1"

# 安装依赖
Write-Host "安装依赖..."
pip install -q -r requirements.txt
pip install -q pyinstaller

# 下载 ffmpeg
$ffmpegZip = "ffmpeg-release-essentials.zip"
$ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
if (-not (Test-Path $ffmpegZip)) {
    Write-Host "下载 ffmpeg..."
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip
}

# 解压 ffmpeg
Write-Host "解压 ffmpeg..."
Expand-Archive -Path $ffmpegZip -DestinationPath ".\ffmpeg-temp" -Force
$ffmpegExe = Get-ChildItem -Path ".\ffmpeg-temp" -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if ($ffmpegExe) {
    Copy-Item $ffmpegExe.FullName -Destination ".\ffmpeg.exe" -Force
    Write-Host "ffmpeg.exe 已准备好"
} else {
    Write-Host "警告: 未找到 ffmpeg.exe，需手动放入项目根目录" -ForegroundColor Yellow
}

# 打包
Write-Host "开始打包..."
$env:FFMPEG_PATH = ".\ffmpeg.exe"
pyinstaller --clean pyinstaller.spec

# 清理
Remove-Item -Recurse -Force ".\ffmpeg-temp" -ErrorAction SilentlyContinue

# 检查结果
$exePath = ".\dist\ovd.exe"
if (Test-Path $exePath) {
    $size = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
    Write-Host "打包成功!" -ForegroundColor Green
    Write-Host "输出文件: $exePath"
    Write-Host "文件大小: $size MB"
} else {
    Write-Host "打包失败!" -ForegroundColor Red
    exit 1
}
