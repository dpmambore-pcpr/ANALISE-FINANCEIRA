@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Verificar Analise Bancaria Local
set "PY="
if exist "runtime_windows\python.exe" set "PY=runtime_windows\python.exe"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY set "PY=python"
%PY% verificar.py
pause
