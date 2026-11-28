# Windows, INSTALL.md's uv route, isolated under C:\bnwalk (run as SYSTEM by utmctl).
# BN_PYTHON: the uv Python request; '3.13' as INSTALL.md says, or e.g.
# 'cpython-3.13-windows-x86_64-none' for x64 under Windows on Arm's emulation.
$B = 'C:\bnwalk'
$Req = if ($env:BN_PYTHON) { $env:BN_PYTHON } else { '3.13' }
function Step([string]$t, [scriptblock]$sb) {
  "== STEP: $t"
  $global:LASTEXITCODE = 0
  try { & $sb 2>&1 | ForEach-Object { "$_" } } catch { "EXCEPTION: $_" }
  "== EXIT: $LASTEXITCODE"
}
if (Test-Path "$B\kit") { Remove-Item -Recurse -Force "$B\kit" }
Expand-Archive -Force "$B\kit.zip" "$B\kit"
$env:UV_UNMANAGED_INSTALL = "$B\uvbin"
$env:UV_TOOL_DIR = "$B\tools"; $env:UV_TOOL_BIN_DIR = "$B\bin"; $env:UV_PYTHON_INSTALL_DIR = "$B\pythons"
$env:UV_CACHE_DIR = "$B\uvcache"; $env:XDG_CACHE_HOME = "$B\cache"; $env:HF_HOME = "$B\hf"
$ff = (Get-ChildItem -Recurse -Filter ffmpeg.exe -Path 'C:\Users\*\AppData\Local\Microsoft\WinGet\Packages' | Select-Object -First 1).DirectoryName
$env:Path = "$B\bin;$B\uvbin;$ff;" + $env:Path
$py = "$B\tools\bristlenose\Scripts\python.exe"
Step 'native arch' { (Get-CimInstance Win32_Processor).Architecture }
Step "ffmpeg from $ff" { ffmpeg -version | Select-Object -First 1 }
Step 'install uv (Astral, unmanaged)' { irm https://astral.sh/uv/install.ps1 | iex }
Step 'uv --version' { uv --version }
Step "uv tool install --python $Req bristlenose" { uv tool install --python $Req bristlenose 2>&1 | Select-Object -Last 6 }
Step 'python in the tool env' { & $py -c "import sys, platform; print(sys.version.split()[0], platform.machine())" }
Step 'bristlenose --version' { bristlenose --version }
Step 'bristlenose doctor' { bristlenose doctor }
Step 'released: python -m pip --version' { & $py -m pip --version }
Step 'released: spacy download' { & $py -m spacy download en_core_web_lg 2>&1 | Select-Object -Last 3 }
$whl = (Get-ChildItem "$B\kit\*.whl" | Select-Object -First 1).FullName
Step 'this checkout' { uv tool install --force $whl --python $Req 2>&1 | Select-Object -Last 3 }
Step 'channel and hint' { & $py -c "from bristlenose.utils.install_channel import install_channel as c, add_extra_command as a; print(c(), '|', a('voice'))" }
Step 'pii route' { & $py -c "from bristlenose.stages import s07_pii_removal as s; print('needs_user_cache', s.spacy_model_needs_user_cache())" }
Step 'transcribe' { bristlenose transcribe "$B\kit\project" -w tiny 2>&1 | Select-Object -Last 14 }
Step 'probe' { & $py "$B\kit\probe.py" "$B\kit\project" pii }
Step 'printed voice hint, run as printed' { $cmd = & $py -c "from bristlenose.utils.install_channel import add_extra_command as a; print(a('voice'))"; $cmd; Invoke-Expression $cmd 2>&1 | Select-Object -Last 2; & $py -c "import sys, platform, bristlenose, kaldi_native_fbank; print('voice on', sys.version.split()[0], platform.machine())" }
"== DONE"
