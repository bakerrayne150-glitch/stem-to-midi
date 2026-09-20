; Inno Setup script — builds the Stem2MIDI installer.
; Install Inno Setup 6 (https://jrsoftware.org/isinfo.php), open this file,
; press Compile. Output: Stem2MIDI-Setup-0.1.0.exe next to this script.
; Run it AFTER build.bat has produced dist\Stem2MIDI\.

#define MyAppName "Stem-to-MIDI Workspace"
#define MyAppVersion "0.1.0"
#define MyAppExeName "Stem2MIDI.exe"

[Setup]
AppId={{B4E2F1A0-7C3D-4E8F-9A1B-2C3D4E5F6071}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Stem2MIDI
DefaultGroupName=Stem2MIDI
OutputBaseFilename=Stem2MIDI-Setup-{#MyAppVersion}
OutputDir=..\..\dist
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "..\..\dist\Stem2MIDI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
