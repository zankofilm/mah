#ifndef MyAppVersion
  #define MyAppVersion "7.6.20"
#endif
#define MyAppName "سامانه مدیریت محله‌محور جوانرود"
#define MyAppPublisher "فرمانداری شهرستان جوانرود"
#define MyAppExeName "JavanroodNeighborhoodManagement.exe"
#define MyAppFolder "JavanroodNeighborhoodManagement"

[Setup]
AppId={{E7C82E6B-48CC-4A42-A0BE-2DA440F5A700}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName}
VersionInfoProductName={#MyAppName}
DefaultDirName={localappdata}\Programs\{#MyAppFolder}
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=JavanroodNeighborhoodManagement_Setup_{#MyAppVersion}_Windows_x64
SetupIconFile=..\assets\javanrood_app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
DisableDirPage=auto
UsePreviousAppDir=yes
UsePreviousTasks=yes
CreateUninstallRegKey=yes
ChangesEnvironment=no
ChangesAssociations=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\JavanroodNeighborhoodManagement\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "ایجاد میانبر روی میزکار"; GroupDescription: "میانبرها:"; Flags: checkedonce
Name: "startmenuicon"; Description: "ایجاد میانبر در منوی Start"; GroupDescription: "میانبرها:"; Flags: checkedonce

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon
Name: "{autoprograms}\حذف {#MyAppName}"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "اجرای سامانه"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
function Pad2(Value: Integer): String;
begin
  if Value < 10 then
    Result := '0' + IntToStr(Value)
  else
    Result := IntToStr(Value);
end;

function TimeStamp: String;
var
  DT: TDateTime;
  Y, M, D, H, N, S, MS: Word;
begin
  DT := Now;
  DecodeDate(DT, Y, M, D);
  DecodeTime(DT, H, N, S, MS);
  Result := IntToStr(Y) + Pad2(M) + Pad2(D) + '_' + Pad2(H) + Pad2(N) + Pad2(S);
end;

function CopyDirectoryTree(const SourceDir, DestDir: String): Boolean;
var
  FindRec: TFindRec;
  SourcePath, DestPath: String;
begin
  Result := True;
  if not DirExists(SourceDir) then
    exit;
  ForceDirectories(DestDir);
  if FindFirst(AddBackslash(SourceDir) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          SourcePath := AddBackslash(SourceDir) + FindRec.Name;
          DestPath := AddBackslash(DestDir) + FindRec.Name;
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          begin
            if not CopyDirectoryTree(SourcePath, DestPath) then
              Result := False;
          end
          else if not FileCopy(SourcePath, DestPath, False) then
            Result := False;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function BackupExistingData(): Boolean;
var
  DataDir, BackupRoot, DbFile: String;
begin
  Result := True;
  DataDir := ExpandConstant('{localappdata}\{#MyAppFolder}');
  DbFile := AddBackslash(DataDir) + 'javanrood.db';
  if not FileExists(DbFile) then
    exit;

  BackupRoot := AddBackslash(DataDir) + 'preinstall_backups\before_' + '{#MyAppVersion}' + '_' + TimeStamp;
  ForceDirectories(BackupRoot);

  if not FileCopy(DbFile, AddBackslash(BackupRoot) + 'javanrood.db', False) then
    Result := False;
  if FileExists(DbFile + '-wal') then
    FileCopy(DbFile + '-wal', AddBackslash(BackupRoot) + 'javanrood.db-wal', False);
  if FileExists(DbFile + '-shm') then
    FileCopy(DbFile + '-shm', AddBackslash(BackupRoot) + 'javanrood.db-shm', False);

  if DirExists(AddBackslash(DataDir) + 'attachments') then
    if not CopyDirectoryTree(AddBackslash(DataDir) + 'attachments', AddBackslash(BackupRoot) + 'attachments') then
      Result := False;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not BackupExistingData() then
    Result := 'پشتیبان‌گیری خودکار از اطلاعات قبلی کامل نشد. نصب متوقف شد تا اطلاعات شما در معرض خطر قرار نگیرد.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    DataDir := ExpandConstant('{localappdata}\{#MyAppFolder}');
    ForceDirectories(DataDir);
    ForceDirectories(AddBackslash(DataDir) + 'attachments');
    ForceDirectories(AddBackslash(DataDir) + 'automatic_backups');
    ForceDirectories(AddBackslash(DataDir) + 'logs');
    ForceDirectories(AddBackslash(DataDir) + 'reports');
  end;
end;
