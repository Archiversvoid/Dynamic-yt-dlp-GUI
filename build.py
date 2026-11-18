"""Builds Dynamic.

    py build.py                     pictures, PyInstaller, completes dist\\Dynamic, makes the installer
    py build.py --installer-only    skip PyInstaller (reuse dist\\Dynamic); refresh the extras and the installer
    py build.py --zip-only          only make the update zip (dist\\Dynamic-<version>-update.zip) from the app already built
    py build.py --version 1.2.3     first write 1.2.3 into src\\core\\app_info.py (the GitHub workflow does this from the tag)
    py build.py --sign              also code-sign Dynamic.exe and the installer (see SIGNING below)

Needs: Python with PyInstaller + PySide6 installed, and Inno Setup 6.3+.

The icons:  icons\\icon 2.ico  is the thumbnail (Dynamic.exe in Explorer, the installer file, the shortcuts, the installer's
            picture); it is used exactly as it is.   icons\\icon.ico  is what the running app shows (taskbar, tray, window).

Why this is a .py and not a .bat: Windows SmartScreen warns about scripts that came out of a downloaded zip.
It does not do that for a Python script run through `py`.

RELEASING: change APP_VERSION in src\\core\\app_info.py, run this, then publish a GitHub release tagged v<version> with the\ntwo files it lists at the end. Installed copies see the release, download the small update package and replace only\nthe files that changed.\n\nSIGNING (optional): set DYNAMIC_SIGN_PFX (path to your code-signing certificate .pfx) and, if it has one,
DYNAMIC_SIGN_PASS, make sure signtool.exe (Windows SDK) is on PATH, and run with --sign.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist" / "Dynamic"
LARGE = (164, 314)         # the installer's side picture
SMALL = (55, 55)           # the installer's corner picture


def step(msg):
    print("\n=== %s ===" % msg, flush=True)


def run(cmd):
    print("> " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=ROOT, check=True)


# ---------------------------------------------------------------- the installer's pictures, from icons\icon 2.ico
def _qt_image(src):
    """The largest picture in the .ico."""
    from PySide6.QtGui import QImage, QImageReader
    reader = QImageReader(str(src))
    count = reader.imageCount()
    best = None
    for i in range(max(count, 1)):
        if count > 1:
            reader.jumpToImage(i)
        img = reader.read()
        if not img.isNull() and (best is None or img.width() > best.width()):
            best = img
    return best if best is not None else QImage(str(src))


def _render_qt(src, jobs, out):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    img = _qt_image(src)
    if img.isNull():
        return False
    c = img.pixelColor(0, 0)
    bg = QColor(c.red(), c.green(), c.blue()) if c.alpha() > 200 else QColor("#121212")
    for w, h, name, fill in jobs:
        canvas = QImage(w, h, QImage.Format.Format_RGB32)
        canvas.fill(bg)
        side = int(min(w, h) * fill)
        scaled = img.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p = QPainter(canvas)
        p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        p.end()
        canvas.save(str(out / name), "BMP")
    return True


def _render_pil(src, jobs, out):
    from PIL import Image
    img = Image.open(src).convert("RGBA")
    corner = img.getpixel((0, 0))
    bg = corner[:3] if corner[3] > 200 else (18, 18, 18)
    for w, h, name, fill in jobs:
        canvas = Image.new("RGB", (w, h), bg)
        side = int(min(w, h) * fill)
        scaled = img.copy()
        scaled.thumbnail((side, side), Image.LANCZOS)
        canvas.paste(scaled, ((w - scaled.width) // 2, (h - scaled.height) // 2), scaled)
        canvas.save(out / name, "BMP")
    return True


def make_installer_art():
    """installer_art\\wizard_large.bmp and wizard_small.bmp (Inno Setup wants bitmaps)."""
    src = ROOT / "icons" / "icon 2.ico"
    if not src.exists():
        print("icons\\icon 2.ico not found - the installer will use Inno's default pictures")
        return
    out = ROOT / "installer_art"
    out.mkdir(exist_ok=True)
    jobs = [(LARGE[0], LARGE[1], "wizard_large.bmp", 0.86), (SMALL[0], SMALL[1], "wizard_small.bmp", 0.92)]
    for render in (_render_qt, _render_pil):
        try:
            if render(src, jobs, out):
                print("installer pictures written to installer_art\\ (from icons\\icon 2.ico)")
                return
        except Exception as e:
            print("  %s failed: %s" % (render.__name__, e))
    print("COULD NOT make the installer pictures - the installer will use Inno's default pictures")


# ---------------------------------------------------------------- the rest
def complete_dist():
    """Put the read-only app files next to Dynamic.exe, as the installer does, so dist\\Dynamic runs on its own.
    (Dynamic.spec does the same, so this is only a safety net.)"""
    if not DIST.exists():
        sys.exit("dist\\Dynamic not found - build the app first:  py build.py")
    for name in ("icons", "assets"):
        if (ROOT / name).is_dir():
            shutil.copytree(ROOT / name, DIST / name, dirs_exist_ok=True)
    for pattern in ("TERMS*", "CHANGELOG*"):
        for f in ROOT.glob(pattern):
            if f.is_file():
                shutil.copy2(f, DIST / f.name)
    (DIST / "bin").mkdir(exist_ok=True)
    print("copied icons, assets, Terms and Changelog into dist\\Dynamic")


def app_version():
    """The release version: APP_VERSION in src\\core\\app_info.py (the one place to change)."""
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "src" / "core" / "app_info.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "0.0.0"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _package_files():
    """The app files an update may replace: everything in dist\\Dynamic except bin\\ and our own bookkeeping."""
    for p in sorted(DIST.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(DIST).as_posix()
        if rel.split("/")[0] in ("bin", "_update") or rel == "manifest.json" or ".dynold" in rel:
            continue
        yield rel, p


def make_update_package(version):
    """dist\\Dynamic\\manifest.json (the installer ships it too) and dist\\Dynamic-<version>-update.zip."""
    files = {rel: _sha256(p) for rel, p in _package_files()}
    manifest = json.dumps({"version": version, "files": files}, indent=1)
    (DIST / "manifest.json").write_text(manifest, encoding="utf-8")
    out = DIST.parent                                # the dist folder, next to the Dynamic folder (never inside it)
    out.mkdir(parents=True, exist_ok=True)
    package = out / ("Dynamic-%s-update.zip" % version)
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("manifest.json", manifest)
        for rel, p in _package_files():
            z.write(p, rel)
    print("update package: %s (%d files, %.0f MB)" % (package.name, len(files), package.stat().st_size / 1048576))
    return package


def sign(path):
    pfx, tool = os.environ.get("DYNAMIC_SIGN_PFX"), shutil.which("signtool")
    if not (pfx and tool):
        print("signing skipped (DYNAMIC_SIGN_PFX not set or signtool.exe not on PATH): %s" % Path(path).name)
        return
    pw = os.environ.get("DYNAMIC_SIGN_PASS")
    run([tool, "sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256", "/f", pfx] + (["/p", pw] if pw else []) + [path])


def write_checksum(path):
    """SHA-256 next to the installer: publish it with the download so people can verify the file."""
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".sha256.txt").write_text("%s  %s\n" % (digest, path.name))
    print("SHA-256: %s" % digest)


def find_iscc():
    cands = [shutil.which("ISCC")]
    for var in ("ProgramFiles(x86)", "ProgramFiles"):
        cands.append(os.path.join(os.environ.get(var, ""), "Inno Setup 6", "ISCC.exe"))
    cands.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"))
    return next((c for c in cands if c and os.path.isfile(c)), None)


def _arg_value(argv, flag):
    if flag in argv:
        i = argv.index(flag)
        return argv[i + 1] if i + 1 < len(argv) else ""
    return None


def set_version(version):
    """Stamp APP_VERSION in src/core/app_info.py - the one place the app takes its version from. CI passes the git tag's
    version here, so the installed app, the installer and the release can never disagree (a mismatch would make the app
    offer an update to itself forever)."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version or ""):
        sys.exit("--version needs three numbers like 1.2.3 (got %r). Tag releases as v1.2.3." % (version,))
    path = ROOT / "src" / "core" / "app_info.py"
    text = path.read_bytes().decode("utf-8")                     # bytes: keeps the file's line endings as they are
    new, n = re.subn(r'(APP_VERSION\s*=\s*")[^"]*(")', lambda m: m.group(1) + version + m.group(2), text)
    if n != 1:
        sys.exit("could not find APP_VERSION in src/core/app_info.py")
    path.write_bytes(new.encode("utf-8"))


