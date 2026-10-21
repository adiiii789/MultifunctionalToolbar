@echo off
rem Einmalige Einrichtung des lokalen Miku-TTS fuer den 3D-Assistenten
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
for %%V in (3.12 3.11 3.10) do (
  py -%%V -c "import sys" >nul 2>&1 && (
    echo Verwende Python %%V
    py -%%V setup_tts.py %*
    goto :ende
  )
)
echo Kein passendes Python gefunden. Bitte Python 3.12 (64 Bit) von python.org installieren
echo (Haken bei "py launcher" setzen) und diese Datei erneut starten.
:ende
echo.
pause
