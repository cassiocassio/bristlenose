# Logged in on a set-back date (the test password has expired on today's), wait
# in this same session until Windows' time service has put the clock right, so
# today's TLS certificates verify. BN_REAL_EPOCH is the host's time at launch.
$real = [DateTimeOffset]::FromUnixTimeSeconds([long]$env:BN_REAL_EPOCH).UtcDateTime
$t0 = Get-Date
while ((($real - [DateTime]::UtcNow).TotalHours -gt 1) -and (((Get-Date) - $t0).TotalMinutes -lt 20)) {
    w32tm /resync /nowait 2>$null | Out-Null
    Start-Sleep -Seconds 15
}
'== guest clock now ' + [DateTime]::UtcNow.ToString('u') + ' after ' + [int]((Get-Date) - $t0).TotalSeconds + ' s'
