@echo off
rem Bead Studio launcher for local development on Windows.
rem   start.cmd                 checks Dahl, Groq, Ollama, then the demo model, and asks which one
rem                             (LLM_PROVIDER=fake or anthropic in .env skips the check)
rem   start.cmd groq            or: dahl, anthropic, ollama, fake: that one, without the check
rem   start.cmd video [groq]    the same on fresh seed data in data-video\ (re-seeded at every
rem                             start, faster renders): for the video takes; data\ is not touched
rem Opens three windows (mock SAP :8100, backend :8000, UI :5173) and the browser. If one of
rem those ports is taken, it shows what holds it and offers to stop it first.
rem Close the three windows to stop. Setup: see "Quick start" in README.md.
setlocal
cd /d "%~dp0"

rem Video mode (decision 0026): environment variables win over .env, so both services and the
rem designs move to data-video\. The reset below empties it at every start.
set "VIDEO="
set "PROVIDER=%~1"
if /i "%~1"=="video" (
  set "VIDEO=1"
  set "PROVIDER=%~2"
  set "DATA_DIR=%~dp0data-video"
  set "DESIGNS_ROOT=%~dp0data-video\designs"
  if not defined RENDER_SAMPLES set "RENDER_SAMPLES=16"
)

if not "%PROVIDER%"=="" (
  if /i not "%PROVIDER%"=="fake" if /i not "%PROVIDER%"=="ollama" if /i not "%PROVIDER%"=="anthropic" if /i not "%PROVIDER%"=="dahl" if /i not "%PROVIDER%"=="groq" (
    echo Unknown LLM provider "%PROVIDER%". Use fake, ollama, anthropic, dahl or groq.
    exit /b 1
  )
  set "LLM_PROVIDER=%PROVIDER%"
)

set "MISSING="
if not exist "backend\.venv\Scripts\python.exe" set "MISSING=1" & echo Missing backend\.venv: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
if not exist "sap-mock\.venv\Scripts\python.exe" set "MISSING=1" & echo Missing sap-mock\.venv: cd sap-mock ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
if not exist "frontend\node_modules" set "MISSING=1" & echo Missing frontend\node_modules: cd frontend ^&^& npm ci
if defined MISSING exit /b 1

if /i "%LLM_PROVIDER%"=="anthropic" if not defined ANTHROPIC_API_KEY if not exist ".env" (
  echo LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY in the environment or in .env.
  exit /b 1
)
if /i "%LLM_PROVIDER%"=="dahl" if not defined DAHL_API_KEY if not exist ".env" (
  echo LLM_PROVIDER=dahl needs DAHL_API_KEY in the environment or in .env.
  exit /b 1
)
if /i "%LLM_PROVIDER%"=="groq" if not defined GROQ_API_KEY if not exist ".env" (
  echo LLM_PROVIDER=groq needs GROQ_API_KEY in the environment or in .env.
  exit /b 1
)

rem Something left from an earlier start on 8000, 8100 or 5173: show it and offer to stop it
rem (decision 0020).
pushd backend
".venv\Scripts\python.exe" -m app.cli free-ports
if errorlevel 1 (
  popd
  echo Nothing was started.
  exit /b 1
)
popd

rem Video mode: back to the seed catalog in data-video\ (the same code as demo-reset, decision 0024).
rem The ports are free now, so no SQLite file is open.
if defined VIDEO (
  pushd backend
  ".venv\Scripts\python.exe" -m app.cli demo-reset --yes >nul
  if errorlevel 1 (
    popd
    echo The video data in data-video\ could not be reset; nothing was started.
    exit /b 1
  )
  popd
  echo Video mode: fresh seed data in data-video\ ^(your data\ folder is not touched^), %RENDER_SAMPLES% render samples.
)
set "CHOICE=%~dp0data\llm-provider.txt"
if defined VIDEO set "CHOICE=%DATA_DIR%\llm-provider.txt"

rem No provider named: check them and let the designer choose (decisions 0019 and 0021). The questions
rem are on this console; the answer comes back in a file under data\ (data-video\ in video mode; gitignored).
if "%PROVIDER%"=="" (
  pushd backend
  ".venv\Scripts\python.exe" -m app.cli llm-check --out "%CHOICE%" >nul
  if errorlevel 1 (
    popd
    echo The model check stopped; nothing was started.
    exit /b 1
  )
  popd
  set /p LLM_PROVIDER=<"%CHOICE%"
)

rem Renders need Blender: use BLENDER_BIN if set, else the newest standard install.
if not defined BLENDER_BIN (
  for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender *") do (
    if exist "%%~D\blender.exe" set "BLENDER_BIN=%%~D\blender.exe"
  )
)

if defined LLM_PROVIDER (echo Starting Bead Studio, LLM: %LLM_PROVIDER%) else (echo Starting Bead Studio, LLM from .env or fake)
if defined BLENDER_BIN (echo Blender: %BLENDER_BIN%) else (echo Blender not found: renders will fail with a hint; set BLENDER_BIN.)

start "Bead Studio - mock SAP :8100" /d "%~dp0sap-mock" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --port 8100"
start "Bead Studio - backend :8000" /d "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
start "Bead Studio - UI :5173" /d "%~dp0frontend" cmd /k "npm run dev -- --port 5173 --strictPort"

echo Waiting for the backend and the UI...
for /l %%i in (1,1,90) do (
  curl -s -o nul -f http://localhost:8000/api/health && curl -s -o nul -f http://localhost:5173 && goto ready
  rem ping as a 1 s pause: timeout needs an interactive console
  ping -n 2 127.0.0.1 >nul
)
echo The services did not answer within 90 s; look at the three windows for errors.
exit /b 1

:ready
echo Bead Studio is running: http://localhost:5173
start "" http://localhost:5173
exit /b 0
