[Setup]
AppId=YouTube Player and Downloader
AppName=YouTube Player and Downloader
AppVersion=1.1
AppPublisher=Blind tech nexus team
DefaultDirName={autopf}\YouTube Player and Downloader
DefaultGroupName=YouTube Player and Downloader
PrivilegesRequired=admin
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
OutputDir=output
OutputBaseFilename=YouTube_Player_And_Downloader_Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\YouTube Player and Downloader\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"

[Icons]
Name: "{group}\YouTube Player and Downloader"; Filename: "{app}\YouTube Player and Downloader.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall YouTube player and downloader"; Filename: "{uninstallexe}"
Name: "{autodesktop}\YouTube Player and Downloader"; Filename: "{app}\YouTube Player and Downloader.exe"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Registry]
Root: HKLM; Subkey: "Software\YouTube Player and Downloader"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\YouTube Player and Downloader"; ValueType: string; ValueName: "Version"; ValueData: "1.1"; Flags: uninsdeletekey

[Code]
function InitializeSetup(): Boolean;
var
  OldUninstallString: String;
  ResultCode: Integer;
begin
  Result := True;
  if RegQueryStringValue(HKLM32, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTube Player and Downloader_is1', 'UninstallString', OldUninstallString) then
  begin
    if OldUninstallString <> '' then
    begin
      OldUninstallString := RemoveQuotes(OldUninstallString);
      Exec(OldUninstallString, '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end
  else if RegQueryStringValue(HKLM64, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTube Player and Downloader_is1', 'UninstallString', OldUninstallString) then
  begin
    if OldUninstallString <> '' then
    begin
      OldUninstallString := RemoveQuotes(OldUninstallString);
      Exec(OldUninstallString, '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;
