<meta name="google-site-verification" content="wVLqXrOqswWKlRo1MyL58tblpG1Yvchn07atnpanGWM" />

<p align="center">
  <img src="assets/DYN.png" alt="Dynamic logo" width="120" />
</p>

<h1 align="center">Dynamic</h1>

<h3 align="center">A simple, cutting-edge yt-dlp GUI</h3>

<p align="center">
  <a href="https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/releases/latest"><img src="https://img.shields.io/github/v/release/Archiversvoid/Dynamic-yt-dlp-GUI?color=1fc8aa&label=release" alt="Latest release"></a>
  <a href="https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/releases"><img src="https://img.shields.io/github/downloads/Archiversvoid/Dynamic-yt-dlp-GUI/total?color=1fc8aa" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Archiversvoid/Dynamic-yt-dlp-GUI?color=1fc8aa" alt="License: GPL-3.0"></a>
  <img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078d6" alt="Platform: Windows 10 and 11">
  <a href="https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/actions/workflows/build.yml"><img src="https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/actions/workflows/build.yml/badge.svg" alt="Build"></a>
  <a href="https://discord.gg/D2x2MVmre"><img src="https://img.shields.io/badge/chat-Discord-5865F2?logo=discord&logoColor=white" alt="Discord"></a>
</p>

<p align="center">
  <b>Dynamic is a free, open-source yt-dlp GUI.</b> Download video and audio from YouTube, YouTube Music, Instagram, TikTok, Reddit, SoundCloud and 1000+ more sites supported by the yt-dlp engine. Licensed under GPL-3.0.
</p>

<p align="center">
  <a href="#installation">Install</a> ·
  <a href="#features">Features</a> ·
  <a href="#trimload-notes">TrimLoad notes</a> ·
  <a href="#security-and-antivirus-warnings">Security</a> ·
  <a href="#build-from-source">Build from source</a> ·
  <a href="#contributing">Contribute</a>
</p>

---

## Screenshots

<p align="center">
  <img src="assets/home.png" alt="Dynamic reading a link's streams" width="800" /><br/>
  <sub><b>Home</b> – paste a link and Dynamic reads the available streams.</sub>
</p>

<p align="center">
  <img src="assets/trimload.png" alt="TrimLoad previewing a video and trimming it" width="800" /><br/>
  <sub><b>TrimLoad</b> – preview the video, set a start and end, and download only that part.</sub>
</p>

## Features

- **Video or audio** – choose a resolution for video, or switch to audio and pick an MP3 bitrate. An estimated file size is shown before you download.
- **Precision clip trimming (TrimLoad)** – watch a preview, pick the exact start and end, and download only that segment instead of the whole video.
- **Downloads tab** – live progress, speed, ETA and thumbnails for every download. If something fails, Dynamic tells you why in plain words.
- **Dark and light themes** – follows Windows by default, or choose one in Settings.
- **Stays up to date** – one place (Settings > Update) keeps yt-dlp, ffmpeg and Dynamic itself current. Updates replace only the files that changed, and yt-dlp/ffmpeg can update on a schedule.
- **Lives in the tray** – closing the window keeps Dynamic running quietly in the system tray; opening it again just brings it back.
- **First-run guide** – a short setup wizard walks you through the terms and downloads the two helper programs for you.
- **No ads, accounts or analytics.**

## Installation

### Windows installer (recommended)

