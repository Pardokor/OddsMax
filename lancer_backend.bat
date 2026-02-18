@echo off
echo Installation des dependances...
pip install flask flask-cors requests
echo.
echo Lancement du backend OddsMax...
python backend.py
pause
