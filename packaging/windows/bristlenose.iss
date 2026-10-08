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
; Inno removes the files it installed; these catch anything created inside our
; own folders since. Never "{app}" itself with filesandordirs: winget passes
; --location through as /DIR=, so {app} can be a folder of the user's, and that
; entry would delete everything in it. dirifempty removes {app} only when
; nothing of theirs is left. User data (~\.config\bristlenose, the Whisper
; model cache, project folders) is elsewhere and is left alone.
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\tools"
Type: dirifempty; Name: "{app}"

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
  begin
    // A Path that exists but cannot be read as a string must not be replaced
    // by one holding only our folder.
    if RegValueExists(HKCU, EnvKey, 'Path') then
    begin
      Log('User Path exists but could not be read; left unchanged.');
      exit;
    end;
    Path := '';
  end;
  if PathHasDir(Path, Dir) then
    exit;
  if (Path <> '') and (Path[Length(Path)] <> ';') then
    Path := Path + ';';
  if not RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Path + Dir) then
    Log('Could not write the user Path.');
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
  if not RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Path) then
    Log('Could not write the user Path.');
end;

// A running bristlenose.exe (serve, or a transcription) holds its files open.
// Restart Manager cannot always close it: for a non-admin user RmGetList
// failed on Windows Server 2025, the exe could not be replaced, and the
// rollback left bristlenose.exe without _internal, which [InstallDelete] had
// already removed. So refuse up front, before anything is touched, rather than
// kill what may be a long transcription.
//
// The test is the lock itself: Windows refuses a write open of a running
// image, for any user, whatever share mode is asked for. Sharing everything
// keeps readers that also share (Defender scanning, Explorer's preview) from
// reading as "running". A WMI process query was tried first and failed open,
// because a non-admin user can be refused WMI access ("SWbemLocator: Access
// denied", measured over SSH on Windows Server 2025).
function BristlenoseRunning(): Boolean;
var
  Exe: string;
  Stream: TFileStream;
begin
  Result := False;
  Exe := ExpandConstant('{app}\bristlenose.exe');
  if not FileExists(Exe) then
    exit;
  try
    Stream := TFileStream.Create(Exe, fmOpenReadWrite or fmShareDenyNone);
    Stream.Free;
  except
    Log('bristlenose.exe is in use: ' + GetExceptionMessage);
    Result := True;
  end;
end;

function RunningMessage(): String;
begin
  Result := 'Bristlenose is running (bristlenose serve, or a transcription), ' +
    'or bristlenose.exe is locked. Stop it, then run this again.';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if BristlenoseRunning() then
    Result := RunningMessage;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  if BristlenoseRunning() then
  begin
    SuppressibleMsgBox(RunningMessage, mbError, MB_OK, IDOK);
    Result := False;
  end;
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
