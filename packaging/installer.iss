; Instalador de Kreix (Inno Setup 6). Lo lanza packaging/build.ps1 con /DAppVersion=x.y.z; compilado a mano:
;   ISCC.exe /DAppVersion=0.3.0 packaging\installer.iss
; Se instala solo para el usuario (no pide permisos de administrador), crea el acceso directo en el menu Inicio y,
; si se quiere, en el escritorio. Al desinstalar NO se borran los datos (%APPDATA%\Kreix): son del usuario.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6D1F5C0B-8E2A-4C57-9A7E-3B1D2F4A9C11}
AppName=Kreix
AppVersion={#AppVersion}
AppVerName=Kreix {#AppVersion}
AppPublisher=Kreix
DefaultDirName={autopf}\Kreix
DefaultGroupName=Kreix
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Kreix-Setup-{#AppVersion}
SetupIconFile=..\logo-mejorado\favicon.ico
UninstallDisplayIcon={app}\Kreix.exe
UninstallDisplayName=Kreix
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Kreix

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "catalan"; MessagesFile: "compiler:Languages\Catalan.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Kreix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Kreix"; Filename: "{app}\Kreix.exe"
Name: "{autodesktop}\Kreix"; Filename: "{app}\Kreix.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Kreix.exe"; Description: "{cm:LaunchProgram,Kreix}"; Flags: nowait postinstall skipifsilent
