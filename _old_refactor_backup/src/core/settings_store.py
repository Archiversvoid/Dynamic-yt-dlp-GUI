"""
Persistent configuration management for Dynamic.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def get_repo_root() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return REPO_ROOT


def load_settings() -> dict:
    root = get_repo_root()
    default_settings = {
        "download_dir": str(root / "downloads"),
        "sidebar_collapsed": False,
        "theme": "Default",
    }
    settings_path = root / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_settings.update(loaded)
        except Exception:
            pass
    return default_settings


def save_settings(settings: dict):
    root = get_repo_root()
    try:
        with open(root / "settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass