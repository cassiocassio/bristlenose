# Clean Windows, this checkout: what doctor says without the C++ runtime, and
# whether msvc-runtime in the tool env plus os.add_dll_directory is enough.
$W = "$env:USERPROFILE\bnwalk"
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
$py = Join-Path ((uv tool dir) | Out-String).Trim() 'bristlenose\Scripts\python.exe'
"== doctor on a clean Windows (this checkout)"
bristlenose doctor 2>&1 | Select-String -Pattern 'Transcription|Visual C|vc_redist|runtime' | ForEach-Object { "  $_" }
"== msvc-runtime into the tool env, then os.add_dll_directory(sys.prefix)"
uv pip install --python $py msvc-runtime 2>&1 | Select-Object -Last 1
& $py -c "import os, sys; os.add_dll_directory(sys.prefix); import ctranslate2, thinc.backends.numpy_ops; print('engines load with add_dll_directory')" 2>&1 | Select-Object -Last 1
& $py -c "import ctranslate2; print('engines load without it')" 2>&1 | Select-Object -Last 1
