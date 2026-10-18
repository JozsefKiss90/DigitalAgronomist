@echo off
REM Rebuild DigitalAgronomist.exe from the recovered source (Python 3.14, Windows).
REM Mirrors the original build: PyInstaller one-file, windowed, with the custom QtWebEngine runtime hook.
py -3.14 -m pip install -r requirements.txt -r requirements-build.txt
py -3.14 -m PyInstaller --noconfirm --onefile --windowed ^
  --name DigitalAgronomist ^
  --runtime-hook runtime_hook_qtwebengine_onefile.py ^
  DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py
