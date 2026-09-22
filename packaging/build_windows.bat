@echo off
setlocal
cd /d "%~dp0.."

python -m PyInstaller --noconfirm --clean ^
  --distpath dist\windows ^
  --workpath build\windows ^
  packaging\fh6parse.spec
if errorlevel 1 exit /b 1

if not exist dist\windows\fh6parse.exe (
  echo error: dist\windows\fh6parse.exe was not created
  exit /b 1
)

for /f "usebackq delims=" %%V in (`python -c "from fh6parse._version import dist_basename; print(dist_basename('windows-x64'))"`) do set STAMPED=%%V
for /f "usebackq delims=" %%V in (`python -c "from fh6parse._version import dist_basename; print(dist_basename('windows-x64', stamped=False))"`) do set PLAIN=%%V
if "%STAMPED%"=="" (
  echo error: could not read package stamp
  exit /b 1
)

mkdir dist\packages 2>nul
copy /Y dist\windows\fh6parse.exe dist\packages\%STAMPED%.exe >nul
copy /Y dist\windows\fh6parse.exe dist\packages\%PLAIN%.exe >nul
copy /Y packaging\USAGE.txt dist\packages\USAGE.txt >nul
copy /Y packaging\fh6parse-kiosk.ini.example dist\packages\fh6parse-kiosk.ini.example >nul

echo Built dist\windows\fh6parse.exe
echo Packaged dist\packages\%STAMPED%.exe
if /I not "%STAMPED%"=="%PLAIN%" echo Packaged dist\packages\%PLAIN%.exe
