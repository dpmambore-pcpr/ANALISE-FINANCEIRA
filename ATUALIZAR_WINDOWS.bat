@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Atualizar Analise Bancaria Local
echo Atualiza somente o codigo do programa a partir do GitHub.
echo As pastas dados, runtime_windows, ollama e modelos_ollama NAO sao alteradas.
echo.
set "PY="
if exist "runtime_windows\python.exe" set "PY=runtime_windows\python.exe"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY set "PY=python"
%PY% atualizar.py --testar %*
pause
