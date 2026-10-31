"""
Platform-specific helper functions (Explorer reveal, binary version checks, etc.).
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_qurl(qurl: QUrl):
    QDesktopServices.openUrl(qurl)


def reveal_file(path: str):
    path = os.path.normpath(path)
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer", "/select,", path])
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", path])
        else:
            folder = os.path.dirname(path)
            for fm, args in (
                ("nautilus", ["--select", path]),
                ("dolphin", ["--select", path]),
                ("nemo", [path]),
                ("pcmanfm", [folder]),
                ("thunar", [folder]),
            ):
                if shutil.which(fm):
                    subprocess.Popen([fm] + args)
                    return
            open_qurl(QUrl.fromLocalFile(folder))
    except Exception:
        folder = os.path.dirname(path)
        if os.path.isdir(folder):
            open_qurl(QUrl.fromLocalFile(folder))


def reveal_in_explorer(item, toast_mgr=None):
    path = getattr(item, "final_path", None)
    if path and os.path.isfile(path):
        reveal_file(path)
        return
    if os.path.isdir(item.out_dir):
        open_qurl(QUrl.fromLocalFile(item.out_dir))
    elif toast_mgr:
        toast_mgr.show_toast("That folder no longer exists")