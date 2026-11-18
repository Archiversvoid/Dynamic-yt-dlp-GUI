"""Makes the update zip from the app you have already built (dist\\Dynamic) - nothing else.

    py make_zip.py

It writes  dist\\Dynamic-<version>-update.zip  (the version comes from src\\core\\app_info.py) and prints where it is.
No PyInstaller and no Inno Setup needed.
"""
import build

if __name__ == "__main__":
    build.main(["--zip-only"])
