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
WizardStyle=modern dark
DisableWelcomePage=no
WizardImageFile=art\panel-100.bmp,art\panel-150.bmp,art\panel-200.bmp
WizardSmallImageFile=art\icono-100.bmp,art\icono-150.bmp,art\icono-200.bmp
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

[Messages]
spanish.WelcomeLabel2=Esto instalará [name/ver] en tu equipo.%n%nKreix guarda tus datos cifrados, solo en este ordenador: no usa internet ni envía nada a ningún sitio. Si ya lo tienes instalado, se actualiza sin tocar tus datos.
catalan.WelcomeLabel2=Això instal·larà [name/ver] al teu equip.%n%nKreix desa les teves dades xifrades, només en aquest ordinador: no usa internet ni envia res enlloc. Si ja el tens instal·lat, s'actualitza sense tocar les teves dades.
english.WelcomeLabel2=This will install [name/ver] on your computer.%n%nKreix keeps your data encrypted, only on this computer: it does not use the internet or send anything anywhere. If you already have it installed, it is updated without touching your data.
spanish.FinishedLabel=Kreix ya está instalado. Puedes abrirlo desde el menú Inicio o desde el escritorio.
catalan.FinishedLabel=Kreix ja està instal·lat. El pots obrir des del menú Inici o des de l'escriptori.
english.FinishedLabel=Kreix is now installed. You can open it from the Start menu or from the desktop.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Kreix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Kreix"; Filename: "{app}\Kreix.exe"
Name: "{autodesktop}\Kreix"; Filename: "{app}\Kreix.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Kreix.exe"; Description: "{cm:LaunchProgram,Kreix}"; Flags: nowait postinstall skipifsilent
