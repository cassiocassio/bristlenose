#!/bin/bash
# Usage: font-list.sh [vm]
# Boot the VM headless, list the monospace fonts Windows ships, power off, restore "clean".
set -u
VM=${1:-win11-26h2}; VBM=/usr/local/bin/VBoxManage; PW=$HOME/bn-wintest/guest-password
ts() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }
[ "$($VBM showvminfo $VM --machinereadable | sed -n 's/^VMState="\(.*\)"/\1/p')" = poweroff ] || { ts "VM not powered off; refusing"; exit 2; }
ts "starting $VM"; $VBM startvm $VM --type headless || exit 3
i=0; until $VBM guestcontrol $VM run --username bn --passwordfile $PW --exe 'C:\Windows\System32\cmd.exe' -- /d /c ver >/dev/null 2>&1; do
  [ $i -ge 1800 ] && { ts "guest never answered"; break; }; sleep 20; i=$((i+20)); done
ts "guest up after ${i}s"
PS='$v = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"; "Windows: " + $v.ProductName + " " + $v.DisplayVersion + " build " + $v.CurrentBuild;
"--- font files (C:\Windows\Fonts) ---"; Get-ChildItem C:\Windows\Fonts | Where-Object { $_.Name -match "cascadia|consol|cour|lucon|mono" } | ForEach-Object { $_.Name + "  " + $_.Length };
"--- registered fonts (HKLM) ---"; (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts").PSObject.Properties | Where-Object { $_.Name -match "Cascadia|Consolas|Courier|Lucida Console|Mono" } | ForEach-Object { $_.Name + " = " + $_.Value };
"--- per-user fonts (HKCU) ---"; $u = Get-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" -ErrorAction SilentlyContinue; if ($u) { $u.PSObject.Properties | Where-Object { $_.Name -match "Cascadia" } | ForEach-Object { $_.Name + " = " + $_.Value } } else { "(none)" };
"--- installed families (GDI+) ---"; Add-Type -AssemblyName System.Drawing; (New-Object System.Drawing.Text.InstalledFontCollection).Families | Where-Object { $_.Name -match "Cascadia|Consolas|Courier|Lucida Console|Mono" } | ForEach-Object { $_.Name };
"--- Windows Terminal package ---"; Get-AppxPackage -Name Microsoft.WindowsTerminal* | ForEach-Object { $_.Name + " " + $_.Version }'
$VBM guestcontrol $VM run --username bn --passwordfile $PW --profile --timeout 300000 --wait-stdout --wait-stderr \
  --exe 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -- -NoProfile -NonInteractive -Command "$PS"
ts "powering off and restoring snapshot clean"
$VBM controlvm $VM poweroff; sleep 10; $VBM snapshot $VM restore clean
$VBM showvminfo $VM --machinereadable | grep -E '^VMState=|^CurrentSnapshotName'
ts done
