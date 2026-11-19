@echo off
rem Bead Studio launcher for local development on Windows.
rem   start.cmd                 the LLM from .env or the environment (default: fake, no model needed)
rem   start.cmd groq            or: dahl, anthropic, ollama, fake
rem Opens three windows (mock SAP :8100, backend :8000, UI :5173) and the browser.
rem Close the three windows to stop. Setup: see "Quick start" in README.md.
setlocal
cd /d "%~dp0"

if not "%~1"=="" (
  if /i not "%~1"=="fake" if /i not "%~1"=="ollama" if /i not "%~1"=="anthropic" if /i not "%~1"=="dahl" if /i not "%~1"=="groq" (
    echo Unknown LLM provider "%~1". Use fake, ollama, anthropic, dahl or groq.
    exit /b 1
  )
  set "LLM_PROVIDER=%~1"
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

rem Renders need Blender: use BLENDER_BIN if set, else the newest standard install.
if not defined BLENDER_BIN (
  for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender *") do (
    if exist "%%~D\blender.exe" set "BLENDER_BIN=%%~D\blender.exe"
  )
)

curl -s -o nul http://localhost:8000/api/health && (
  echo Something already answers on port 8000. Close the running backend first.
  exit /b 1
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
