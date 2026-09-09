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

for /f "usebackq delims=" %%V in (`python -c "from fh6parse._version import __version__; print(__version__)"`) do set APPVER=%%V
if "%APPVER%"=="" (
  echo error: could not read version
  exit /b 1
)

mkdir dist\packages 2>nul
copy /Y dist\windows\fh6parse.exe dist\packages\fh6parse-%APPVER%-windows-x64.exe >nul
copy /Y packaging\USAGE.txt dist\packages\USAGE.txt >nul

echo Built dist\windows\fh6parse.exe
echo Packaged dist\packages\fh6parse-%APPVER%-windows-x64.exe
