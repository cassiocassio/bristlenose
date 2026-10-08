<#
.SYNOPSIS
  Smoke-test a built Windows Bristlenose folder (docs/design-winget.md, step 1.5).
  Run by build.ps1 after PyInstaller and by the Windows CI build job.

.EXAMPLE
  .\packaging\windows\smoke.ps1 -App build\windows\dist\bristlenose
#>
param(
    [Parameter(Mandatory = $true)][string]$App,
    [string]$Fixture = "",
    [int]$Port = 8157,
    [int]$MaxPathLength = 150
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$App = (Resolve-Path $App).Path
if (-not $Fixture) { $Fixture = Join-Path $root "tests\fixtures\smoke-test\input" }
$exe = Join-Path $App "bristlenose.exe"
$failures = New-Object System.Collections.Generic.List[string]

function Check([string]$Name, [scriptblock]$Body) {
    try {
        $detail = & $Body
        Write-Host ("  ok    {0}  {1}" -f $Name, $detail)
    } catch {
        Write-Host ("  FAIL  {0}  {1}" -f $Name, $_.Exception.Message) -ForegroundColor Red
        $failures.Add($Name)
    }
}

# Through cmd so the redirect is a real codepage pipe, the way a user's
# `bristlenose ... > out.txt` is; a PowerShell redirect would re-decode it.
function Invoke-Redirected([string]$Exe, [string]$Arguments, [string]$OutFile) {
    cmd /c "`"$Exe`" $Arguments > `"$OutFile`" 2>&1"
    return $LASTEXITCODE
}

$work = Join-Path ([IO.Path]::GetTempPath()) ("bn-smoke-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force $work | Out-Null
$savedPath = $env:Path
# No Python and no FFmpeg from the machine: the bundle must carry its own.
$env:Path = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue

try {
    Write-Host "Smoke-testing $App"

    Check "--version, redirected" {
        $out = Join-Path $work "version.txt"
        $code = Invoke-Redirected $exe "--version" $out
        if ($code -ne 0) { throw "exit $code" }
        (Get-Content $out -Raw).Trim()
    }

    Check "--help, redirected" {
        $out = Join-Path $work "help.txt"
        $code = Invoke-Redirected $exe "--help" $out
        if ($code -ne 0) { throw "exit $code" }
        if ((Get-Content $out -Raw) -notmatch "transcribe") { throw "help does not list transcribe" }
        "lists commands"
    }

    Check "doctor --self-test" {
        $out = Join-Path $work "selftest.txt"
        $code = Invoke-Redirected $exe "doctor --self-test" $out
        if ($code -ne 0) { throw "exit $code`n$(Get-Content $out -Raw)" }
        "all bundle checks pass"
    }

    Check "transcribe, awkward folder name" {
        $study = Join-Path $work ("My Study " + [char]0x4F1A + [char]0x8B70)
        New-Item -ItemType Directory -Force $study | Out-Null
        Copy-Item (Join-Path $Fixture "Session 1.vtt") $study
        $out = Join-Path $work "transcribe.txt"
        $code = Invoke-Redirected $exe "transcribe `"$study`"" $out
        if ($code -ne 0) { throw "exit $code`n$(Get-Content $out -Raw)" }
        $raw = Join-Path $study "bristlenose-output\transcripts-raw"
        $txt = Get-ChildItem $raw -Filter *.txt -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $txt) { throw "no transcript in $raw" }
        # A line from the fixture: an empty or garbled transcript must not pass.
        if ((Get-Content $txt.FullName -Raw -Encoding UTF8) -notmatch "dashboard pretty confusing") {
            throw "$($txt.Name) does not carry the fixture's words"
        }
        "transcript written"
    }

    Check "serve /report/" {
        # A leftover server on the port would answer for ours (the stale-:8150
        # trap in CLAUDE.md), so the port must be free, and the answer must name
        # this fixture's project through our own token.
        if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
            throw "port $Port is already in use; stop whatever is listening there"
        }
        $project = Join-Path $work "serve-project"
        Copy-Item -Recurse $Fixture $project
        $log = Join-Path $work "serve.txt"
        $token = [guid]::NewGuid().ToString("N")
        $env:_BRISTLENOSE_AUTH_TOKEN = $token
        $proc = Start-Process -PassThru -WindowStyle Hidden -FilePath $exe `
            -ArgumentList "serve", "`"$project`"", "--port", "$Port", "--no-open" `
            -RedirectStandardOutput $log -RedirectStandardError "$log.err"
        try {
            $ok = $false
            for ($i = 0; $i -lt 60 -and -not $ok; $i++) {
                Start-Sleep 1
                if ($proc.HasExited) { throw "serve exited $($proc.ExitCode)`n$(Get-Content "$log.err" -Raw)" }
                try {
                    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$Port/report/"
                    if ($r.StatusCode -eq 200 -and $r.Content -match "bn-app-root") { $ok = $true }
                } catch { }
            }
            if (-not $ok) { throw "no report with bn-app-root on port $Port within 60 s" }
            $info = Invoke-RestMethod -TimeoutSec 10 -Headers @{ Authorization = "Bearer $token" } `
                "http://127.0.0.1:$Port/api/projects/1/info"
            if ($info.project_name -ne "Smoke Test") { throw "the server on $Port is serving '$($info.project_name)', not the fixture" }
            "report served"
        } finally {
            Remove-Item Env:_BRISTLENOSE_AUTH_TOKEN -ErrorAction SilentlyContinue
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $proc.WaitForExit(15000) | Out-Null
        }
    }

    Check "runs from a moved folder" {
        # The self-test, not --version: --version returns before any native
        # library or data file loads, so a build-time path would still pass it.
        $moved = Join-Path $work ("Bristle nose " + [char]0x00F1 + " " + [char]0x8A66)
        Copy-Item -Recurse $App $moved
        $out = Join-Path $work "moved.txt"
        $code = Invoke-Redirected (Join-Path $moved "bristlenose.exe") "doctor --self-test" $out
        if ($code -ne 0) { throw "exit $code`n$(Get-Content $out -Raw)" }
        "self-test passes from $moved"
    }

    Check "deepest path <= $MaxPathLength" {
        $longest = Get-ChildItem $App -Recurse -File | ForEach-Object { $_.FullName.Substring($App.Length + 1) } |
            Sort-Object Length -Descending | Select-Object -First 1
        if ($longest.Length -gt $MaxPathLength) { throw "$($longest.Length): $longest" }
        "$($longest.Length) characters"
    }

    Check "no CUDA libraries" {
        # ctranslate2's wheel carries a 0.3 MB cudnn64_9.dll stub; anything else
        # CUDA-shaped means a GPU build slipped in (docs/design-winget.md, CPU only).
        $cuda = Get-ChildItem $App -Recurse -File -Include "cublas*.dll", "cudart*.dll", "cudnn*.dll", "nvrtc*.dll" |
            Where-Object { $_.Name -ne "cudnn64_9.dll" -or $_.Length -gt 2MB }
        if ($cuda) { throw ($cuda.Name -join ", ") }
        "none beyond ctranslate2's stub"
    }

    Check "VC++ runtime bundled" {
        # Beside python312.dll, where the loader looks; a copy deeper in a
        # package folder would not be found, and the runner's System32 copy
        # would hide that from every other check.
        $internal = Join-Path $App "_internal"
        foreach ($dll in "python312.dll", "vcruntime140.dll", "vcruntime140_1.dll") {
            if (-not (Test-Path (Join-Path $internal $dll))) { throw "$dll missing from $internal" }
        }
        "vcruntime140, vcruntime140_1 beside python312.dll"
    }
} finally {
    $env:Path = $savedPath
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host ("{0} smoke check(s) failed: {1}" -f $failures.Count, ($failures -join "; ")) -ForegroundColor Red
    exit 1
}
Write-Host "All smoke checks passed."
