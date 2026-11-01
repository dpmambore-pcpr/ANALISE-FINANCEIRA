@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ollama local (somente 127.0.0.1, sem nuvem)
rem Inicia o Ollama somente em 127.0.0.1, com recursos de nuvem desativados e modelos dentro da pasta.
rem Feche antes qualquer Ollama ja aberto (icone na bandeja), senao ele continuara com a configuracao antiga.
set "OLLAMA_HOST=127.0.0.1:11434"
set "OLLAMA_NO_CLOUD=1"
set "OLLAMA_MODELS=%~dp0modelos_ollama"
if not exist "modelos_ollama" mkdir "modelos_ollama"
set "OLL="
if exist "ollama\ollama.exe" set "OLL=ollama\ollama.exe"
if not defined OLL (
  where ollama >nul 2>nul && set "OLL=ollama"
)
if not defined OLL (
  echo Ollama nao encontrado. Veja docs\IA_LOCAL.md.
  pause
  exit /b 1
)
echo Mantenha esta janela aberta enquanto usar a IA. Modelos em: %OLLAMA_MODELS%
"%OLL%" serve
pause
