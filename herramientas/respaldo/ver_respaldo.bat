@echo off
rem Abre y COMPRUEBA los respaldos mas nuevos (el del VPS y el de la PC). Pide la contrasena de la llave. No deja nada descifrado.
rem   ver_respaldo.bat [carpeta]   (por defecto: Documentos\llave_respaldo)
chcp 65001 >nul
where age >nul 2>nul || (echo Falta age: winget install FiloSottile.age  y abri una ventana nueva & pause & exit /b 1)
set "DIR=%~1"
if "%DIR%"=="" set "DIR=%USERPROFILE%\Documents\llave_respaldo"
set "HAY="
for %%k in (enenos_respaldo_2 enenos_respaldo_pc_2) do call :ver %%k
if "%HAY%"=="" echo No hay respaldos en %DIR%
pause
exit /b
:ver
set "ULT="
for /f "delims=" %%f in ('dir /b /o:n "%DIR%\%1*.tar.gz.age" 2^>nul') do set "ULT=%%f"
if "%ULT%"=="" exit /b
set "HAY=1"
echo.
echo Respaldo: %ULT%
python -X utf8 "%~dp0respaldo.py" ver --archivo "%DIR%\%ULT%" --llave "%DIR%\enenos_respaldo_llave.age"
exit /b
