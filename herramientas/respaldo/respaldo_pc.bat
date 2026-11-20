@echo off
rem Respaldo de los SECRETOS de esta PC (llaves de las listas, Cloudflare, SSH). Cifrado a la llave publica: no pide contrasena.
rem Lo que guarda: respaldo_pc.json. Sale a Documentos\llave_respaldo\enenos_respaldo_pc_<fecha>.tar.gz.age
chcp 65001 >nul
where age >nul 2>nul || (echo Falta age: winget install FiloSottile.age  y abri una ventana nueva & pause & exit /b 1)
set "DIR=%~1"
if "%DIR%"=="" set "DIR=%USERPROFILE%\Documents\llave_respaldo"
python -X utf8 "%~dp0respaldo.py" armar --lista "%~dp0respaldo_pc.json" --origen "%USERPROFILE%" --salida "%DIR%" --para "%~dp0llave_publica.txt" --nombre enenos_respaldo_pc
pause
