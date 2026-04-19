; Inno Setup script for ShotTrainer.
;
; Build with:
;   iscc packaging\shottrainer.iss
;
; Inputs (relative to the repo root):
;   dist\ShotTrainer\          PyInstaller's one-folder build
;   src\shottrainer\ui\assets\icon.ico
;
; Output:
;   dist\ShotTrainer-Setup.exe

#define MyAppName "ShotTrainer"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "dsgnr"
#define MyAppURL "https://github.com/dsgnr/ShotTrainer"
#define MyAppExeName "ShotTrainer.exe"

[Setup]
AppId={{2E6E1B53-7AAE-4F02-9F73-2C29E73D7C7B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENCE
OutputDir=..\dist
OutputBaseFilename=ShotTrainer-Setup
SetupIconFile=..\src\shottrainer\ui\assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\ShotTrainer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
