import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

app_name = "YouTube Player and Downloader"
source_dir = os.path.abspath("source")
entry_point = os.path.join(source_dir, "youtube_player_and_downloader.py")

all_datas = []
all_binaries = []

for root, dirs, files in os.walk(source_dir):
    for file in files:
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(root, source_dir)
        dest_dir = "." if rel_path == "." else rel_path
        
        if file.lower().endswith((".dll", ".exe", ".so", ".pyd", ".dylib")):
            all_binaries.append((full_path, dest_dir))
        else:
            all_datas.append((full_path, dest_dir))

a = Analysis(
    [entry_point],
    pathex=[source_dir],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory="",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)