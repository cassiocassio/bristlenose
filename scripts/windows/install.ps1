# Bristlenose installer for Windows.
#
#   irm https://bristlenose.app/install.ps1 | iex
#
# Installs, for the current user and without administrator rights:
#   1. uv, using Astral's own installer (skipped if uv is already on PATH)
#   2. FFmpeg and ffprobe: winget's Gyan.FFmpeg when winget works, otherwise a
#      pinned build from the same publisher, checked against its SHA-256
#   3. bristlenose, with `uv tool install --python 3.13` (or `uv tool upgrade`
#      when it is already installed, so running this again upgrades)
# then puts everything on PATH for this window and for new ones, and runs
# `bristlenose doctor`.
#
# It never asks for administrator rights, never changes your execution policy,
# and never reads or writes an API key.
#
# Two settings exist for testing, and nobody else needs them:
#   BRISTLENOSE_INSTALL_SPEC    what uv installs (default: bristlenose)
#   BRISTLENOSE_INSTALL_FFMPEG  auto | winget | zip (default: auto)
#
# Keep this file plain ASCII: PowerShell 5.1 decodes a download with no charset
# as Latin-1, so any other character arrives garbled. tests/test_windows_installer.py
# checks it, along with the other promises above.

& {
    Set-StrictMode -Version 2

    # Pinned fallback FFmpeg: GyanD/codexffmpeg is where winget's Gyan.FFmpeg
    # comes from. The hash was computed from the downloaded file, 5 Oct 2026.
    $FfmpegZipUrl = 'https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip'
    $FfmpegZipSha256 = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
    $UvInstallerUrl = 'https://astral.sh/uv/install.ps1'
    $PythonVersion = '3.13'   # the voice extra has no Windows wheel for 3.14 yet

    $ProgressPreference = 'SilentlyContinue'  # PowerShell 5.1's progress bar makes downloads crawl
    $ErrorActionPreference = 'Continue'       # native tools write progress to stderr; we check exit codes

    function Write-Step([string]$Text) { Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
    function Write-Done([string]$Text) { Write-Host "    $Text" -ForegroundColor Green }
    function Write-Note([string]$Text) { Write-Host "    $Text" }
    function Write-Caution([string]$Text) { Write-Host "    $Text" -ForegroundColor Yellow }

    # A failure we can explain: throws, and the message is the whole story for the user.
    function Exit-Install([string]$Text) { throw [System.Exception]::new("BRISTLENOSE-INSTALL: $Text") }

    function Get-Setting([string]$Name, [string]$Default) {
        $value = [Environment]::GetEnvironmentVariable($Name)
        if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
        return $value.Trim()
    }

    function Split-PathList([string]$PathValue) {
        if ([string]::IsNullOrEmpty($PathValue)) { return @() }
        return @($PathValue -split ';' | Where-Object { $_ -ne '' })
    }

    # Pull PATH entries added to the registry (by uv's installer, winget,
    # `uv tool update-shell` or us) into this window, in front, without
    # dropping anything this window already had.
    function Sync-SessionPath {
        $current = @(Split-PathList $env:Path)
        $added = @()
        foreach ($scope in 'User', 'Machine') {
            foreach ($entry in Split-PathList ([Environment]::GetEnvironmentVariable('Path', $scope))) {
                $expanded = [Environment]::ExpandEnvironmentVariables($entry).TrimEnd('\')
                $known = @($current + $added | ForEach-Object { $_.TrimEnd('\') })
                if ($known -notcontains $expanded) { $added += $expanded }
            }
        }
        if ($added.Count -gt 0) { $env:Path = (@($added) + @($current)) -join ';' }
    }

    function Add-SessionPath([string]$Dir) {
        $known = @(Split-PathList $env:Path | ForEach-Object { $_.TrimEnd('\') })
        if ($known -notcontains $Dir.TrimEnd('\')) { $env:Path = "$Dir;$env:Path" }
    }

    # Add a folder to the user's own PATH, the way uv's installer does: keep the
    # value REG_EXPAND_SZ, then tell open programs the environment changed.
    function Add-UserPath([string]$Dir) {
        $key = 'registry::HKEY_CURRENT_USER\Environment'
        $existing = @(Split-PathList ((Get-Item -LiteralPath $key).GetValue('Path', '', 'DoNotExpandEnvironmentNames')))
        if ($existing -contains $Dir) { return }
        Set-ItemProperty -Type ExpandString -LiteralPath $key -Name Path -Value ((@($Dir) + @($existing)) -join ';')
        $dummy = 'bristlenose-install-' + [guid]::NewGuid().ToString()
        [Environment]::SetEnvironmentVariable($dummy, '1', 'User')
        [Environment]::SetEnvironmentVariable($dummy, [NullString]::Value, 'User')
    }

    function Test-Command([string]$Name) {
        return [bool](Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue)
    }

    function Get-CommandDir([string]$Name) {
        $cmd = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { return Split-Path -Parent $cmd.Source }
        return $null
    }

    # Group Policy beats -ExecutionPolicy on the command line, so it is the one
    # policy that can stop uv's installer even though we run it with Bypass.
    function Get-PolicyBlock {
        foreach ($scope in 'MachinePolicy', 'UserPolicy') {
            $policy = (Get-ExecutionPolicy -Scope $scope).ToString()
            if ($policy -in 'Restricted', 'AllSigned') { return "$policy, set by $scope" }
        }
        return $null
    }

    function Test-Winget {
        if (-not (Test-Command 'winget')) { return $false }
        $null = & winget --version 2>&1
        return ($LASTEXITCODE -eq 0)
    }

    function Install-WingetPackage([string]$Id) {
        & winget install --id $Id -e --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
        return ($LASTEXITCODE -eq 0)
    }

    function Get-DownloadFailure([string]$What, [string]$Url, $ErrorRecord) {
        return "Could not download $What from $Url ($($ErrorRecord.Exception.Message)). " +
            'If this computer is behind a company proxy or firewall, that is the likely cause: ' +
            'ask IT to allow it, or follow the manual steps at https://bristlenose.app/docs/install.html'
    }

    # Set once uv has put Bristlenose in place. A later failure (PATH, doctor)
    # must not tell the user it was never installed.
    $installed = $false
    try {
        # ----- 0. Where are we? ------------------------------------------------
        if ($env:OS -ne 'Windows_NT') { Exit-Install 'This installer is for Windows. On macOS or Linux, see https://bristlenose.app/docs/install.html' }
        if ($PSVersionTable.PSVersion.Major -lt 5) { Exit-Install 'This installer needs PowerShell 5.1 or later, which every supported Windows has. Update Windows, then run it again.' }
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

        Write-Host 'Installing Bristlenose for this Windows user (no administrator rights needed).'
        Sync-SessionPath  # a window opened before an earlier run still has the old PATH

        # ----- 1. uv -----------------------------------------------------------
        Write-Step 'uv (installs Bristlenose and the Python it runs on)'
        if (Test-Command 'uv') {
            Write-Done "Already installed: $(Get-CommandDir 'uv')"
        } else {
            $block = Get-PolicyBlock
            if ($block) {
                Write-Caution "Your organisation's PowerShell policy ($block) stops uv's installer from running."
                if ((Test-Winget) -and (Install-WingetPackage 'astral-sh.uv')) {
                    Sync-SessionPath
                } else {
                    Exit-Install "Your organisation's PowerShell policy ($block) stops uv's installer, and winget could not install uv either. Ask IT to install uv (https://docs.astral.sh/uv/), then run this again."
                }
            } else {
                # Astral's installer, in a child PowerShell. It refuses to run under
                # the Restricted policy Windows 11 ships with, and Bypass for that one
                # process is what Astral's own instructions use. Nothing is changed
                # for any other process.
                $shell = Join-Path $PSHOME 'powershell.exe'
                if (-not (Test-Path -LiteralPath $shell)) { $shell = Join-Path $PSHOME 'pwsh.exe' }
                & $shell -NoProfile -ExecutionPolicy Bypass -Command "irm $UvInstallerUrl | iex"
                if ($LASTEXITCODE -ne 0) {
                    Exit-Install "uv's installer did not finish (exit code $LASTEXITCODE; its message is above). If it could not download, a company proxy or firewall is the likely cause."
                }
                Sync-SessionPath
            }
            if (-not (Test-Command 'uv')) {
                Exit-Install 'uv was installed, but this window still cannot find it. Open a new terminal and run the same command again.'
            }
        }
        $uvVersion = & uv --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Exit-Install "uv is installed at $(Get-CommandDir 'uv') but Windows would not run it. On a work computer this is usually an application-control policy: ask IT to allow uv."
        }
        Write-Done "$uvVersion"

        # ----- 2. FFmpeg -------------------------------------------------------
        Write-Step 'FFmpeg (reads audio and video)'
        $ffmpegSource = (Get-Setting 'BRISTLENOSE_INSTALL_FFMPEG' 'auto').ToLowerInvariant()
        if ($ffmpegSource -notin 'auto', 'winget', 'zip') { Exit-Install "BRISTLENOSE_INSTALL_FFMPEG must be auto, winget or zip, not '$ffmpegSource'." }

        if ((Test-Command 'ffmpeg') -and (Test-Command 'ffprobe') -and $ffmpegSource -eq 'auto') {
            Write-Done "Already installed: $(Get-CommandDir 'ffmpeg')"
        } else {
            $haveFfmpeg = $false
            if ($ffmpegSource -ne 'zip') {
                if (Test-Winget) {
                    Write-Note 'Installing with winget (Gyan.FFmpeg, about 250 MB). winget source terms are accepted on your behalf.'
                    # Sync even on failure: an existing install exits non-zero
                    # ("no applicable upgrade") but is still the right FFmpeg.
                    $null = Install-WingetPackage 'Gyan.FFmpeg'
                    Sync-SessionPath
                    $haveFfmpeg = (Test-Command 'ffmpeg') -and (Test-Command 'ffprobe')
                    if (-not $haveFfmpeg) { Write-Caution 'winget did not give us a working FFmpeg; downloading it directly instead.' }
                } elseif ($ffmpegSource -eq 'winget') {
                    Exit-Install 'BRISTLENOSE_INSTALL_FFMPEG=winget, but winget is not available here.'
                } else {
                    Write-Note 'winget is not available here; downloading FFmpeg directly.'
                }
            }
            if (-not $haveFfmpeg) {
                if ($ffmpegSource -eq 'winget') { Exit-Install 'winget could not install FFmpeg (its message is above).' }
                $dest = Join-Path $env:LOCALAPPDATA 'Programs\bristlenose-ffmpeg'
                $zip = Join-Path ([IO.Path]::GetTempPath()) ('bristlenose-ffmpeg-' + [guid]::NewGuid().ToString() + '.zip')
                Write-Note "Downloading $FfmpegZipUrl (about 110 MB)"
                try {
                    Invoke-WebRequest -Uri $FfmpegZipUrl -OutFile $zip -UseBasicParsing -ErrorAction Stop
                } catch {
                    Exit-Install (Get-DownloadFailure 'FFmpeg' $FfmpegZipUrl $_)
                }
                try {
                    $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
                    if ($actual -ne $FfmpegZipSha256) {
                        Exit-Install "The FFmpeg download did not match its expected checksum (got $actual), so it was not installed. Run this again; if it happens twice, something between you and GitHub is changing downloads."
                    }
                    Add-Type -AssemblyName System.IO.Compression.FileSystem
                    $null = New-Item -ItemType Directory -Force -Path $dest
                    $archive = [IO.Compression.ZipFile]::OpenRead($zip)
                    try {
                        $wanted = 'ffmpeg.exe', 'ffprobe.exe', 'LICENSE'
                        foreach ($entry in $archive.Entries) {
                            if ($wanted -contains $entry.Name -and ($entry.FullName -match '/bin/' -or $entry.Name -eq 'LICENSE')) {
                                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $dest $entry.Name), $true)
                            }
                        }
                    } finally {
                        $archive.Dispose()
                    }
                } finally {
                    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
                }
                if (-not ((Test-Path (Join-Path $dest 'ffmpeg.exe')) -and (Test-Path (Join-Path $dest 'ffprobe.exe')))) {
                    Exit-Install "The FFmpeg download did not contain ffmpeg.exe and ffprobe.exe where expected, so nothing was installed to $dest."
                }
                Add-UserPath $dest
                Add-SessionPath $dest
            }
            if (-not ((Test-Command 'ffmpeg') -and (Test-Command 'ffprobe'))) {
                Exit-Install 'FFmpeg was installed, but this window cannot find ffmpeg and ffprobe. Open a new terminal and run the same command again.'
            }
            Write-Done "Installed: $(Get-CommandDir 'ffmpeg')"
        }

        # ----- 3. Bristlenose --------------------------------------------------
        Write-Step 'Bristlenose'
        $spec = Get-Setting 'BRISTLENOSE_INSTALL_SPEC' 'bristlenose'
        $tools = (& uv tool list 2>&1 | Out-String)
        if ($tools -match '(?m)^bristlenose v') {
            Write-Note 'Already installed with uv; upgrading.'
            & uv tool upgrade bristlenose
            if ($LASTEXITCODE -ne 0) { Exit-Install 'uv could not upgrade Bristlenose (its message is above).' }
        } else {
            $other = Get-Command bristlenose -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($other) {
                Exit-Install ("A copy of Bristlenose that uv did not install is already at $($other.Source). " +
                    'Remove it first (pipx uninstall bristlenose, or pip uninstall bristlenose), then run this again.')
            }
            Write-Note "Installing with Python $PythonVersion. uv downloads it for Bristlenose alone; any other Python stays as it is. This takes a few minutes the first time."
            & uv tool install --python $PythonVersion $spec
            if ($LASTEXITCODE -ne 0) { Exit-Install 'uv could not install Bristlenose (its message is above).' }
        }
        $installed = $true
        # From here on, Exit-Install messages finish the sentence
        # "Bristlenose is installed, but ...", so they start in lower case.

        # ----- 4. PATH, now and for new windows --------------------------------
        $toolBin = (& uv tool dir --bin 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $toolBin) { Exit-Install 'uv would not say where it is. Run uv tool dir --bin to see why.' }
        # Quietly: its own advice ("Restart your shell") is wrong once we have
        # updated this window's PATH ourselves.
        $null = & uv tool update-shell 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Caution "Bristlenose works in this window, but could not be added to PATH for new ones. Run: uv tool update-shell"
        }
        Sync-SessionPath
        Add-SessionPath $toolBin
        $found = Get-Command bristlenose -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $found) { Exit-Install "this window cannot find it in $toolBin. Open a new terminal and run bristlenose doctor." }
        if ((Split-Path -Parent $found.Source).TrimEnd('\') -ne $toolBin.TrimEnd('\')) {
            Write-Caution "Another bristlenose comes first on PATH: $($found.Source). The one just installed is in $toolBin."
        }

        # ----- 5. Check --------------------------------------------------------
        Write-Step 'Checking the installation (bristlenose doctor)'
        & $found.Source doctor
        if ($LASTEXITCODE -ne 0) { Exit-Install "bristlenose doctor did not run (exit code $LASTEXITCODE; its message is above). Open a new terminal and run bristlenose doctor to check it." }

        Write-Host ''
        Write-Host 'Bristlenose is installed.' -ForegroundColor Green
        Write-Host 'If you have not connected it to an AI provider yet, that is next:'
        Write-Host ''
        Write-Host '    bristlenose configure claude' -ForegroundColor Cyan
        Write-Host ''
        Write-Host '(or chatgpt, gemini, azure, local). If a new terminal says bristlenose is not found, sign out and back in.'
    } catch {
        $message = $_.Exception.Message
        $known = $message.StartsWith('BRISTLENOSE-INSTALL: ')
        if ($known) { $message = $message.Substring(21) }
        $where = "(line $($_.InvocationInfo.ScriptLineNumber))"
        Write-Host ''
        if ($installed) {
            if (-not $known) { $message = "something unexpected went wrong after that: $message $where" }
            Write-Host "Bristlenose is installed, but $message" -ForegroundColor Yellow
        } else {
            if (-not $known) { $message = "Something unexpected went wrong: $message $where" }
            Write-Host "Bristlenose was not installed. $message" -ForegroundColor Red
            Write-Host 'The manual steps are at https://bristlenose.app/docs/install.html'
        }
        # Run as a file (CI, or powershell -File), report failure to the caller.
        # Run through `irm | iex`, `exit` would close the user's terminal, so don't.
        if ($PSCommandPath) { exit 1 }
    }
}
