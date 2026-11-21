; Dynamic - Inno Setup script (Inno Setup 6.3 or newer)
;
; Compile with Build > Compile (Ctrl+F9). "Run" (F9) also starts the installer under the IDE's debugger, which can fail with
; "Debugger version ... does not match Setup version ..." - the compiled installer itself is fine.
;
; Build order:  1) py -m PyInstaller Dynamic.spec --noconfirm --clean     -> dist\Dynamic\
;               2) compile this script (ISCC.exe Dynamic.iss)             -> Output\Dynamic-Setup-1.1.0.exe
; build.bat does both.
;
; Where things go:
;   {app}                      the install folder (default: %LOCALAPPDATA%\Programs\Dynamic, no admin needed;
;                              the user can pick another place, or install for all users from the dialog)
;   {app}\bin                  yt-dlp + ffmpeg (created here; the app tells the user if they are missing)
;   %APPDATA%\Dynamic          everything the app writes: settings, downloads list, cache, logs, binary_dir.json
;                              (kept on uninstall unless the user chooses to remove it)

#define MyAppName "Dynamic"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"          ; build.py passes the real one (from src\core\app_info.py) with /DMyAppVersion=
#endif
#define MyAppPublisher "Archivers_void"
#define MyAppURL "https://Github.com/Archiversvoid/Dynamic-yt-dlp-GUI"
#define MyAppExeName "Dynamic.exe"

[Setup]
; AppId identifies this app to Windows and to every future update. NEVER change it: a new value makes updates install
; side by side as a second app instead of replacing this one.
AppId={{8C5E4D2A-3B1F-4A7C-9E26-5D1B7F0A94C3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppComments=Dynamic yt-dlp GUI
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Always show the folder page (by default Setup silently reuses the folder of an earlier install),
; and use exactly the folder the user types or picks - nothing is appended to it.
DisableDirPage=no
UsePreviousAppDir=yes
AppendDefaultDirName=no
PrivilegesRequired=lowest
; Per-user install: no administrator rights, so Windows never shows a UAC prompt for this installer.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=Dynamic-Setup-{#MyAppVersion}
; the thumbnail of the installer file itself
#if FileExists(SourcePath + "icons\icon 2.ico")
SetupIconFile=icons\icon 2.ico
#else
SetupIconFile=icons\icon.ico
#endif
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Dynamic yt-dlp GUI
VersionInfoProductName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}\bin"; Permissions: users-modify
Name: "{userappdata}\{#MyAppName}"

[Files]
Source: "dist\Dynamic\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "TERMS.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "TERMS.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "CHANGELOG.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--setup"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; the in-app updater runs the installer silently (/LAUNCH=1) when a release has no update package: start the app again afterwards
Filename: "{app}\{#MyAppExeName}"; Parameters: "--restart"; Flags: nowait; Check: LaunchAfterSilentUpdate

[UninstallRun]
; Dynamic keeps running in the system tray after its window is closed - stop it before its files are removed
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden; RunOnceId: "StopDynamic"

[UninstallDelete]
; files added by in-app updates are not in the installer's list, so name the app's own folders (never {app} as a whole:
; the user may have installed into a folder that holds other things)
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\bin"
Type: filesandordirs; Name: "{app}\icons"
Type: filesandordirs; Name: "{app}\assets"
Type: filesandordirs; Name: "{app}\_update"
Type: files; Name: "{app}\manifest.json"
Type: files; Name: "{app}\*.dynold*"

[Code]
function LaunchAfterSilentUpdate: Boolean;
begin
  Result := ExpandConstant('{param:LAUNCH|0}') = '1';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  { an older copy may be hiding in the tray: stop it so its files can be replaced }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    if MsgBox('Also delete Dynamic''s settings, download history, cache and logs?' + #13#10 + #13#10 +
              'Your downloaded files are not touched.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\{#MyAppName}'), True, True, True);
  end;
end;
