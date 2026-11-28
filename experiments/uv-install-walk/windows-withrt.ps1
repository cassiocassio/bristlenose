# Clean Windows, this checkout: the no-admin runtime route through the real CLI.
$W = "$env:USERPROFILE\bnwalk"
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
$py = Join-Path ((uv tool dir) | Out-String).Trim() 'bristlenose\Scripts\python.exe'
"== reinstall this checkout with the voice extra and msvc-runtime (no admin)"
uv tool install --force "bristlenose[voice] @ $W\kit\bristlenose-0.49.0-py3-none-any.whl" --with msvc-runtime --python 3.13 2>&1 | Select-Object -Last 2
"== doctor"
bristlenose doctor 2>&1 | Select-String -Pattern 'Transcription|Visual C|Voice|PII' | ForEach-Object { "  $_" }
"== transcribe"
bristlenose transcribe "$W\kit\project" -w tiny 2>&1 | Select-String -Pattern 'Transcribed|x |Done' | ForEach-Object { "  $_" }
"== probe"
& $py "$W\kit\probe.py" "$W\kit\project" pii
"== voice engine"
& $py -c "import bristlenose, kaldi_native_fbank; print('voice engine loads')" 2>&1 | Select-Object -Last 1