1. Open the [**latest release**](https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/releases/latest) and download `Dynamic-Setup-1.1.0.exe`.
2. Run it. **Windows or your antivirus may warn you** because the app is not code-signed – see [Security and antivirus warnings](#security-and-antivirus-warnings) for what to do.
3. Leave *Launch Dynamic* ticked on the last page. The setup guide opens, asks you to accept the terms, and offers to download **yt-dlp** and **ffmpeg** (you can skip this and do it later from the Home page or Settings).

**Requirements:** Windows 10 or 11 (64-bit) and an internet connection for the first setup. No administrator rights are needed.

By default Dynamic installs to `%LOCALAPPDATA%\Programs\Dynamic`; you can pick another folder in the installer.

### Updating

Dynamic checks for new releases by itself and shows a notification. Press **Update** and it downloads the new version, swaps in only the files that changed, and offers to restart. You can also check manually under **Settings > Update > Dynamic**. If you press *Remind me later*, the notification stays quiet for 24 hours.

### Uninstalling

Use **Windows Settings > Apps > Installed apps > Dynamic > Uninstall**. The uninstaller asks whether to also delete your settings and download history; your downloaded files are never touched.

## Quick start

1. **Paste a link** on the Home page and press Enter. Dynamic contacts the site and reads the available streams.
2. In **TrimLoad**, choose **Video** or **Audio**, pick a quality, and (if you only want a clip) drag the handles or type the **Start** and **End** times.
3. Press **Download**, then follow it in the **Downloads** tab.

If yt-dlp or ffmpeg is missing, a notification on the Home and TrimLoad pages lets you download it with one click, or point Dynamic at a copy you already have (**From disk...**).

## TrimLoad notes

> [!NOTE]
> **TrimLoad is not 100% perfect.** The preview depends on what each website allows, so a few things can behave differently from site to site.

- **Some sites don't allow streaming with audio.** The preview may play without sound even though the finished download has it.
- **Some videos show "Preview not available".** The site may not offer a stream that can be played directly. Downloading usually still works – you just can't scrub through the preview first.
- **Some formats can't be previewed.** The preview uses Windows' built-in media engine, so a few codecs (for example VP9/AV1) may not play even when downloading them works fine.
- **Live and scheduled streams are not supported** in TrimLoad.
- **The estimated size is only an estimate.** The real file can differ a little.
- Trimming needs **ffmpeg**.

If a site behaves badly, please [open an issue](https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/issues) with the link (if it's public) and what you saw.

## Security and antivirus warnings

> [!WARNING]
> **Dynamic is not code-signed.** Code-signing certificates cost money, and a brand-new unsigned program has no reputation yet. Because of that, Windows SmartScreen or your antivirus can warn about the installer or even block it. This is a **false positive**, but you don't have to take my word for it – see below.

**What you might see**

- **Windows SmartScreen – "Windows protected your PC".** Click **More info**, then **Run anyway**.
- **Avast / other antivirus – "checking if the file contains malware" or a quarantine.** Let the scan finish. If the file is quarantined, restore it and add an exception, or submit it to your antivirus vendor as a false positive. The first launch after an update can be scanned again because the file is new.

**How to check for yourself**

- **The source is public.** Everything in this repository is what gets built – read it, or build it yourself (see [Build from source](#build-from-source)).
- **Releases are built automatically by GitHub Actions** from this repository, not on a private machine. You can read the [workflow](.github/workflows/build.yml) and see every build in the *Actions* tab.
- **Compare checksums.** Each release has a `.sha256.txt` file. In PowerShell, run the following in the folder you downloaded to, and compare the result with the file:

  ```powershell
  Get-FileHash .\Dynamic-Setup-x.y.z.exe -Algorithm SHA256
  ```

## Where Dynamic keeps its files

| What | Where |
| --- | --- |
| The app | `%LOCALAPPDATA%\Programs\Dynamic` (or the folder you chose) |
| yt-dlp and ffmpeg | the `bin` folder inside the app folder |
| Settings, download list, cache, logs | `%APPDATA%\Dynamic` |
| Your downloads | your Windows **Downloads** folder (change it in Settings) |

## Build from source

You only need this if you want to run or change the code. Normal users should use the [installer](#installation).

### Prerequisites

- **Windows 10 or 11**
- **[Python 3.12](https://www.python.org/downloads/)** (the version releases are built with)
- **[Git](https://git-scm.com/downloads)** – only to download the code (the "clone" step below)
- **[Inno Setup 6.3+](https://jrsoftware.org/isinfo.php)** – only if you want to build the installer

### Run it

Run this command to clone the repo *developers only*.

```powershell
# 1. Download a copy of the code and go into the folder
git clone https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI.git
cd Dynamic-yt-dlp-GUI

# 2. Create an isolated Python environment and switch it on
python -m venv .venv
.venv\Scripts\activate

# 3. Install what the app needs (yt-dlp is used directly when running from source)
pip install -r requirements.txt
pip install yt-dlp

# 4. Start it
python launcher.py
```

ffmpeg: put `ffmpeg.exe` and `ffprobe.exe` in a folder named `bin` next to `launcher.py` (or have them on your `PATH`), or let the in-app notification download them.

### Build the installer

```powershell
python build.py            # PyInstaller build + update package + installer
python build.py --help     # (see the top of build.py for all options)
```

The installer ends up in `Output\` and the in-app update package in `dist\`.

### Project structure

```text
launcher.py        entry point: splash screen, then starts the app
main.py            the main window
setup_wizard.py    first-run setup guide
theme.py           dark/light theme engine
src/core/          downloading, yt-dlp/ffmpeg handling, updates
src/ui/            interface: tabs, TrimLoad, components
icons/  assets/    images
build.py           builds the app, the update package and the installer
Dynamic.spec       PyInstaller configuration
Dynamic.iss        Inno Setup (installer) script
.github/workflows/ automatic release builds
```

<details>
<summary><b>For maintainers: how releases are made</b></summary>

Releases are built by the **Build release** workflow – the version always comes from what you type, never from the file.

- **From the Actions tab:** *Build release > Run workflow*, type a version such as `1.2.0`. It builds the installer and the in-app update package and leaves them on a **draft** release. Open the draft, write the notes, and press *Publish release*.
- **From the Releases page:** create a release with a **new tag** (`v1.2.0` or `1.2.0`) and publish it. Creating the tag starts the build, which attaches the files to your release.
- Leaving the version empty makes a test build (files are kept on the run, no release is made).
- The first release (1.1.0) ships the installer only; later releases also include `Dynamic-x.y.z-update.zip`, which the in-app updater downloads.

</details>

## Contributing

Bug reports, ideas and pull requests are welcome.

- **Found a bug or want a feature?** [Open an issue](https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/issues). Please include your Windows version, the Dynamic version (Settings > Update), what you expected, and what happened. Logs are in `%APPDATA%\Dynamic\logs`.
- **Want to change the code?**
  1. **Fork** the repository (the *Fork* button, top right).
  2. **Clone your fork** and make a branch:
     ```powershell
     git clone https://github.com/<your-username>/Dynamic-yt-dlp-GUI.git
     cd Dynamic-yt-dlp-GUI
     git checkout -b my-change
     ```
  3. Make your change, then save and upload it:
     ```powershell
     git add .
     git commit -m "Describe what you changed"
     git push origin my-change
     ```
  4. On GitHub, press **Compare & pull request**.

## Community

- 💬 [Discord](https://discord.gg/D2x2MVmre)
- 👽 [Reddit – u/Archivers_void](https://reddit.com/users/Archivers_void)
- 🐛 [Bugs](https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/issues)
- ✨ [Ideas](https://github.com/Archiversvoid/Dynamic-yt-dlp-GUI/discussions)

## Disclaimer

Dynamic is a graphical front end for [yt-dlp](https://github.com/yt-dlp/yt-dlp). It does not host, provide or endorse any content. You are responsible for following the terms of service of the sites you download from and the copyright laws that apply to you. Dynamic is not affiliated with yt-dlp, FFmpeg, or any website it can download from.

## License and credits

Dynamic is licensed under the **GNU General Public License v3.0** – see [LICENSE](LICENSE).

Built with the help of these projects (downloaded separately; not bundled in the app):

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) – the download engine
- [FFmpeg](https://ffmpeg.org/) – merging, trimming and converting (Windows builds by [gyan.dev](https://www.gyan.dev/ffmpeg/builds/))
- [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/) – the interface
- [PyInstaller](https://pyinstaller.org/) and [Inno Setup](https://jrsoftware.org/isinfo.php) – packaging and the installer
