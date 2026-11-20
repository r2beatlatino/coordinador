@echo off
rem Crea LA llave del respaldo (una sola vez). Doble clic o desde cmd. Ver crear_llave.sh.
chcp 65001 >nul
where age-keygen >nul 2>nul || (
  echo Falta age. Instalalo con:  winget install FiloSottile.age
  echo y despues CERRA esta ventana y abri una nueva, para que Windows lo encuentre.
  pause
  exit /b 1
)
set "DEST=%~1"
if "%DEST%"=="" set "DEST=%USERPROFILE%\Documents\llave_respaldo"
cd /d "%~dp0..\.."
"C:\Program Files\Git\bin\sh.exe" herramientas/respaldo/crear_llave.sh "%DEST%"
pause
