# Build with:  pyinstaller -y MarineOps.spec

import os
from pathlib import Path

import certifi
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

project_dir = Path.cwd()  # robust when __file__ isn't set

# Exclude these directories anywhere under the project tree
EXCLUDE_DIRS = {".venv", "__pycache__", "build", "dist", ".git"}

datas = []

def add_tree_excluding(root_name: str):
    root = project_dir / root_name
    if not root.exists():
        return
    for path in root.rglob("*"):
        # Skip directories we don't want to include
        parts = set(path.parts)
        if EXCLUDE_DIRS & parts:
            continue
        if path.is_file():
            # Destination directory inside the bundle mirrors project layout
            rel_parent = path.parent.relative_to(project_dir)
            datas.append((str(path), str(rel_parent)))

# Include these directories wholesale (recursively), but skip EXCLUDE_DIRS
for d in ["frontend_build", "Loading_Computer", "static", "staticfiles"]:
    add_tree_excluding(d)

# Optional single files (no .env)
for fname in ["manage.py", "manage"]:
    p = project_dir / fname
    if p.exists():
        datas.append((str(p), "."))

custom_files = ["setup_ipsum.txt"]
for fname in custom_files:
    p = project_dir / fname
    if p.exists():
        datas.append((str(p), "."))

# Ensure certifi's CA bundle is included to keep requests happy
datas += collect_data_files("certifi")
cacert = Path(certifi.where())
datas.append((str(cacert), "certifi"))
datas += collect_data_files("setuptools._vendor.jaraco.text")

# Make sure Django & pywebview get fully collected
hiddenimports = collect_submodules("django") + collect_submodules("webview")

# Exclude modules not needed on Windows
excludes = ["django.contrib.postgres", "webview.platforms.android"]

a = Analysis(
    scripts=[str(project_dir / "desktop_app.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

icon_path = project_dir / "frontend_build" / "favicon.ico"
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="Marine-Ops",
    console=False,  # windowed
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Marine-Ops",
)
