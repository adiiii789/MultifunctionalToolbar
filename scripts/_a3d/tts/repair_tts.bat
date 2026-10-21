@echo off
rem Reparatur des lokalen Miku-TTS (z. B. nach einem Absturz des PCs)
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
for %%V in (3.12 3.11 3.10) do (
  py -%%V -c "import sys" >nul 2>&1 && (
    py -%%V setup_tts.py --repair %*
    goto :ende
  )
)
echo Kein passendes Python gefunden.
:ende
echo.
pause
