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
        if (-not (Get-ChildItem $raw -Filter *.txt -ErrorAction SilentlyContinue)) { throw "no transcript in $raw" }
        "transcript written"
    }

    Check "serve /report/" {
        $project = Join-Path $work "serve-project"
        Copy-Item -Recurse $Fixture $project
        $log = Join-Path $work "serve.txt"
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
            "report served"
        } finally {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }

    Check "runs from a moved folder" {
        $moved = Join-Path $work ("Bristle nose " + [char]0x00F1 + " " + [char]0x8A66)
        Copy-Item -Recurse $App $moved
        $out = Join-Path $work "moved.txt"
        $code = Invoke-Redirected (Join-Path $moved "bristlenose.exe") "--version" $out
        if ($code -ne 0) { throw "exit $code" }
        "ok"
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
        foreach ($dll in "vcruntime140.dll", "vcruntime140_1.dll") {
            if (-not (Get-ChildItem $App -Recurse -File -Filter $dll)) { throw "$dll missing" }
        }
        "vcruntime140, vcruntime140_1"
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
