@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
cd /d "%~dp0"
title Verificar Analise Bancaria Local
set "PY="
if exist "%~dp0runtime_windows\python.exe" set PY="%~dp0runtime_windows\python.exe"
if not defined PY call :procurar_python
if not defined PY goto sem_python
%PY% -X utf8 -u "%~dp0verificar.py" > "%~dp0diagnostico_windows.txt" 2>&1
type "%~dp0diagnostico_windows.txt"
echo.
echo O resultado tambem foi salvo em diagnostico_windows.txt nesta pasta.
pause
exit /b 0

:procurar_python
for %%C in ("py -3" "python") do (
  if not defined PY (
    %%~C -c "import sqlite3,sys;sys.exit(0 if sys.version_info[:2]>=(3,9) else 1)" >nul 2>nul && set "PY=%%~C"
  )
)
exit /b 0

:sem_python
echo.
echo Nao foi encontrado um Python que funcione.
echo O pacote correto traz o Python portatil na pasta runtime_windows (arquivo runtime_windows\python.exe).
echo Baixe novamente o repositorio inteiro: GitHub ^> Code ^> Download ZIP, clique com o botao direito
echo no ZIP, escolha "Extrair tudo" e abra esta pasta extraida (nao abra o .bat dentro do ZIP).
echo Nao e necessario instalar Python nem abrir a Microsoft Store.
echo.
pause
exit /b 1
