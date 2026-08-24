@echo off
setlocal
cd /d "%~dp0"
set "FLUTTER_SUPPRESS_ANALYTICS=true"

set "CODEX_GIT=C:\Users\soy25\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd"
if exist "%CODEX_GIT%\git.exe" set "PATH=%CODEX_GIT%;%PATH%"

where git.exe >nul 2>nul
if errorlevel 1 (
  echo.
  echo Nie znaleziono programu Git.
  echo Zainstaluj Git for Windows: https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

if not exist ".tools\flutter\bin\flutter.bat" (
  echo.
  echo Nie znaleziono lokalnego Flutter SDK.
  echo.
  pause
  exit /b 1
)

echo Uruchamianie MotorSport Calendar w Chrome...
call ".tools\flutter\bin\flutter.bat" run -d chrome

if errorlevel 1 (
  echo.
  echo Nie udalo sie uruchomic aplikacji.
  pause
)
