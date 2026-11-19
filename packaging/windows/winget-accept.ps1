<#
.SYNOPSIS
  Acceptance run for a Windows installer before it goes to winget: upgrade over
  the published version, refusals while Bristlenose is running, and a clean
  uninstall. Runs inside the Windows guest (aella Server, the UTM VM, any real
  machine), as the user who will own the per-user install.

.DESCRIPTION
  The test list is docs/design-windows-linux-hardware-testing.md section 3.3; the
  sequence it belongs to is section 3.4. Steps, in order (each records ok / FAIL /
  not run, and the run carries on so the uninstall still happens):

    1. Baseline: `winget install --id Bristlenose.Bristlenose -e --version
       <Baseline>` (the published version), then `winget list` must find it.
    2. Upgrade while `serve` runs: the new installer must refuse with exit 7
       (winget maps 7 to packageInUse) and leave the old version working.
    3. Upgrade with nothing running: exit 0, `--version` reads the new version,
       `winget list` reports it, the user PATH has the app folder.
    4. `doctor --self-test`, then (unless -SkipTranscribe) a real transcription
       of a spoken WAV, words checked. The first one downloads a 1.6 GB model.
       With -CpuPaths, the same transcription again under each forced CPU path.
    5. Uninstall while `serve` runs: `winget uninstall` must return within the
       timeout having reached the uninstaller and had it refuse (a non-zero exit,
       not "no package found"), the app must still be there, and no uninstaller
       process may be left waiting on a dialog nobody can see.
    6. Uninstall with nothing running: the folder, the PATH entry and the
       Apps & Features entry all go.

  The verdict is PASSED (exit 0) only when every check ran and passed; any
  FAIL is FAILED (exit 1); otherwise a skipped check makes it INCOMPLETE
  (exit 2), with the skipped checks listed. Without winget, steps 1, 2 and 5
  are skipped, so a guest without winget can never pass.

  What it cannot do: the SmartScreen check (download the installer in Edge and
  double-click it) needs a person; the run prints that reminder at the end.

  winget applies the Mark of the Web to what it downloads, so an unsigned
  baseline shows SmartScreen during step 1. Over SSH that dialog is invisible
  and winget waits forever (docs/release-winget.md, Gotchas): run this from a
  desktop session (`aella rdp`, the UTM window), and click "Run anyway" if it
  appears. Every external command here has a timeout, so a hang is a FAIL with
  its output kept, never a stuck run.

  Written 19 Nov 2026 in a session with no Windows machine, then revised after
  an independent review for checks that could pass without testing anything:
  it had not run anywhere when it was committed. Treat its first run as a test of the script
  as much as of the installer, and fix it in place.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\winget-accept.ps1 `
      -Installer .\bristlenose-0.46.0-setup-x64.exe `
      -ExpectedSha256 EDE0BDA4C4B4574896FDBA350892D6C957930A71F1B2B676F91D3ECB0BC82799
