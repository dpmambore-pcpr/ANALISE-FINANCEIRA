@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Analise Bancaria Local
set "PY="
if exist "runtime_windows\python.exe" set "PY=runtime_windows\python.exe"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python nao encontrado. Coloque o Python portatil em runtime_windows ^(veja runtime_windows\LEIA.txt^).
  pause
  exit /b 1
)
%PY% iniciar.py %*
if errorlevel 1 (
  echo.
  echo O programa encerrou com erro. Execute VERIFICAR_WINDOWS.bat e envie o resultado.
  pause
)
