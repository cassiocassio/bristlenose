# Clean Windows: is the Visual C++ runtime what the engines lack? Diagnose,
# install Microsoft's redistributable, then transcribe and probe again.
$W = "$env:USERPROFILE\bnwalk"
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
$py = Join-Path ((uv tool dir) | Out-String).Trim() 'bristlenose\Scripts\python.exe'
$base = & $py -c "import sys; print(sys.base_prefix)"
"== runtime DLLs in System32:"
'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll' | ForEach-Object { "  $_ : " + (Test-Path "$env:SystemRoot\System32\$_") }
"== runtime DLLs beside uv's Python ($base):"
Get-ChildItem $base -Filter '*140*.dll' | ForEach-Object { "  " + $_.Name }
"== before: import the engines"
& $py -c "import ctranslate2; print('ctranslate2 ok')" 2>&1 | Select-Object -Last 1
& $py -c "import thinc.backends.numpy_ops; print('thinc ok')" 2>&1 | Select-Object -Last 1
"== install the Microsoft Visual C++ Redistributable (x64)"
Invoke-WebRequest -UseBasicParsing -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile "$W\vc_redist.x64.exe"
$p = Start-Process "$W\vc_redist.x64.exe" -ArgumentList '/install', '/quiet', '/norestart' -Wait -PassThru
"vc_redist exit: " + $p.ExitCode
'msvcp140.dll', 'vcruntime140_1.dll' | ForEach-Object { "  $_ : " + (Test-Path "$env:SystemRoot\System32\$_") }
"== after: import the engines"
& $py -c "import ctranslate2; print('ctranslate2 ok')" 2>&1 | Select-Object -Last 1
& $py -c "import thinc.backends.numpy_ops; print('thinc ok')" 2>&1 | Select-Object -Last 1
& powershell -NoProfile -ExecutionPolicy Bypass -File "$W\post.ps1"
