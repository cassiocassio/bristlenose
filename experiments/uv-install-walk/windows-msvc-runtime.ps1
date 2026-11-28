# Clean Windows: does an app-local runtime (PyPI's msvc-runtime) let the
# engines load without administrator rights? Then transcribe and probe.
$W = "$env:USERPROFILE\bnwalk"
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
$py = Join-Path ((uv tool dir) | Out-String).Trim() 'bristlenose\Scripts\python.exe'
"== before"
& $py -c "import ctranslate2; print('ctranslate2 ok')" 2>&1 | Select-Object -Last 1
"== uv pip install msvc-runtime into the tool env (no admin)"
uv pip install --python $py msvc-runtime 2>&1 | Select-Object -Last 3
$prefix = & $py -c "import sys; print(sys.prefix)"
$base = & $py -c "import sys; print(sys.base_prefix)"
"DLLs in the tool env:"; Get-ChildItem $prefix -Recurse -Filter 'msvcp140*.dll' -ErrorAction SilentlyContinue | ForEach-Object { "  " + $_.FullName }
"== after (env only)"
& $py -c "import ctranslate2; print('ctranslate2 ok')" 2>&1 | Select-Object -Last 1
& $py -c "import thinc.backends.numpy_ops; print('thinc ok')" 2>&1 | Select-Object -Last 1
"== copy the same DLLs beside uv's base Python ($base), the folder Windows searches for python.exe"
Get-ChildItem $prefix -Filter '*.dll' | Where-Object { $_.Name -match '140' } | Copy-Item -Destination $base -Force
& $py -c "import ctranslate2; print('ctranslate2 ok')" 2>&1 | Select-Object -Last 1
& $py -c "import thinc.backends.numpy_ops; print('thinc ok')" 2>&1 | Select-Object -Last 1
& powershell -NoProfile -ExecutionPolicy Bypass -File "$W\post.ps1"
