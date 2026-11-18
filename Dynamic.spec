# -*- mode: python ; coding: utf-8 -*-
# Dynamic - PyInstaller spec. ONE-FOLDER build: nothing is packed into a single exe.
#
#     py build.py                    (runs this, then makes the installer)
#     py -m PyInstaller Dynamic.spec --noconfirm --clean       (just this step)
#
# Output: dist\Dynamic\Dynamic.exe plus an _internal folder holding the libraries. The installer (Dynamic.iss)
# adds the read-only app files next to it (icons, Terms/Changelog). Nothing user-specific is built in.
#
# What is deliberately NOT in the build (this is where the old 261 MB went):
#   * PyQt6 / PyQt5     the app uses PySide6 only. Two Qt bindings in one build make PyInstaller abort - that was the
#                       "problem" when PyQt6 was added to the old spec. (Only the legacy src/core/Fetcher.py imported it.)
#   * Qt's FFmpeg backend (QtMultimedia's video engine, ~75 MB of avcodec/avformat/... DLLs). The preview player uses
#                       Windows' built-in Media Foundation backend instead (launcher.py selects it).
#   * Every Qt module the app doesn't import (WebEngine, Qml, Quick, 3D, Charts, PDF, ...): the old spec used
#                       collect_all('PySide6'), which copies ALL of Qt.
#   * yt-dlp and ffmpeg they are separate programs in bin\ (yt-dlp.exe, ffmpeg.exe) that the app starts when needed.
#                       That is also why curl_cffi is not bundled: yt-dlp.exe carries everything it needs itself.
#
# Want broader preview-codec support (VP9/AV1) at the cost of ~75 MB? Set USE_QT_FFMPEG_BACKEND = True.
from pathlib import Path

USE_QT_FFMPEG_BACKEND = False

ROOT = Path(SPECPATH)


def project_modules():
    """Every module under src/, so modules that are only imported dynamically are not missed."""
    mods = ["src", "main", "theme", "setup_wizard"]
    for p in sorted((ROOT / "src").rglob("*.py")):
        m = ".".join(p.relative_to(ROOT).with_suffix("").parts)
        if m.endswith(".__init__"):
            m = m[:-9]
        if m.endswith(".__main__") or m.endswith("Fetcher"):      # Fetcher imports PyQt6 - never bundle it
            continue
        if m not in mods:
            mods.append(m)
    return mods


EXCLUDES = [
    "PyQt5", "PyQt6", "PySide2", "tkinter", "yt_dlp", "matplotlib", "numpy", "scipy", "pandas", "IPython", "pytest", "setuptools", "pip", "wheel",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuickWidgets", "PySide6.QtQuick3D", "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtHttpServer", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtConcurrent", "PySide6.QtPrintSupport", "PySide6.QtSpatialAudio",
]

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=project_modules(),
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

# Trim what PyInstaller's Qt hooks still pull in
_DROP = ["opengl32sw"]                                                       # software OpenGL (~20 MB) - not needed
if not USE_QT_FFMPEG_BACKEND:
    _DROP += ["avcodec", "avformat", "avutil", "swresample", "swscale", "avdevice", "avfilter", "postproc", "ffmpegmediaplugin"]
a.binaries = [b for b in a.binaries if not Path(b[0]).name.lower().startswith(tuple(_DROP))]
a.datas = [d for d in a.datas if not d[0].lower().endswith(".qm")]            # Qt's own translation files

pyz = PYZ(a.pure)

_icon = ROOT / "icons" / "icon 2.ico"                     # the thumbnail Explorer shows for Dynamic.exe
if not _icon.exists():
    _icon = ROOT / "icons" / "icon.ico"
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,           # one-folder build
    name="Dynamic",
    debug=False,
    strip=False,
    upx=False,                       # UPX slows startup and upsets antivirus
    console=False,
    icon=str(_icon) if _icon.exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Dynamic")

# >>> app files next to the exe
# Put the read-only app files next to Dynamic.exe (the installer does the same), so dist\Dynamic runs on its own
# however this spec was started - the icons, the font, Terms and Changelog, and an empty bin\ folder.
import shutil
_dist = Path(DISTPATH) / "Dynamic"
for _name in ("icons", "assets"):
    if (ROOT / _name).is_dir():
        shutil.copytree(ROOT / _name, _dist / _name, dirs_exist_ok=True)
for _pattern in ("TERMS*", "CHANGELOG*"):
    for _f in ROOT.glob(_pattern):
        if _f.is_file():
            shutil.copy2(_f, _dist / _f.name)
(_dist / "bin").mkdir(exist_ok=True)
# <<< app files next to the exe
