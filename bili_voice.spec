# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import subprocess
import typing

from PyInstaller.utils.hooks import collect_data_files

if typing.TYPE_CHECKING:
    import os

    from PyInstaller.building.api import COLLECT, EXE, PYZ
    from PyInstaller.building.build_main import Analysis

    SPECPATH = ''

DISTPATH = os.path.join(SPECPATH, "dist")
WORKPATH = os.path.join(SPECPATH, "build")

# Executable name
NAME = "bili_voice"

# Python module search paths (pathex)
PYTHONPATH = [
    SPECPATH,
]

# ------------------------------------------------------------------
# Data files to include
# Each tuple: (source_path, destination_relative_path)
# ------------------------------------------------------------------
DATAS = []

if os.path.isdir(os.path.join(SPECPATH, "app_data")):
    DATAS.append((os.path.join(SPECPATH, "app_data"), "app_data"))

if os.path.isdir(os.path.join(SPECPATH, "frontend", "out")):
    DATAS.append((os.path.join(SPECPATH, "frontend", "out"), os.path.join("frontend", "out")))

if os.path.isfile(os.path.join(SPECPATH, "LICENSE")):
    DATAS.append((os.path.join(SPECPATH, "LICENSE"), "."))

if os.path.isfile(os.path.join(SPECPATH, "favicon.ico")):
    DATAS.append((os.path.join(SPECPATH, "favicon.ico"), "."))

# ------------------------------------------------------------------
# FFmpeg binaries
# ------------------------------------------------------------------
FFMPEG_BINARIES = []

def _collect_ffmpeg_binaries():
    """收集 FFmpeg 可执行文件"""
    binaries = []
    ffmpeg_paths = []
    
    # 检查常见的 FFmpeg 安装路径
    possible_paths = [
        # 系统 PATH 中的 ffmpeg
        shutil.which("ffmpeg.exe"),
        shutil.which("ffprobe.exe"),
        # conda 环境中的 ffmpeg
        os.path.join(sys.prefix, "Scripts", "ffmpeg.exe"),
        os.path.join(sys.prefix, "Scripts", "ffprobe.exe"),
        os.path.join(sys.prefix, "Library", "bin", "ffmpeg.exe"),
        os.path.join(sys.prefix, "Library", "bin", "ffprobe.exe"),
        # 项目目录中的 ffmpeg
        os.path.join(SPECPATH, "ffmpeg", "ffmpeg.exe"),
        os.path.join(SPECPATH, "ffmpeg", "ffprobe.exe"),
        os.path.join(SPECPATH, "bin", "ffmpeg.exe"),
        os.path.join(SPECPATH, "bin", "ffprobe.exe"),
    ]
    
    # 添加 conda 环境的路径
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        possible_paths.extend([
            os.path.join(conda_prefix, "Scripts", "ffmpeg.exe"),
            os.path.join(conda_prefix, "Scripts", "ffprobe.exe"),
            os.path.join(conda_prefix, "Library", "bin", "ffmpeg.exe"),
            os.path.join(conda_prefix, "Library", "bin", "ffprobe.exe"),
        ])
    
    # 收集找到的 FFmpeg 可执行文件
    for path in possible_paths:
        if path and os.path.isfile(path):
            exe_name = os.path.basename(path)
            binaries.append((path, "."))  # 放在 dist 根目录
            print(f"Found FFmpeg binary: {path} -> {exe_name}")
    
    return binaries

try:
    import shutil
    FFMPEG_BINARIES = _collect_ffmpeg_binaries()
    if FFMPEG_BINARIES:
        print(f"Collected {len(FFMPEG_BINARIES)} FFmpeg binaries")
    else:
        print("Warning: No FFmpeg binaries found. Audio playback may not work on non-Windows platforms.")
except Exception as e:
    print(f"Error collecting FFmpeg binaries: {e}")
    FFMPEG_BINARIES = []


# Third-party package data (gradio_client requires it sometimes)
DATAS += collect_data_files("gradio_client")

# ------------------------------------------------------------------
# Hidden imports (if PyInstaller misses dynamic imports)
# ------------------------------------------------------------------
HIDDENIMPORTS = [
    "bilibili_api.clients.HTTPXClient",
    "bilibili_api.clients.RequestsClient",
    "bilibili_api.clients.CurlCFFIClient",
    "bilibili_api.clients.AioHTTPClient",
    "protos.fans_club_pb2",
    "protos.interact_word_v2_pb2",
    "protos.online_rank_v3_pb2",
    "protos.user_dagw_pb2"
]

block_cipher = None

# Begin: bundle OpenSSL DLLs and certifi cacert
import glob

OPENSSL_BINARIES = []

def _collect_openssl_dlls():
    dlls = []
    seen = set()
    base_roots = [sys.base_prefix, sys.exec_prefix, sys.prefix, os.path.dirname(sys.executable)]
    base_dirs = list({d for root in base_roots for d in (
            root,
            os.path.join(root, "DLLs"),
            os.path.join(root, "Library", "bin"),  # conda/Anaconda OpenSSL DLLs
        )})
    # Also consider explicit CONDA_PREFIX
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        for d in (conda_prefix, os.path.join(conda_prefix, "DLLs"), os.path.join(conda_prefix, "Library", "bin")):
            if d not in base_dirs:
                base_dirs.append(d)
    patterns = []
    for d in base_dirs:
        for name in ("libcrypto-1_1", "libssl-1_1", "libcrypto-3", "libssl-3"):
            patterns.append(os.path.join(d, f"{name}*.dll"))
    for pat in patterns:
        for p in glob.glob(pat):
            rp = os.path.realpath(p)
            if os.path.isfile(rp) and rp.lower().endswith(".dll") and rp not in seen:
                seen.add(rp)
                # Place into dist root so _ssl.pyd can resolve them via PATH
                dlls.append((rp, "."))
    return dlls

try:
    OPENSSL_BINARIES = _collect_openssl_dlls()
except Exception:
    OPENSSL_BINARIES = []


# ------------------------------------------------------------------
# Analysis
# ------------------------------------------------------------------
a = Analysis(
    ["run.py"],  # Entry script
    pathex=PYTHONPATH,
    binaries=OPENSSL_BINARIES + FFMPEG_BINARIES,  # 合并 OpenSSL 和 FFmpeg 二进制文件
    datas=DATAS,
    hiddenimports=HIDDENIMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    module_collection_mode={
        # Collect 'gradio' as source if needed to avoid missing templates
        "gradio": "py",
    },
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # change to False to hide console if desired
    icon=os.path.join(SPECPATH, "favicon.ico"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=NAME,
)
