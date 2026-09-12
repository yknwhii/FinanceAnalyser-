@echo off
REM Launch the local finance CLI application.
REM Priority: .venv -> Python in %LOCALAPPDATA%\Programs\Python -> py launcher.
REM Always sets console codepage to 65001 (UTF-8) for proper Cyrillic output.
REM On error - pause so the user can read the message.

setlocal
chcp 65001 >nul

REM 1. Local .venv (if created).
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    goto :run
)

REM 2. Direct path to Python 3.13 in LOCALAPPDATA (python.org default).
REM    We avoid "where python" because PATH often contains a Microsoft
REM    Store stub that opens the store instead of running Python.
set "PY_LOCAL=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%PY_LOCAL%" (
    set "PYTHON_EXE=%PY_LOCAL%"
    goto :run
)

REM 3. Try other Python 3.x versions installed in LOCALAPPDATA.
for %%V in (313 312 311 310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        goto :run
    )
)

REM 4. py launcher as last resort.
where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py -3"
    goto :run
)

REM 5. Not found - friendly message and pause.
echo.
echo [ERROR] Python 3.10 or newer is required.
echo         Install it from https://www.python.org/downloads/
echo         or create a virtual environment:  python -m venv .venv
echo.
echo Press any key to exit...
pause >nul
exit /b 1

:run
echo Using Python: %PYTHON_EXE%
%PYTHON_EXE% src\main.py
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo Press any key to exit...
    pause >nul
)

endlocal & exit /b %RC%
