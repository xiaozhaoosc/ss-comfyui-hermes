; Inno Setup 脚本 - 换脸客户端安装包
; 用法:
;   ISCC.exe /DVARIANT=cpu build\installer.iss   -> 生成 FaceswapApp_cpu_setup.exe
;   ISCC.exe /DVARIANT=gpu build\installer.iss   -> 生成 FaceswapApp_gpu_setup.exe
;
; 编译前需先用 PyInstaller 生成 dist/FaceswapApp_{variant}/ 目录

#ifndef VARIANT
  #error 必须通过 /DVARIANT=cpu 或 /DVARIANT=gpu 指定版本
#endif

#if VARIANT == "gpu"
  #define AppName "视频换脸客户端 (GPU 版)"
  #define ExeName "FaceswapApp_gpu.exe"
  #define SrcDir "dist\FaceswapApp_gpu"
#else
  #define AppName "视频换脸客户端 (CPU 版)"
  #define ExeName "FaceswapApp_cpu.exe"
  #define SrcDir "dist\FaceswapApp_cpu"
#endif

[Setup]
AppName={#AppName}
AppVersion=1.0.0
AppPublisher=FaceswapApp
DefaultDirName={pf}\FaceswapApp_{#VARIANT}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=FaceswapApp_{#VARIANT}_setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#ExeName}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"

[Files]
; 主程序目录（PyInstaller 产物）
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 模型文件（如存在则打包，约 800MB，可选）
Source: "..\..\models\insightface\inswapper_128.onnx"; DestDir: "{app}\models\insightface"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\..\..\models\insightface\inswapper_128.onnx'))
Source: "..\..\models\facerestore_models\GFPGANv1.4.pth"; DestDir: "{app}\models\facerestore_models"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\..\..\models\facerestore_models\GFPGANv1.4.pth'))
; ffmpeg/ffprobe（如已下载到 build/bin/ 则打包）
Source: "bin\ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\bin\ffmpeg.exe'))
Source: "bin\ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\bin\ffprobe.exe'))

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "立即启动"; Flags: nowait postinstall skipifsilent
