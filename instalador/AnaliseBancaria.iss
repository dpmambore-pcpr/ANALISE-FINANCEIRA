; Instalador do Windows (Inno Setup 6). Gerado pelo fluxo .github/workflows/instalador.yml.
; Instala em %LOCALAPPDATA%\AnaliseBancariaLocal (sem precisar de administrador), de modo que o
; programa consiga se atualizar sozinho pela tela ("Atualizar agora"). Os dados ficam em
; <pasta>\dados e NUNCA são apagados nem pela atualização, nem pela desinstalação.
#ifndef Versao
  #define Versao "0.0.0"
#endif

[Setup]
AppId={{8D3F5C1A-6B2E-4F7A-9C10-2A5E7B9D4C31}
AppName=Analise Bancaria Local
AppVersion={#Versao}
AppPublisher=Delegacia de Policia de Mambore
DefaultDirName={localappdata}\AnaliseBancariaLocal
DefaultGroupName=Analise Bancaria Local
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AnaliseBancariaLocal-Instalador-{#Versao}
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
UninstallDisplayName=Analise Bancaria Local
WizardStyle=modern
CloseApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktop"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\*"; DestDir: "{app}"; Excludes: ".git\*,.github\*,dados\*,backup_versoes\*,legado\*,dist\*,instalador\*,diagnostico_windows.txt,configuracao_local.json,__pycache__\*"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Analise Bancaria Local"; Filename: "{app}\INICIAR_WINDOWS.bat"; WorkingDir: "{app}"
Name: "{group}\Atualizar (pelo programa: botao Verificar atualizacao)"; Filename: "{app}\ATUALIZAR_WINDOWS.bat"; WorkingDir: "{app}"
Name: "{group}\Verificar instalacao"; Filename: "{app}\VERIFICAR_WINDOWS.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Analise Bancaria Local"; Filename: "{app}\INICIAR_WINDOWS.bat"; WorkingDir: "{app}"; Tasks: desktop

[Run]
Filename: "{app}\INICIAR_WINDOWS.bat"; Description: "Abrir a Analise Bancaria Local agora"; WorkingDir: "{app}"; Flags: postinstall skipifsilent nowait

[UninstallDelete]
Type: filesandordirs; Name: "{app}\financeira"
Type: filesandordirs; Name: "{app}\vendor"
