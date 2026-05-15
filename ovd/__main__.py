"""命令行入口: `python -m ovd` / `ovd`."""

from __future__ import annotations

import argparse
import os
import webbrowser
from threading import Timer

import uvicorn

# PyInstaller 兼容：优先尝试绝对导入
try:
    from ovd import __version__
    from ovd.config import Settings
except ImportError:
    from . import __version__
    from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="ovd", description="在线视频搜索下载器")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="监听端口 (默认 8787)")
    parser.add_argument(
        "--download-dir",
        default=None,
        help="下载目录 (默认 ./downloads, 可用环境变量 OVD_DOWNLOAD_DIR 覆盖)",
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="启动后不自动打开浏览器"
    )
    parser.add_argument("--version", action="version", version=f"ovd {__version__}")
    args = parser.parse_args()

    if args.download_dir:
        os.environ["OVD_DOWNLOAD_DIR"] = args.download_dir

    # 触发一次配置加载, 让用户尽早看到下载目录。
    settings = Settings.load()
    print(f"[ovd {__version__}] 下载目录: {settings.download_dir}")
    print(f"[ovd {__version__}] 访问 http://127.0.0.1:{args.port}")

    if not args.no_browser:
        # 浏览器总是用 127.0.0.1 访问，即使监听的是 0.0.0.0
        Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()

    uvicorn.run("ovd.web.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