def main(argv):
    installer_only, do_sign, zip_only = "--installer-only" in argv, "--sign" in argv, "--zip-only" in argv
    print("build.py: makes the update zip (in the dist folder) and the installer (in the Output folder)", flush=True)
    wanted = _arg_value(argv, "--version")
    if wanted is not None:
        set_version(wanted)
        print("version set to %s (src/core/app_info.py)" % wanted, flush=True)
    if not zip_only:
        step("1/4  Installer pictures (from icon 2.ico)")
        make_installer_art()
        if not installer_only:
            step("2/4  PyInstaller")
            run([sys.executable, "-m", "PyInstaller", "Dynamic.spec", "--noconfirm", "--clean"])
    step("Update zip" if zip_only else "3/4  Extras and update zip")
    complete_dist()
    if do_sign:
        sign(str(DIST / "Dynamic.exe"))
    version = app_version()
    package = make_update_package(version)           # after signing: the manifest holds the hash of the signed exe
    write_checksum(package)
    setup = None
    if not zip_only:
        step("4/4  Inno Setup")
        iscc = find_iscc()
        if not iscc:
            print("Inno Setup (ISCC.exe) not found - the update zip is ready, the installer was NOT built.")
            print("Install Inno Setup 6.3+ (or add ISCC.exe to PATH), then run:  py build.py --installer-only")
        else:
            run([iscc, "/DMyAppVersion=" + version, "Dynamic.iss"])
            setups = sorted((ROOT / "Output").glob("Dynamic-Setup-*.exe"), key=lambda f: f.stat().st_mtime)
            if setups:
                setup = setups[-1]
                if do_sign:
                    sign(str(setup))
                write_checksum(setup)
    print("\n" + "=" * 70)
    print("DONE - release %s. Attach these to a GitHub release tagged v%s:" % (version, version))
    print("  update zip : %s   <- what the in-app updater downloads" % package)
    if setup is not None:
        print("  installer  : %s   <- for new installs" % setup)
    print("=" * 70)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except subprocess.CalledProcessError as e:
        sys.exit("\nBUILD FAILED (exit code %s) - see the messages above." % e.returncode)
