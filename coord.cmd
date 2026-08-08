@echo off
rem coord — the developer entry point for Windows Coordinator (Windows launcher).
rem
rem Forwards everything to tools\coord\coord.py, resolved from THIS file's directory (%~dp0) rather
rem than the current directory, so it works from anywhere. The POSIX counterpart is `coord`.
rem
rem Stdlib-only Python 3.11+ — no virtual environment, no pip install. See tools\coord\README.md.

setlocal

set "COORD_SCRIPT=%~dp0tools\coord\coord.py"

if not exist "%COORD_SCRIPT%" (
    echo coord: cannot find "%COORD_SCRIPT%" 1>&2
    echo        This launcher must sit at the repository root, next to tools\. 1>&2
    exit /b 2
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python "%COORD_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

rem Fall back to the py launcher, which a Microsoft Store or all-users install often provides
rem when `python` itself is not on PATH.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 "%COORD_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

echo coord: no Python interpreter found on PATH ^(looked for python, then py^). 1>&2
echo        The tooling needs Python 3.11+; see docs\runbooks\dev-setup.md. 1>&2
exit /b 2
