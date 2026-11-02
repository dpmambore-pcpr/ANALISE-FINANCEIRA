@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Instalar Analise Bancaria Local
set "DEST=%LOCALAPPDATA%\AnaliseBancariaLocal"
if not exist "%~dp0iniciar.py" (
  echo Extraia TODO o ZIP antes ^(botao direito ^> Extrair tudo^) e execute este arquivo de dentro da pasta extraida.
  pause
  exit /b 1
)
echo Instalando em: %DEST%
echo Seus casos ^(pasta dados^) nunca sao apagados nem sobrescritos.
echo.
robocopy "%~dp0." "%DEST%" /E /XD .git dados backup_versoes legado dist /XF diagnostico_windows.txt configuracao_local.json /NFL /NDL /NJH /NJS /NP
if errorlevel 8 (
  echo.
  echo Nao foi possivel copiar os arquivos. Feche o programa se estiver aberto e tente de novo.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\Analise Bancaria Local.lnk'); $s.TargetPath='%DEST%\INICIAR_WINDOWS.bat'; $s.WorkingDirectory='%DEST%'; $s.Description='Analise Bancaria Local'; $s.Save()"
echo.
echo Instalacao concluida. Use o atalho "Analise Bancaria Local" na area de trabalho.
echo Quando houver versao nova, o programa avisa no topo da tela e o botao "Atualizar agora" faz tudo.
echo Voce ja pode apagar a pasta extraida do ZIP.
pause
exit /b 0
