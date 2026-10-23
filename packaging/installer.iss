; Instalador de Kreix (Inno Setup 6). Lo lanza packaging/build.ps1 con /DAppVersion=x.y.z; compilado a mano:
;   ISCC.exe /DAppVersion=0.6.1 packaging\installer.iss
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

spanish.ConfirmUninstall=¿Quieres quitar %1 de este equipo?%n%nTus datos no se borran: seguirán guardados, cifrados, por si lo vuelves a instalar.
catalan.ConfirmUninstall=Vols treure %1 d'aquest equip?%n%nLes teves dades no s'esborren: continuaran desades, xifrades, per si el tornes a instal·lar.
english.ConfirmUninstall=Do you want to remove %1 from this computer?%n%nYour data is not deleted: it stays saved, encrypted, in case you install it again.
spanish.UninstalledAll=Kreix se ha quitado de este equipo. Gracias por usarlo.
catalan.UninstalledAll=Kreix s'ha tret d'aquest equip. Gràcies per fer-lo servir.
english.UninstalledAll=Kreix has been removed from this computer. Thank you for using it.
spanish.UninstallStatusLabel=Quitando Kreix de tu equipo…
catalan.UninstallStatusLabel=Traient Kreix del teu equip…
english.UninstallStatusLabel=Removing Kreix from your computer…

[CustomMessages]
spanish.DeleteDataPrompt=¿Quieres borrar también tus datos de Kreix (movimientos, cuentas y las copias de seguridad guardadas junto a ellos)?%n%nNo se puede deshacer. Si no estás seguro, elige No: tus datos seguirán ahí si vuelves a instalar Kreix.
catalan.DeleteDataPrompt=Vols esborrar també les teves dades de Kreix (moviments, comptes i les còpies de seguretat desades al costat)?%n%nNo es pot desfer. Si no n'estàs segur, tria No: les teves dades continuaran allà si tornes a instal·lar Kreix.
english.DeleteDataPrompt=Do you also want to delete your Kreix data (transactions, accounts and the backups saved next to them)?%n%nThis cannot be undone. If you are not sure, choose No: your data will still be there if you install Kreix again.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Kreix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Kreix"; Filename: "{app}\Kreix.exe"
Name: "{autodesktop}\Kreix"; Filename: "{app}\Kreix.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Kreix.exe"; Description: "{cm:LaunchProgram,Kreix}"; Flags: nowait postinstall skipifsilent

[Code]
// El idioma elegido en el instalador pasa a la aplicacion: Kreix lo usa en la pantalla de contrasena, que sale antes de
// poder leer los datos cifrados. Solo se escribe si aun no hay uno (un idioma elegido dentro de Kreix manda).
function ChosenLanguage(): String;
begin
  if ActiveLanguage = 'catalan' then
    Result := 'ca'
  else if ActiveLanguage = 'english' then
    Result := 'en'
  else
    Result := 'es';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Folder, HintFile: String;
begin
  if CurStep = ssPostInstall then
  begin
    Folder := ExpandConstant('{userappdata}\Kreix');
    HintFile := Folder + '\idioma.txt';
    if not FileExists(HintFile) then
    begin
      ForceDirectories(Folder);
      SaveStringToFile(HintFile, ChosenLanguage() + #13#10, False);
    end;
  end;
end;

// Al desinstalar se ofrece, sin marcar por defecto, borrar tambien los datos del usuario. Un desinstalado silencioso nunca los toca.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Folder: String;
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent()) then
  begin
    Folder := ExpandConstant('{userappdata}\Kreix');
    if DirExists(Folder) then
      if MsgBox(CustomMessage('DeleteDataPrompt'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Folder, True, True, True);
  end;
end;
