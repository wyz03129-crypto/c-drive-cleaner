#define AppName "PDF 套料单打印优化助手"
#define AppVersion "1.0.0"
[Setup]
AppId={{A74C7B80-6C5E-4D2D-9D4E-8F45A69B70D3}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\PDFPrintOptimizer
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=PDF_Print_Optimizer_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
[Files]
Source: "dist\PDF_Print_Optimizer.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\PDF_Print_Optimizer.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\PDF_Print_Optimizer.exe"
[Run]
Filename: "{app}\PDF_Print_Optimizer.exe"; Description: "启动 PDF 打印优化助手"; Flags: nowait postinstall skipifsilent
