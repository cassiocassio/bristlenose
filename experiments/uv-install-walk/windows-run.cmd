@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File C:\bnwalk\%1.ps1 > C:\bnwalk\%1.out.txt 2>&1
echo done > C:\bnwalk\%1.done
