# Digital Agronomist: recovered source

This is source code recovered from `DigitalAgronomist.exe` (dated 13 Oct 2026, 248 MB,
SHA-256 `554ad374d39fff6c33b50ff593e475a899045186fff95c52e1b31eb32b449029`).

| File | What it is |
|---|---|
| `DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py` | The whole application (1,701 lines). PySide6 GUI, Leaflet/OpenStreetMap map in QWebEngine, KML/manual parcel import, SQLite storage, platform-data and local-sensor tabs. |
| `runtime_hook_qtwebengine_onefile.py` | The custom PyInstaller runtime hook that was bundled in the exe. It points QtWebEngine to its process, resources, locales and plugins inside the one-file bundle. |
| `requirements.txt` | `PySide6==6.10.1`, the version found inside the exe. |
| `build_exe.bat` | Rebuilds a one-file windowed exe with PyInstaller and the runtime hook. Not yet tested on Windows. |
| `tools/pyc_tools.py` | The disassembly and verification helper used during recovery. |

## How faithful is it?

- **Bytecode-identical:** compiled with CPython 3.14, all 119 code objects in the main module have
  exactly the same raw bytecode, names, constants and signatures as the original `.pyc`. Both code
  objects in the runtime hook match too, including their line tables.
- **Comments are gone.** Comments are not stored in bytecode, so none survive. Docstrings and string
  literals survive (the SQL, the map HTML/JS and the Qt stylesheet).
- **Line numbers mostly match.** Lines 1–501 match the original. In the `MainWindow` class some
  statements are laid out differently, so the end of the file is 5 lines longer than the original
  (`main()` is at line 1689 instead of 1684). This doesn't change behaviour.
- **Odd-looking code is reproduced as written.** For example, `parse_kml_file` has an unused
  `parent_local_names = []`, and the third tab is titled "Local censors data". Both are in the
  original bytecode, so they were kept, not corrected.

## Running it

```
py -3.14 -m pip install -r requirements.txt
py -3.14 DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py
```
Use Python 3.14 to match the original. It should also run on 3.10+, because it uses no 3.14-only syntax.
The map needs internet access, because Leaflet and the OSM tiles load from unpkg.com and
tile.openstreetmap.org. The database `water_parcel_data.sqlite3` is created next to the script, or
next to the exe when the app is frozen.

Test run (Linux, offscreen Qt, PySide6 6.10.1):
- The module imports.
- KML parsing, manual coordinate parsing, area calculation and the SQLite schema all work.
- `MainWindow` opens with its three tabs: "Parcel map", "Platform data" and "Local censors data".

## How the exe was taken apart

1. **Extraction:** `pyinstxtractor-ng` (2026.07.03) found PyInstaller one-file, Python 3.14 and
   3,625 archive entries plus 260 PYZ modules. All the application code is in one entry point,
   `DigitalAgronomist_GOLD_FIXED_SQLite_EXE.pyc`. Everything else is the standard library,
   PySide6/shiboken6 and PyInstaller's own bootstrap.
2. **Decompilation:** no available decompiler handles Python 3.14 bytecode:
   - `pycdc` stops with "Bad MAGIC".
   - `uncompyle6` and `decompyle3` stop at 3.8.
   - PyLingual lists 3.14 support, but its models download from Hugging Face, which wasn't reachable here.

   So the source was rebuilt by hand from the CPython 3.14 `dis` output, one function at a time. Each
   function was recompiled and compared against the original until they matched (`tools/pyc_tools.py verify`).

To check the source against a `.pyc` yourself:
```
py -3.14 tools/pyc_tools.py verify <path>\DigitalAgronomist_GOLD_FIXED_SQLite_EXE.pyc DigitalAgronomist_GOLD_FIXED_SQLite_EXE.py --all
```
