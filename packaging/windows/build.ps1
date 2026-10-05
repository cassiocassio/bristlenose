<#
.SYNOPSIS
  Build the self-contained Windows x64 Bristlenose folder (and, with -Installer,
  the Inno Setup installer) from a built wheel. docs/design-winget.md.

.EXAMPLE
  .\packaging\windows\build.ps1 -Wheel dist\bristlenose-0.33.1-py3-none-any.whl -Installer
#>
param(
    [Parameter(Mandatory = $true)][string]$Wheel,
    [string]$Python = "3.12",
    [string]$Out = "build\windows",
    [switch]$Installer
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Step($msg) { Write-Host "==> $msg" }
function Run($exe, [string[]]$argv) {
    & $exe @argv
    if ($LASTEXITCODE -ne 0) { throw "$exe exited $LASTEXITCODE" }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Wheel = (Resolve-Path $Wheel).Path
New-Item -ItemType Directory -Force $Out | Out-Null
$Out = (Resolve-Path $Out).Path
$venv = Join-Path $Out "venv"
$py = Join-Path $venv "Scripts\python.exe"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv is not on PATH" }

Step "build venv (Python $Python)"
if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
Run uv @("venv", "--python", $Python, $venv)
$wheelUrl = "file:///" + ($Wheel -replace "\\", "/")
# Pinned to the set CI tested (packaging/windows/lock.py writes it); a build
# that resolved its own dependencies would ship something nothing tested.
$constraints = Join-Path $root "packaging\windows\constraints.txt"
Run uv @("pip", "install", "--python", $py, "--constraint", $constraints,
    "bristlenose[voice] @ $wheelUrl", "pyinstaller")

Step "PyInstaller"
$dist = Join-Path $Out "dist"
Run $py @("-m", "PyInstaller", "--noconfirm", "--log-level", "WARN",
    "--distpath", $dist, "--workpath", (Join-Path $Out "work"),
    (Join-Path $root "packaging\windows\bristlenose-win.spec"))
$app = Join-Path $dist "bristlenose"

Step "FFmpeg"
# Pinned: a known build, verified by hash, so the installer is reproducible.
# 9.0.2 is what winget's Gyan.FFmpeg installed on both Windows test boxes.
$ffUrl = "https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip"
$ffSha = "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"
$ffZip = Join-Path $Out "ffmpeg-9.0.2.zip"
if (-not (Test-Path $ffZip)) { Invoke-WebRequest -Uri $ffUrl -OutFile $ffZip }
$got = (Get-FileHash $ffZip -Algorithm SHA256).Hash.ToLower()
if ($got -ne $ffSha) { Remove-Item $ffZip; throw "FFmpeg zip hash $got, expected $ffSha" }
$ffDir = Join-Path $Out "ffmpeg"
if (Test-Path $ffDir) { Remove-Item -Recurse -Force $ffDir }
Expand-Archive -Path $ffZip -DestinationPath $ffDir
$bin = Get-ChildItem -Path $ffDir -Recurse -Filter ffmpeg.exe | Select-Object -First 1
# In tools\, not beside bristlenose.exe: the app folder goes on the user PATH,
# and ours must not shadow (or be shadowed by) a user's own FFmpeg.
$tools = Join-Path $app "tools"
New-Item -ItemType Directory -Force $tools | Out-Null
Copy-Item (Join-Path $bin.DirectoryName "ffmpeg.exe") $tools
Copy-Item (Join-Path $bin.DirectoryName "ffprobe.exe") $tools
$lic = Get-ChildItem -Path $ffDir -Recurse -Filter LICENSE* | Select-Object -First 1
if ($lic) { Copy-Item $lic.FullName (Join-Path $tools "FFmpeg-LICENSE.txt") }

# Tells doctor this is the winget/installer build, so its fix text says
# "reinstall with winget", never "pip install" (doctor_fixes.INSTALL_MARKER,
# read from sys.prefix, which is _internal\ in a PyInstaller onedir build).
Set-Content -Path (Join-Path $app "_internal\.install-method") -Value "winget" -NoNewline -Encoding ascii

$size = (Get-ChildItem $app -Recurse | Measure-Object Length -Sum).Sum / 1MB
Step ("folder: {0}  ({1:N0} MB)" -f $app, $size)

Step "smoke: --version"
Run (Join-Path $app "bristlenose.exe") @("--version")

if ($Installer) {
    Step "Inno Setup"
    $iscc = Get-ChildItem -ErrorAction SilentlyContinue -Path "$env:ProgramFiles\Inno Setup *\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup *\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup *\ISCC.exe" |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (-not $iscc) { throw "Inno Setup (ISCC.exe) not found" }
    $version = (& (Join-Path $app "bristlenose.exe") --version).Trim() -replace "^.*?(\d+\.\d+\.\d+).*$", '$1'
    Run $iscc @("/Qp", "/DAppVersion=$version", "/DSourceDir=$app", "/DOutDir=$Out",
        (Join-Path $root "packaging\windows\bristlenose.iss"))
    Get-ChildItem $Out -Filter "bristlenose-*-setup-x64.exe" | ForEach-Object {
        Step ("installer: {0}  ({1:N0} MB)  sha256 {2}" -f $_.FullName, ($_.Length / 1MB), (Get-FileHash $_.FullName).Hash)
    }
}
