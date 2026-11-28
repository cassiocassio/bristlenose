# After the one-liner, as the signed-in test user: what a new terminal would get.
$W = "$env:USERPROFILE\bnwalk"
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
function Step([string]$t, [scriptblock]$sb) {
  "== STEP: $t"
  $global:LASTEXITCODE = 0
  try { & $sb 2>&1 | ForEach-Object { "$_" } } catch { "EXCEPTION: $_" }
  "== EXIT: $LASTEXITCODE"
}
$py = Join-Path ((uv tool dir) | Out-String).Trim() 'bristlenose\Scripts\python.exe'
Step 'machine' { (Get-CimInstance Win32_OperatingSystem).Caption; (Get-CimInstance Win32_Processor).Name }
Step 'bristlenose --version' { bristlenose --version }
Step 'tool python' { & $py -c "import sys, sysconfig; print(sysconfig.get_platform(), sys.version)" }
Step 'bristlenose doctor' { bristlenose doctor }
Step 'channel and hint' { & $py -c "from bristlenose.utils.install_channel import install_channel as c, add_extra_command as a; print(c(), '|', a('voice'))" }
Step 'transcribe' { bristlenose transcribe "$W\kit\project" -w tiny 2>&1 | Select-Object -Last 14 }
Step 'probe' { & $py "$W\kit\probe.py" "$W\kit\project" pii }
Step 'voice hint, run as printed' { $cmd = & $py -c "from bristlenose.utils.install_channel import add_extra_command as a; print(a('voice'))"; $cmd; Invoke-Expression $cmd 2>&1 | Select-Object -Last 1; & $py -c "import sys, bristlenose, kaldi_native_fbank; print('voice on', sys.version.split()[0])" }
"== DONE"
