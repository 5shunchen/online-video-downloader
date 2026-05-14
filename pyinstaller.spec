# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置

import os

block_cipher = None

# 数据源
datas = [
    ('ovd/static/index.html', 'ovd/static'),
]

# 内置 ffmpeg
ffmpeg_path = os.environ.get('FFMPEG_PATH', '')
if ffmpeg_path and os.path.exists(ffmpeg_path):
    datas.append((ffmpeg_path, '.'))

a = Analysis(
    ['ovd/__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.off',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.responses',
        'httpx',
        'cryptography',
        'ovd',
        'ovd.config',
        'ovd.api',
        'ovd.api.maccms',
        'ovd.downloader',
        'ovd.downloader.jobs',
        'ovd.web',
        'ovd.web.app',
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
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
