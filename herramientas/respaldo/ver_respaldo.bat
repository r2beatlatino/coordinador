@echo off
rem Abre y COMPRUEBA el respaldo mas nuevo de una carpeta (pide la contrasena de la llave). No deja nada descifrado.
rem   ver_respaldo.bat [carpeta]   (por defecto: Documentos\llave_respaldo)
chcp 65001 >nul
where age >nul 2>nul || (echo Falta age: winget install FiloSottile.age  y abri una ventana nueva & pause & exit /b 1)
set "DIR=%~1"
if "%DIR%"=="" set "DIR=%USERPROFILE%\Documents\llave_respaldo"
set "ULT="
for /f "delims=" %%f in ('dir /b /o:n "%DIR%\enenos_respaldo_2*.tar.gz.age"') do set "ULT=%%f"
if "%ULT%"=="" (echo No hay respaldos en %DIR% & pause & exit /b 1)
echo Respaldo: %ULT%
python -X utf8 "%~dp0respaldo.py" ver --archivo "%DIR%\%ULT%" --llave "%DIR%\enenos_respaldo_llave.age"
pause
