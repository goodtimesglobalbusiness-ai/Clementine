@echo off
title Clementine Runtime
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File scripts\rc.ps1 start
pause
