from __future__ import annotations

import os
import sys
from pathlib import Path


def first_existing(paths):
    for path in paths:
        if path and path.exists():
            return path
    return None


bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

process_path = first_existing([
    bundle_root / "PySide6" / "Qt" / "libexec" / "QtWebEngineProcess.exe",
    bundle_root / "PySide6" / "Qt" / "bin" / "QtWebEngineProcess.exe",
    bundle_root / "QtWebEngineProcess.exe",
    bundle_root / "PySide6" / "QtWebEngineProcess.exe",
])

resources_path = first_existing([
    bundle_root / "PySide6" / "Qt" / "resources",
    bundle_root / "resources",
])

translations_path = first_existing([
    bundle_root / "PySide6" / "Qt" / "translations" / "qtwebengine_locales",
    bundle_root / "translations" / "qtwebengine_locales",
    bundle_root / "qtwebengine_locales",
])

plugins_path = first_existing([
    bundle_root / "PySide6" / "Qt" / "plugins",
    bundle_root / "plugins",
])

if process_path:
    os.environ["QTWEBENGINEPROCESS_PATH"] = str(process_path)

if resources_path:
    os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(resources_path)

if translations_path:
    os.environ["QTWEBENGINE_LOCALES_PATH"] = str(translations_path)

if plugins_path:
    os.environ["QT_PLUGIN_PATH"] = str(plugins_path)

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-sandbox")
