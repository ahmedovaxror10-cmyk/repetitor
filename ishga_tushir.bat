@echo off
cd /d "%~dp0"
call venv\Scripts\activate
set DEBUG=1
set ADMIN_LOGINS=admin
start http://127.0.0.1:5000
python app.py
pause