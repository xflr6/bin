@echo off

REM cd into project subdirectory, activate its _venv,
REM and optionally start idle with the remaining arguments

cd %userprofile%\projects\%1
shift

call _venv\Scripts\activate.bat

if "%~1" NEQ "" cd %1
shift

set args=%1
shift
if [%args%] == [] goto :end

:loop
if "%~1" == "" goto loop_end
set args=%args% %1
shift
goto loop
:loop_end

start /b python -m idlelib.idle %args%

:end
