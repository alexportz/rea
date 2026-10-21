@echo off
rem Sobe o ambiente local de testes: MariaDB do XAMPP, Canary, login.php e OTClient.
rem Tudo escuta só em 127.0.0.1. Feche as janelas abertas para parar.
setlocal
set ROOT=%~dp0..\..
start "MariaDB (127.0.0.1:3306)" /min /d "C:\xampp\mysql" bin\mysqld.exe --defaults-file=bin\my.ini --standalone --bind-address=127.0.0.1
timeout /t 5 /nobreak >nul
start "Canary (127.0.0.1:7171/7172)" /d "%ROOT%\local\canary" canary.exe
start "Login HTTP (127.0.0.1:8080)" /min C:\xampp\php\php.exe -S 127.0.0.1:8080 -t "%ROOT%\tibia-acessibilidade\servidor-local"
echo Aguarde a janela do Canary mostrar "server online!" e pressione uma tecla para abrir o OTClient.
pause >nul
start "" /d "%ROOT%\local\otclient" otclient.exe
