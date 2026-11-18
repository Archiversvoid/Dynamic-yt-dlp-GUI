@echo off
rem Builds Dynamic: PyInstaller (one-folder build), then the Inno Setup installer.
rem Needs: Python with PyInstaller + PySide6 installed, and Inno Setup 6.3+ (ISCC.exe).
cd /d "%~dp0"
echo === 1/2  PyInstaller ===
py -m PyInstaller Dynamic.spec --noconfirm --clean || goto :err
echo === 2/2  Inno Setup ===
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
%ISCC% Dynamic.iss || goto :err
echo.
echo Done:  Output\Dynamic-Setup-1.1.0.exe
exit /b 0
:err
echo.
echo BUILD FAILED - see the messages above.
exit /b 1