#>
param(
    [Parameter(Mandatory = $true)][string]$Installer,
    # The version winget serves today, installed first so the upgrade is real.
    [string]$Baseline = "0.36.0",
    [string]$ExpectedSha256 = "",
    # A spoken WAV to transcribe. Without one, Windows' own speech synthesiser
    # makes one if it can; Server editions may have no voice.
    [string]$Wav = "",
    [switch]$SkipTranscribe,
    # Also transcribe under forced CPU code paths (design doc section 6.2): the
    # typical Intel laptop (AVX2, no AVX-512), the non-MKL backend AMD CPUs get,
    # and the generic fallback. Same audio, words checked, time recorded.
    [switch]$CpuPaths,
    # Uninstall an existing Bristlenose first instead of refusing to start.
    [switch]$Reset,
    [int]$Port = 8158,
    [string]$WorkDir = ""
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$AppId = "{6C1F8E2A-5B3D-4E7A-9C41-B2E5D8A7F3C9}_is1"   # bristlenose.iss AppId + _is1
$ArpKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"
$PackageId = "Bristlenose.Bristlenose"
$App = Join-Path $env:LOCALAPPDATA "Programs\Bristlenose"
$Exe = Join-Path $App "bristlenose.exe"
# winget's own switches for an Inno installer in silent mode.
$InnoSilent = "/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
$Words = "dashboard"
$Sentence = "Honestly I found the dashboard pretty confusing the first time I opened it."

if (-not $WorkDir) {
    $WorkDir = Join-Path ([IO.Path]::GetTempPath()) ("bn-accept-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
}
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$Transcript = Join-Path $WorkDir "winget-accept.log"
Start-Transcript -Path $Transcript | Out-Null

$results = New-Object System.Collections.Generic.List[object]
function Record([string]$Status, [string]$Name, [string]$Detail) {
    $results.Add([pscustomobject]@{ Status = $Status; Name = $Name; Detail = $Detail })
    $colour = @{ "ok" = "Green"; "FAIL" = "Red"; "not run" = "Yellow" }[$Status]
    Write-Host ("  {0,-8}{1}  {2}" -f $Status, $Name, $Detail) -ForegroundColor $colour
}
function Check([string]$Name, [scriptblock]$Body) {
    try { Record "ok" $Name ([string](& $Body)) }
    catch { Record "FAIL" $Name $_.Exception.Message }
}
function Skip([string]$Name, [string]$Why) { Record "not run" $Name $Why }

# Through cmd: in Windows PowerShell 5.1, a native command's stderr redirected
# with 2>&1 under ErrorActionPreference Stop throws ("process not found").
function Stop-Tree([int]$ProcessId) { cmd.exe /d /c "taskkill /T /F /PID $ProcessId >nul 2>&1" }

# Run a program with a deadline. Output goes to files under $WorkDir, so a
# command that never exits still leaves what it printed. On timeout the whole
# process tree is killed.
$script:runCount = 0
function Invoke-Timed([string]$File, [string]$Arguments, [int]$Seconds) {
    $script:runCount++
    $stem = Join-Path $WorkDir ("{0:D2}-{1}" -f $script:runCount, [IO.Path]::GetFileNameWithoutExtension($File))
    $p = Start-Process -PassThru -WindowStyle Hidden -FilePath $File -ArgumentList $Arguments `
        -RedirectStandardOutput "$stem.out" -RedirectStandardError "$stem.err"
    $null = $p.Handle   # without this, ExitCode can read as null after exit
    $timedOut = -not $p.WaitForExit($Seconds * 1000)
    if ($timedOut) { Stop-Tree $p.Id }
    $text = ((Get-Content "$stem.out" -Raw -ErrorAction SilentlyContinue) + "`n" +
             (Get-Content "$stem.err" -Raw -ErrorAction SilentlyContinue)).Trim()
    [pscustomobject]@{ TimedOut = $timedOut; ExitCode = $(if ($timedOut) { $null } else { $p.ExitCode }); Text = $text; Log = $stem }
}
function Tail([string]$Text, [int]$Chars = 300) {
    $t = ($Text -replace "\s+", " ").Trim()
    if ($t.Length -gt $Chars) { "..." + $t.Substring($t.Length - $Chars) } else { $t }
}

function Installed() { Test-Path $ArpKey }
function InstalledVersion() {
    if (-not (Test-Path $Exe)) { throw "bristlenose.exe is missing at $Exe" }
    $r = Invoke-Timed $Exe "--version" 60
    if ($r.TimedOut -or $r.ExitCode -ne 0) { throw "--version: exit $($r.ExitCode) $(Tail $r.Text)" }
    if ($r.Text -match "bristlenose\s+(\S+)") { return $Matches[1] }
    throw "--version printed no version: $(Tail $r.Text)"
}
function UserPathHasApp() {
    $p = (Get-ItemProperty -Path "HKCU:\Environment" -Name Path -ErrorAction SilentlyContinue).Path
    return ($p -split ";" | Where-Object { $_.TrimEnd("\") -ieq $App.TrimEnd("\") }).Count -gt 0
}
function UninstallerProcesses() {
    # Inno's uninstaller copies itself to %TEMP% as _iuXXXX.tmp and runs that. The
    # name pattern is unverified for Inno 7, so a .tmp image under TEMP counts too.
    $temp = [IO.Path]::GetTempPath().TrimEnd("\")
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        if ($_.ProcessName -like "_iu*" -or $_.ProcessName -like "unins*") { return $true }
        try { $image = $_.Path } catch { $image = $null }
        [bool]($image -and $image -like "$temp\*" -and $image -like "*.tmp")
    }
}
function WaitFor([scriptblock]$Condition, [int]$Seconds) {
    for ($i = 0; $i -lt $Seconds; $i++) { if (& $Condition) { return $true }; Start-Sleep 1 }
    return [bool](& $Condition)
}

$script:serve = $null
function PortAnswers() {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $Port); return $true } catch { return $false } finally { $c.Close() }
}
function ServeAlive() { return [bool]($script:serve -and -not $script:serve.HasExited) }
function Start-Serve() {
    # Asked by connecting, not Get-NetTCPConnection, whose failure reads as "free".
    if (PortAnswers) { throw "port $Port is already in use" }
    $project = Join-Path $WorkDir "serve-project"
    New-Item -ItemType Directory -Force $project | Out-Null
    $log = Join-Path $WorkDir ("serve-{0}" -f (Get-Date -Format "HHmmss"))
    $script:serve = Start-Process -PassThru -WindowStyle Hidden -FilePath $Exe `
        -ArgumentList "serve `"$project`" --port $Port --no-open" `
        -RedirectStandardOutput "$log.out" -RedirectStandardError "$log.err"
    $up = WaitFor { if ($script:serve.HasExited) { return $true }; PortAnswers } 90
    if ($script:serve.HasExited -or -not $up) {
        $err = Get-Content "$log.err" -Raw -ErrorAction SilentlyContinue
        try { $null = Stop-Serve } catch { }
        throw "serve did not start on port ${Port}: $(Tail $err)"
    }
    "serve pid $($script:serve.Id) on port $Port"
}
function Stop-Serve() {
    if ($script:serve -and -not $script:serve.HasExited) {
        $id = $script:serve.Id
        Stop-Tree $id
        if (-not (WaitFor { $script:serve.HasExited } 30)) { throw "serve (pid $id) still running after taskkill" }
    }
    $script:serve = $null
    # Windows releases the image lock a moment after the process goes.
    if (-not (WaitFor { -not (Get-Process -Name bristlenose -ErrorAction SilentlyContinue) } 30)) {
        throw "a bristlenose.exe is still running after serve was stopped"
    }
    "stopped"
}

function ListedVersion([string]$Version) {
    $r = Invoke-Timed $winget "list --id $PackageId -e --accept-source-agreements --disable-interactivity" 120
    $row = '(?m)' + [regex]::Escape($PackageId) + '\s+' + [regex]::Escape($Version) + '(\s|$)'  # single quotes: no $ expansion
    if ($r.TimedOut -or $r.Text -notmatch $row) { throw "no $PackageId $Version row: $(Tail $r.Text)" }
    "listed"
}

# Transcribe the WAV in a fresh folder and find the words in what this run wrote
# (transcripts-raw only, as smoke.ps1 reads it), with extra environment for the run.
function Transcribe([string]$Dir, [hashtable]$Vars) {
    if (Test-Path (Join-Path $Dir "bristlenose-output")) { throw "$Dir already has output; use a fresh -WorkDir" }
    $saved = @{}
    foreach ($k in $Vars.Keys) {
        $saved[$k] = [Environment]::GetEnvironmentVariable($k, "Process")
        [Environment]::SetEnvironmentVariable($k, $Vars[$k], "Process")
    }
    try {
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $r = Invoke-Timed $Exe "transcribe `"$Dir`"" 2400
        $secs = [int]$clock.Elapsed.TotalSeconds
    } finally {
        foreach ($k in $Vars.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], "Process") }
    }
    if ($r.TimedOut -or $r.ExitCode -ne 0) { throw "exit $($r.ExitCode): $(Tail $r.Text)" }
    $raw = Join-Path $Dir "bristlenose-output\transcripts-raw"
    # Joined into one string: -match on an array filters it instead of testing it.
    $txt = (Get-ChildItem -Filter *.txt $raw -ErrorAction SilentlyContinue |
        ForEach-Object { Get-Content -Raw -Encoding UTF8 $_.FullName }) -join "`n"
    if ($txt -notmatch $Words) { throw "no '$Words' in $raw : $(Tail $txt)" }
    [pscustomobject]@{ Seconds = $secs; Text = $r.Text }
}

function Run-Installer([string]$Label) {
    $log = Join-Path $WorkDir ("setup-{0}.log" -f $Label)
    Invoke-Timed $InstallerCopy "$InnoSilent /LOG=`"$log`"" 600
}

try {
    Write-Host "== Bristlenose winget acceptance run, $(Get-Date -Format s)"
    $nt = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    $nativeArch = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment").PROCESSOR_ARCHITECTURE
    $cpu = (Get-ItemProperty "HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0" -ErrorAction SilentlyContinue).ProcessorNameString
    Write-Host ("   Windows: {0} {1} build {2}.{3}; machine {4}; CPU {5}" -f $nt.ProductName, $nt.DisplayVersion,
        $nt.CurrentBuild, $nt.UBR, $nativeArch, $cpu)
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    $sshSession = [bool]$env:SSH_CONNECTION
    Write-Host ("   user {0}; elevated {1}; over SSH {2}; work folder {3}" -f $env:USERNAME, $admin, $sshSession, $WorkDir)
    if ($admin) { Write-Host "   NOTE: elevated. A per-user installer is meant for a normal user; results still count, but say so." -ForegroundColor Yellow }
    if ($sshSession) { Write-Host "   NOTE: over SSH. A SmartScreen dialog in step 1 would be invisible; expect that step to time out." -ForegroundColor Yellow }

    $winget = (Get-Command winget.exe -ErrorAction SilentlyContinue).Source
    if ($winget) {
        $v = Invoke-Timed $winget "--version" 60
        Write-Host "   winget $($v.Text)"
    } else {
        Write-Host "   winget: not installed. Steps that need it are not run." -ForegroundColor Yellow
    }

    # Precondition: the installer, its hash, and no Bristlenose already here.
    if (-not (Test-Path $Installer)) { throw "no installer at $Installer" }
    $InstallerCopy = Join-Path $WorkDir (Split-Path $Installer -Leaf)
    Copy-Item $Installer $InstallerCopy
    # A copy carries no Mark of the Web once unblocked, so the silent runs below
    # cannot stop on SmartScreen. The SmartScreen check is the manual one.
    Unblock-File $InstallerCopy
    $hash = (Get-FileHash -Algorithm SHA256 $InstallerCopy).Hash
    $NewVersion = if ((Split-Path $Installer -Leaf) -match "bristlenose-(\d+\.\d+\.\d+)-setup") { $Matches[1] } else { $null }
    Write-Host "   installer $(Split-Path $Installer -Leaf), version $NewVersion, sha256 $hash"
    if ($ExpectedSha256) {
        Check "installer hash matches" {
            if ($hash -ine $ExpectedSha256) { throw "expected $ExpectedSha256, got $hash" }
            "matches"
        }
    } else {
        Skip "installer hash matches" "no -ExpectedSha256: nothing ties these bytes to the ones submitted"
    }
    if (-not $NewVersion) { throw "cannot read a version from the installer's file name" }
    if ([version]$NewVersion -le [version]$Baseline) {
        throw "the installer ($NewVersion) is not newer than -Baseline $Baseline, so nothing would be upgraded"
    }

    if (Installed) {
        if (-not $Reset) { throw "Bristlenose is already installed for this user; pass -Reset to remove it first" }
        Write-Host "   -Reset: removing the installed Bristlenose first"
        $null = Stop-Serve
        Get-Process -Name bristlenose -ErrorAction SilentlyContinue | Stop-Process -Force
        $un = (Get-ItemProperty $ArpKey).UninstallString -replace '"', ''
        $null = Invoke-Timed $un "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" 300
        if (-not (WaitFor { -not (Installed) -and -not (Test-Path $App) } 180)) { throw "-Reset could not remove the existing install" }
    }

    # ---- 1. Baseline: the published version, through winget ---------------
    Write-Host "== 1. Baseline $Baseline from winget"
    $haveBaseline = $false
    if ($winget) {
        Check "winget install $Baseline" {
            $r = Invoke-Timed $winget ("install --id $PackageId -e --version $Baseline --source winget --silent " +
                "--accept-source-agreements --accept-package-agreements --disable-interactivity") 900
            if ($r.TimedOut) { throw "no exit in 15 min (a SmartScreen dialog nobody can see?): $(Tail $r.Text)" }
            if ($r.ExitCode -ne 0) { throw "exit $($r.ExitCode): $(Tail $r.Text)" }
            $got = InstalledVersion
            if ($got -ne $Baseline) { throw "--version reads $got" }
            $script:haveBaseline = $true
            "bristlenose $got"
        }
        $haveBaseline = $script:haveBaseline
        if ($haveBaseline) {
            Check "winget list finds $Baseline" { ListedVersion $Baseline }
        }
    } else {
        Skip "winget install $Baseline" "no winget"
    }

    # ---- 2. Upgrade while serve runs: must refuse -------------------------
    Write-Host "== 2. Upgrade to $NewVersion while serve runs"
    if ($haveBaseline) {
        $serving = $false
        Check "serve ($Baseline) running" { $r = Start-Serve; $script:serving = $true; $r }
        $serving = $script:serving
        if ($serving) {
            Check "installer refuses while running (exit 7)" {
                if (-not (ServeAlive)) { throw "serve had exited before the installer ran; nothing was tested" }
                $r = Run-Installer "while-running"
                if ($r.TimedOut) { throw "no exit in 10 min: waiting on a dialog?" }
                if (-not (ServeAlive)) { throw "serve exited while the installer ran (exit $($r.ExitCode))" }
                if ($r.ExitCode -ne 7) { throw "exit $($r.ExitCode), expected 7" }
                # bristlenose.iss logs this when its lock probe refuses.
                $log = Get-Content -Raw (Join-Path $WorkDir "setup-while-running.log") -ErrorAction SilentlyContinue
                if ($log -notmatch "bristlenose\.exe is in use") { throw "exit 7, but the setup log shows no running-check refusal" }
                "exit 7, refused by the running check"
            }
            Check "$Baseline still works after the refusal" {
                if (-not (Test-Path (Join-Path $App "_internal"))) { throw "_internal is gone" }
                $got = InstalledVersion
                if ($got -ne $Baseline) { throw "--version reads $got" }
                # --version returns before any native library loads (smoke.ps1).
                $d = Invoke-Timed $Exe "doctor --self-test" 300
                if ($d.TimedOut -or $d.ExitCode -ne 0) { throw "doctor --self-test: exit $($d.ExitCode): $(Tail $d.Text)" }
                "bristlenose $got, self-test passes"
            }
        }
        Check "serve stopped" { Stop-Serve }
    } else {
        Skip "upgrade refusal while running" "no baseline install"
    }

    # ---- 3. Upgrade (or first install) with nothing running ---------------
    $how = if ($haveBaseline) { "upgrade from $Baseline" } else { "fresh install" }
    Write-Host "== 3. $how"
    Check "$how, silent" {
        $r = Run-Installer "install"
        if ($r.TimedOut) { throw "no exit in 10 min" }
        if ($r.ExitCode -ne 0) { throw "exit $($r.ExitCode): see $WorkDir\setup-install.log" }
        "exit 0"
    }
    Check "--version reads $NewVersion" {
        $got = InstalledVersion
        if ($got -ne $NewVersion) { throw "reads $got" }
        "bristlenose $got"
    }
    Check "user PATH has the app folder" { if (-not (UserPathHasApp)) { throw "not in HKCU\Environment Path" }; $App }
    Check "Apps & Features reads $NewVersion" {
        if (-not (Installed)) { throw "no $ArpKey" }
        $shown = (Get-ItemProperty $ArpKey).DisplayVersion
        if ($shown -ne $NewVersion) { throw "DisplayVersion is '$shown'" }
        "DisplayVersion $shown"
    }
    if ($winget) {
        Check "winget list reports $NewVersion" { ListedVersion $NewVersion }
    } else {
        Skip "winget list reports $NewVersion" "no winget"
    }

    # ---- 4. The product works ---------------------------------------------
    Write-Host "== 4. doctor and a transcription"
    Check "doctor --self-test" {
        $r = Invoke-Timed $Exe "doctor --self-test" 300
        if ($r.TimedOut -or $r.ExitCode -ne 0) { throw "exit $($r.ExitCode): $(Tail $r.Text)" }
        "passes"
    }
    if ($SkipTranscribe) {
        Skip "transcribe a spoken WAV" "-SkipTranscribe"
    } else {
        $study = Join-Path $WorkDir "Bristle Study"
        New-Item -ItemType Directory -Force $study | Out-Null
        $haveWav = $false
        if ($Wav) {
            Copy-Item $Wav (Join-Path $study "hello.wav"); $haveWav = $true
        } else {
            try {
                Add-Type -AssemblyName System.Speech
                $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
                $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,
                    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
                $synth.SetOutputToWaveFile((Join-Path $study "hello.wav"), $fmt)
                $synth.Speak($Sentence)
                $synth.Dispose()
                $haveWav = $true
            } catch {
                Skip "transcribe a spoken WAV" "no speech synthesiser here ($($_.Exception.Message)); pass -Wav"
            }
        }
        if ($haveWav) {
            Check "transcribe a spoken WAV" {
                $t = Transcribe $study @{}
                "transcript has '$Words' ($($t.Seconds) s)"
            }
        }
        if ($CpuPaths -and -not $haveWav) { Skip "transcribe, forced CPU paths" "no spoken WAV" }
        if ($CpuPaths -and $haveWav) {
            # CTranslate2 picks its backend by CPU vendor (MKL only on Intel) and its
            # kernels by instruction set; these steer both. It picks AVX2 for its own
            # kernels even on an AVX-512 CPU (measured, 4.9.0), but MKL dispatches
            # for itself, so MKL_CBWR pins MKL to what a typical Intel laptop runs.
            # Never force an instruction set the CPU lacks. MKL is forced on for the
            # Intel and generic paths so an AMD guest runs them too (without MKL there
            # is no MKL line to confirm the pin; measured 19 Nov 2026). CT2_VERBOSE makes CTranslate2
            # print what it chose ("- Selected ISA: AVX2", "- Use Intel MKL: true",
            # read from 4.9.0 on 19 Nov 2026) and MKL_VERBOSE makes MKL print the
            # instruction set it was held to ("CNR:AVX2"); a path not taken fails.
            # On an Intel CPU the CTranslate2 lines of the Intel path match the
            # default run, so only CNR:AVX2 tells it apart. Without these, three runs
            # of the default path would pass under three names.
            # tests/test_windows_packaging.py runs CTranslate2 and checks every
            # pattern against what it prints, and against the default run.
            $paths = @(
                @{ Name = "intel-avx2"; Env = @{ CT2_FORCE_CPU_ISA = "AVX2"; MKL_CBWR = "AVX2"; CT2_USE_MKL = "1"; MKL_VERBOSE = "1" };
                   Expect = @("Selected ISA: AVX2\b", "Use Intel MKL: true\b", "CNR:AVX2\b") },
                @{ Name = "non-mkl"; Env = @{ CT2_USE_MKL = "0" };
                   Expect = @("Use Intel MKL: false\b") },
                @{ Name = "generic"; Env = @{ CT2_FORCE_CPU_ISA = "GENERIC"; MKL_CBWR = "COMPATIBLE"; CT2_USE_MKL = "1"; MKL_VERBOSE = "1" };
                   Expect = @("Selected ISA: GENERIC\b", "CNR:COMPATIBLE\b") }
            )
            foreach ($path in $paths) {
                # Not $name: variable names ignore case, and inside Check's body
                # $name would be Check's own $Name parameter, the label.
                $pathName = $path.Name
                $vars = $path.Env + @{ CT2_VERBOSE = "1" }
                $expect = $path.Expect
                Check "transcribe, CPU path $pathName" {
                    $dir = Join-Path $WorkDir "cpu-$pathName"
                    New-Item -ItemType Directory -Force $dir | Out-Null
                    Copy-Item (Join-Path $study "hello.wav") $dir
                    $t = Transcribe $dir $vars
                    $chosen = ($t.Text -split "`r?`n" | Where-Object { $_ -match "(?i)\b(isa|mkl)\b" }) -join " | "
                    foreach ($pattern in $expect) {
                        if ($t.Text -notmatch $pattern) {
                            throw "forced path not confirmed ($pattern); CTranslate2 said: $(Tail $chosen 200)"
                        }
                    }
                    "'$Words' in $($t.Seconds) s; $(Tail $chosen 160)"
                }
            }
        }
    }

    # ---- 5. Uninstall while serve runs: must refuse, promptly, no dialog ---
    Write-Host "== 5. Uninstall while serve runs"
    if ($winget) {
        $serving = $false
        $script:serving = $false
        Check "serve ($NewVersion) running" { $r = Start-Serve; $script:serving = $true; $r }
        $serving = $script:serving
        if ($serving) {
            Check "winget uninstall refuses promptly" {
                if (-not (ServeAlive)) { throw "serve had exited before the uninstall ran; nothing was tested" }
                $wlog = Join-Path $WorkDir "winget-uninstall-running.log"
                $r = Invoke-Timed $winget ("uninstall --id $PackageId -e --silent --accept-source-agreements " +
                    "--disable-interactivity --log `"$wlog`"") 180
                if ($r.TimedOut) { throw "no exit in 3 min: the hidden-dialog wait is back. $(Tail $r.Text)" }
                # Promptly is only half of it: winget must have reached the uninstaller and
                # had it refuse. A winget that failed before running anything also returns
                # promptly and also leaves the app in place.
                if ($r.Text -match "(?i)No installed package found|Failed when searching|argument") {
                    throw "the uninstaller never ran: $(Tail $r.Text)"
                }
                if ($r.ExitCode -eq 0) { throw "winget reported success, but nothing should have been removed: $(Tail $r.Text)" }
                if (-not (ServeAlive)) { throw "serve exited during the uninstall (exit $($r.ExitCode))" }
                "refused, exit $($r.ExitCode): $(Tail $r.Text 160)"
            }
            Check "no uninstaller left waiting" {
                Start-Sleep 15
                $left = UninstallerProcesses
                if ($left) { throw "still running: $(($left | ForEach-Object { "$($_.ProcessName) ($($_.Id))" }) -join ', ')" }
                "none after 15 s"
            }
            Check "the app is still installed" {
                if (-not (Installed) -or -not (Test-Path $Exe) -or -not (Test-Path (Join-Path $App "_internal"))) {
                    throw "partly or wholly removed while running"
                }
                "intact"
            }
        }
        Check "serve stopped" { Stop-Serve }
        UninstallerProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    } else {
        Skip "uninstall refusal while running" "no winget"
    }

    # ---- 6. Uninstall with nothing running ---------------------------------
    Write-Host "== 6. Uninstall"
    Check "uninstall" {
        if ($winget) {
            $r = Invoke-Timed $winget "uninstall --id $PackageId -e --silent --accept-source-agreements --disable-interactivity" 300
            if ($r.TimedOut) { throw "winget uninstall: no exit in 5 min" }
            $what = "winget exit $($r.ExitCode)"
        } else {
            $un = (Get-ItemProperty $ArpKey).UninstallString -replace '"', ''
            $r = Invoke-Timed $un "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" 300
            $what = "unins000 exit $($r.ExitCode)"
        }
        # The first uninstaller process returns before its copy in %TEMP% finishes.
        if (-not (WaitFor { -not (Test-Path $App) } 180)) { throw "$what; folder still there after 3 min" }
        $what
    }
    Check "Apps & Features entry gone" { if (Installed) { throw "$ArpKey remains" }; "gone" }
    Check "PATH entry gone" { if (UserPathHasApp) { throw "still in HKCU\Environment Path" }; "gone" }
    Check "no uninstaller left running" {
        if (-not (WaitFor { -not (UninstallerProcesses) } 30)) {
            throw "still running: $((UninstallerProcesses | ForEach-Object { "$($_.ProcessName) ($($_.Id))" }) -join ', ')"
        }
        "none"
    }
    $cfg = Join-Path $env:USERPROFILE ".config\bristlenose"
    Write-Host ("   user config folder after uninstall: {0}" -f $(if (Test-Path $cfg) { "kept ($cfg)" } else { "none" }))
}
catch {
    Record "FAIL" "run stopped" $_.Exception.Message
}
finally {
    try { $null = Stop-Serve } catch { Record "FAIL" "serve stopped at the end" $_.Exception.Message }
    $fails = @($results | Where-Object { $_.Status -eq "FAIL" }).Count
    $notRun = @($results | Where-Object { $_.Status -eq "not run" }).Count
    # A skipped step is not a passed one: the uninstall-while-running check, the
    # point of the run, is among the steps that need winget.
    $verdict = if ($fails) { "FAILED" } elseif ($notRun) { "INCOMPLETE" } else { "PASSED" }
    Write-Host ""
    Write-Host ("== {0}: {1} ok, {2} FAIL, {3} not run. Log and outputs: {4}" -f
        $verdict, @($results | Where-Object { $_.Status -eq "ok" }).Count, $fails, $notRun, $WorkDir)
    foreach ($skipped in @($results | Where-Object { $_.Status -eq "not run" })) {
        Write-Host ("   not run: {0} ({1})" -f $skipped.Name, $skipped.Detail) -ForegroundColor Yellow
    }
    Write-Host "   Still a person's job: download the installer in Edge, double-click it, and note what SmartScreen shows."
    Stop-Transcript | Out-Null
}
if ($fails) { exit 1 } elseif ($notRun) { exit 2 } else { exit 0 }
