"""Dynamic's own updates: look for a new GitHub release, download its update package, replace only what changed.

Built so that nothing here looks like malware to an antivirus (the same idea as the yt-dlp update):
  * no helper .exe, no .bat/.ps1 script, no administrator rights, and nothing that was downloaded is ever run
  * the app replaces its own files from the inside; a file that is in use (Windows refuses to overwrite a running
    exe/DLL but allows renaming it) is renamed to *.dynold first, and those leftovers are deleted on the next start
  * only files whose SHA-256 differs are touched, and all of them are extracted and verified BEFORE the first one is replaced
  * if anything fails the update is rolled back; bin\\ (yt-dlp, ffmpeg) and your data are never touched

A release carries two files for people: Dynamic-Setup-x.y.z.exe (new installs) and Dynamic-x.y.z-update.zip (this).
The zip holds the app files plus manifest.json: {"version": "x.y.z", "files": {"Dynamic.exe": "<sha256>", ...}}.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError

from src.core.app_info import APP_VERSION
from src.paths import FROZEN, app_dir, data_dir

REPO = "Archiversvoid/Dynamic-yt-dlp-GUI"
API_LATEST = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASES_URL = "https://github.com/%s/releases/latest" % REPO
PACKAGE_RE = re.compile(r"^Dynamic-.*update.*\.zip$", re.I)
OLD_SUFFIX = ".dynold"
PROTECTED_TOP = ("bin", "_update")           # never replaced, never removed
NOT_INSTALLED = "not an installed copy"
PROTECTED_FOLDER = "the install folder is protected"


def _ua():
    return "Dynamic/%s" % APP_VERSION


# ---------------------------------------------------------------- looking for a release
def parse_version(text):
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def is_newer(latest, current):
    a, b = list(parse_version(latest)), list(parse_version(current))
    if not a:
        return False
    n = max(len(a), len(b))
    a += [0] * (n - len(a))
    b += [0] * (n - len(b))
    return a > b


def _pick_asset(assets):
    """The file to update from, best first: Dynamic-x.y.z-update.zip (what build.py makes); any other .zip, whatever it is
    called (e.g. a zip of the app folder); else the installer (.exe). {"name", "url", "size", "sha256", "kind"} or None."""
    def pack(a, kind):
        digest = str(a.get("digest") or "")
        return {"name": a["name"], "url": a["browser_download_url"], "size": int(a.get("size") or 0), "kind": kind,
                "sha256": digest[7:].lower() if digest.lower().startswith("sha256:") else ""}
    def lower(a):
        return str(a.get("name", "")).lower()
    zips = [a for a in assets if lower(a).endswith(".zip")]
    for a in zips:
        if PACKAGE_RE.match(str(a.get("name", ""))):
            return pack(a, "package")
    if zips:
        zips.sort(key=lambda a: not lower(a).startswith("dynamic"))
        return pack(zips[0], "package")
    exes = [a for a in assets if lower(a).endswith(".exe") and ("setup" in lower(a) or "install" in lower(a) or lower(a).startswith("dynamic"))]
    if exes:
        exes.sort(key=lambda a: "setup" not in lower(a))
        return pack(exes[0], "installer")
    return None


def fetch_latest(timeout=15):
    """The newest published release: {"version", "tag", "page", "notes", "asset": {...} | None}.
    None if there is no release to compare with (a repo that hasn't published one yet answers 404). Raises on real failures."""
    req = urllib.request.Request(API_LATEST, headers={"User-Agent": _ua(), "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return None
        raise
    tag = str(data.get("tag_name") or "")
    version = ".".join(str(x) for x in parse_version(tag))
    if not version:                                       # a tag like "nightly": nothing we can compare
        return None
    return {"version": version, "tag": tag, "page": data.get("html_url") or RELEASES_URL,
            "notes": str(data.get("body") or "")[:2000], "asset": _pick_asset(data.get("assets") or [])}


# ---------------------------------------------------------------- can this copy update itself?
def can_apply(app_root=None):
    """(True, "") if this is an installed copy whose folder we can write to; else (False, reason)."""
    if not FROZEN:
        return False, NOT_INSTALLED
    root = Path(app_root or app_dir)
    try:
        probe = root / ".write_test"
        probe.write_text("x")
        probe.unlink()
        return True, ""
    except OSError:
        return False, PROTECTED_FOLDER


# ---------------------------------------------------------------- downloading
def download_package(info, progress=None, dest_dir=None):
    """Download the release's update package, verified. -> path of the zip."""
    asset = info.get("asset")
    if not asset:
        raise RuntimeError("This release has no update package")
    dest_dir = Path(dest_dir or (data_dir / "updates"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / asset["name"]
    part = Path(str(final) + ".part")
    sha = hashlib.sha256()
    try:
        req = urllib.request.Request(asset["url"], headers={"User-Agent": _ua(), "Accept": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or asset.get("size") or 0)
            done = 0
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if asset.get("size") and done != asset["size"]:
            raise RuntimeError("The download is incomplete - try again")
        if asset.get("sha256") and sha.hexdigest() != asset["sha256"]:
            raise RuntimeError("The download is corrupt - try again")
        if asset["name"].lower().endswith(".exe"):
            with open(part, "rb") as f:
                if f.read(2) != b"MZ":
                    raise RuntimeError("The download isn't a valid installer")
        elif not zipfile.is_zipfile(part):
            raise RuntimeError("The download isn't a valid update package")
        os.replace(part, final)
    finally:
        if part.exists():
            try:
                os.remove(part)
            except OSError:
                pass
    return final


def _package_prefix(names):
    """'' if Dynamic.exe is at the top of the zip, 'Folder/' if it is inside a single folder, None if it isn't there."""
    if "Dynamic.exe" in names:
        return ""
    tops = [n[:-len("Dynamic.exe")] for n in names if n.endswith("/Dynamic.exe") and n.count("/") == 1]
    return tops[0] if len(tops) == 1 else None


def prepare_download(path, dest_dir=None):
    """What did we get? -> ("package", zip) to apply in place, or ("installer", exe) to run. A zip that holds an
    installer instead of the app files has the installer taken out of it."""
    path = Path(path)
    if path.suffix.lower() == ".exe":
        return "installer", path
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "manifest.json" in names or _package_prefix(names) is not None:
            return "package", path
        exes = [n for n in names if n.lower().endswith(".exe") and ("setup" in n.lower() or "install" in n.lower())]
        if len(exes) == 1:
            out = Path(dest_dir or path.parent) / Path(exes[0]).name
            with zf.open(exes[0]) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            return "installer", out
    raise RuntimeError("This zip isn't a Dynamic update package")


def run_installer(path):
    """Run a downloaded installer silently: it closes this copy, replaces the files and starts the app again.
    (Only used when a release has no update package. Unlike the in-place update this runs a new exe, which antivirus
    may scan first - signing it is what avoids that.) True if it was started."""
    if not FROZEN:
        return False
    try:
        flags = (0x00000008 | 0x00000200 | 0x08000000) if sys.platform == "win32" else 0
        subprocess.Popen([str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/LAUNCH=1"],
                         cwd=str(Path(path).parent), close_fds=True, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- reading the package
def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_rel(rel):
    """A package path we are willing to write: relative, inside the app folder, not bin\\ and not our own bookkeeping."""
    r = str(rel).replace("\\", "/")
    if not r or r.startswith("/") or ":" in r:
        return None
    parts = r.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    if parts[0] in PROTECTED_TOP or r.lower() == "manifest.json" or r.endswith(OLD_SUFFIX):
        return None
    return r


def read_manifest(zf):
    try:
        data = json.loads(zf.read("manifest.json").decode("utf-8"))
    except KeyError:
        raise RuntimeError("The update package has no manifest")
    files = data.get("files")
    if not isinstance(files, dict) or not files:
        raise RuntimeError("The update package is empty")
    clean = {}
    for rel, digest in files.items():
        r = _safe_rel(rel)
        if not r or not re.fullmatch(r"[0-9a-f]{64}", str(digest).lower()):
            raise RuntimeError("The update package is not valid")
        clean[r] = str(digest).lower()
    return str(data.get("version") or ""), clean


def _installed_manifest(root):
    try:
        with open(root / "manifest.json", "r", encoding="utf-8") as f:
            files = json.load(f).get("files") or {}
        return {r: h for r, h in files.items() if _safe_rel(r)}
    except (OSError, ValueError, AttributeError):
        return {}


def read_package(zf):
    """-> (version, {rel: sha256}, {rel: name inside the zip}, manifest bytes or None).
    A package made by build.py has a manifest.json. A plain zip of the app folder works too (Dynamic.exe at its top, or
    inside a single folder): its hashes are then computed from the zip itself."""
    names = zf.namelist()
    if "manifest.json" in names:
        version, files = read_manifest(zf)
        return version, files, {r: r for r in files}, zf.read("manifest.json")
    if "Dynamic.exe" in names:
        prefix = ""
    else:
        tops = [n[:-len("Dynamic.exe")] for n in names if n.endswith("/Dynamic.exe") and n.count("/") == 1]
        if len(tops) != 1:
            raise RuntimeError("This zip isn't a Dynamic update package")
        prefix = tops[0]
    files, members = {}, {}
    for entry in zf.infolist():
        if entry.is_dir() or not entry.filename.startswith(prefix):
            continue
        rel = _safe_rel(entry.filename[len(prefix):])
        if not rel:                                        # bin\, ../, absolute paths, our own bookkeeping: skipped
            continue
        h = hashlib.sha256()
        with zf.open(entry) as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                h.update(chunk)
        files[rel], members[rel] = h.hexdigest(), entry.filename
    if "Dynamic.exe" not in files:
        raise RuntimeError("This zip isn't a Dynamic update package")
    return "", files, members, None


def plan_update(package, root):
    """-> (version, files, members, manifest, changed, stale): what the package holds, what differs from what is
    installed, and what the old version had that the new one no longer does."""
    root = Path(root)
    with zipfile.ZipFile(package) as zf:
        version, files, members, manifest = read_package(zf)
        names = set(zf.namelist())
    if [r for r in files if members[r] not in names]:
        raise RuntimeError("The update package is incomplete")
    changed = [r for r, h in files.items() if not (root / r).is_file() or _sha256_file(root / r) != h]
    stale = [r for r in _installed_manifest(root) if r not in files and (root / r).exists()]
    return version, files, members, manifest, changed, stale


# ---------------------------------------------------------------- replacing files
def _free_old_name(target):
    for i in range(200):
        cand = target.with_name(target.name + OLD_SUFFIX + ("" if i == 0 else str(i)))
        if not cand.exists():
            return cand
    raise RuntimeError("Too many leftovers of earlier updates")


def _swap_in(target, staged):
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists():
        backup = _free_old_name(target)
        os.replace(target, backup)            # renaming works even while the file is running / loaded
    try:
        os.replace(staged, target)
    except Exception:
        if backup is not None:
            os.replace(backup, target)
        raise
    return (target, backup, True)


def _take_away(target):
    backup = _free_old_name(target)
    os.replace(target, backup)
    return (target, backup, False)


def _undo(entry):
    target, backup, placed = entry
    try:
        if placed and target.exists():
            os.remove(target)
    except OSError:
        pass
    try:
        if backup is not None and backup.exists():
            os.replace(backup, target)
    except OSError:
        pass


def apply_update(package, app_root=None, progress=None, version_hint=""):
    """Extract what changed, verify it, then swap it in. All-or-nothing. -> {"version", "changed", "removed"}."""
    root = Path(app_root or app_dir)
    version, files, members, manifest, changed, stale = plan_update(package, root)
    version = version or version_hint
    if manifest is None:
        manifest = json.dumps({"version": version, "files": files}, indent=1).encode("utf-8")
    staging = root / "_update"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(package) as zf:               # 1. extract and verify everything; the app folder is untouched so far
            for i, rel in enumerate(changed):
                out = staging / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                with zf.open(members[rel]) as src, open(out, "wb") as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        dst.write(chunk)
                        h.update(chunk)
                if h.hexdigest() != files[rel]:
                    raise RuntimeError("An update file is corrupt: " + rel)
                if progress:
                    progress(i + 1, len(changed))
        (staging / "manifest.json").write_bytes(manifest)
        done = []
        try:                                               # 2. swap
            for rel in changed:
                done.append(_swap_in(root / rel, staging / rel))
            for rel in stale:
                done.append(_take_away(root / rel))
            done.append(_swap_in(root / "manifest.json", staging / "manifest.json"))
        except Exception:
            for entry in reversed(done):
                _undo(entry)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    try:
        os.remove(package)
    except OSError:
        pass
    return {"version": version, "changed": len(changed), "removed": len(stale)}


def cleanup_old_files(app_root=None):
    """Delete the *.dynold leftovers of earlier updates (run in the background shortly after start)."""
    root = Path(app_root or app_dir)
    try:
        for p in root.rglob("*" + OLD_SUFFIX + "*"):
            try:
                if p.is_file():
                    p.unlink()
            except OSError:
                pass
        shutil.rmtree(root / "_update", ignore_errors=True)
        cutoff = time.time() - 2 * 86400                       # downloads of earlier updates (zips, installers)
        for p in (data_dir / "updates").glob("*"):
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                pass
    except OSError:
        pass


def restart_app():
    """Start a fresh copy that waits for this one to exit (see claim_or_wake(restart=True)). True if it was started."""
    if not FROZEN:
        return False
    try:
        flags = (0x00000008 | 0x00000200 | 0x08000000) if sys.platform == "win32" else 0     # detached, own group, no window
        subprocess.Popen([sys.executable, "--restart"], cwd=str(app_dir), close_fds=True, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False
