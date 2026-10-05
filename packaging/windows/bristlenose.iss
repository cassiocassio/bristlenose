; Inno Setup script for the Bristlenose CLI on Windows (docs/design-winget.md).
; User scope: no admin, no UAC prompt; installs to %LOCALAPPDATA%\Programs\Bristlenose
; and adds that folder to the user PATH, removing it again on uninstall.
;
; Built by packaging\windows\build.ps1 -Installer, which passes:
;   /DAppVersion=0.33.1  /DSourceDir=<PyInstaller folder>  /DOutDir=<output dir>

#ifndef AppVersion
  #error AppVersion must be defined (/DAppVersion=X.Y.Z)
#endif
#ifndef SourceDir
  #error SourceDir must be defined (/DSourceDir=...)
#endif
#ifndef OutDir
  #define OutDir "."
#endif

[Setup]
; Never change AppId: it is how a newer installer finds and upgrades this one,
; and how winget matches the Apps & Features entry.
AppId={{6C1F8E2A-5B3D-4E7A-9C41-B2E5D8A7F3C9}
AppName=Bristlenose
AppVersion={#AppVersion}
AppVerName=Bristlenose {#AppVersion}
AppPublisher=Bristlenose
AppPublisherURL=https://bristlenose.app
AppSupportURL=https://github.com/cassiocassio/bristlenose/issues
AppUpdatesURL=https://github.com/cassiocassio/bristlenose/releases
DefaultDirName={localappdata}\Programs\Bristlenose
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
; A running `bristlenose serve` holds its files open; ask Restart Manager to
; close it rather than fail half-way through replacing them.
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
OutputDir={#OutDir}
OutputBaseFilename=bristlenose-{#AppVersion}-setup-x64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Bristlenose
UninstallDisplayIcon={app}\bristlenose.exe
MinVersion=10.0.17763

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; An in-place upgrade would otherwise keep DLLs and .pyd files the new build no
; longer ships, which can load ahead of what it does ship.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\tools"

[UninstallDelete]
; Everything the installer put down. User data (~\.config\bristlenose, the
; Whisper model cache, project folders) is not here and is left alone.
Type: filesandordirs; Name: "{app}"

[Code]
const
  EnvKey = 'Environment';

function PathHasDir(Path, Dir: string): Boolean;
begin
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Path) + ';') > 0;
end;

procedure AddToUserPath(Dir: string);
var
  Path: string;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Path) then
    Path := '';
  if PathHasDir(Path, Dir) then
    exit;
  if (Path <> '') and (Path[Length(Path)] <> ';') then
    Path := Path + ';';
  RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Path + Dir);
end;

procedure RemoveFromUserPath(Dir: string);
var
  Path, Upper, Needle: string;
  P: Integer;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Path) then
    exit;
  Path := ';' + Path + ';';
  Upper := Uppercase(Path);
  Needle := ';' + Uppercase(Dir) + ';';
  P := Pos(Needle, Upper);
  while P > 0 do
  begin
    Delete(Path, P, Length(Needle) - 1);
    Upper := Uppercase(Path);
    P := Pos(Needle, Upper);
  end;
  Path := Copy(Path, 2, Length(Path) - 2);
  RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Path);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AddToUserPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromUserPath(ExpandConstant('{app}'));
end;
