# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files

# 收集所有静态文件
datas = collect_data_files('ovd')
datas += [
    ('ovd/static/index.html', 'ovd/static'),
]

# 添加 ffmpeg (Windows 版本会在打包时下载)
ffmpeg_path = os.environ.get('FFMPEG_PATH', '')
if ffmpeg_path and os.path.exists(ffmpeg_path):
    datas.append((ffmpeg_path, '.'))

a = Analysis(
    ['ovd/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'fastapi',
        'fastapi.responses',
        'httpx',
        'cryptography',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
        'pytest',
        'matplotlib',
        'numpy',
        'pandas',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ovd',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
