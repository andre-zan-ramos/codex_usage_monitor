@echo off
setlocal

rem Resolve o projeto a partir deste arquivo, inclusive em caminhos com espacos.
pushd "%~dp0"
if errorlevel 1 (
  echo Nao foi possivel acessar o diretorio do Codex Usage Monitor.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python nao encontrado em .venv.
  echo Siga a instalacao descrita no README antes de iniciar o monitor.
  goto :failure
)

where node.exe >nul 2>&1
if errorlevel 1 (
  echo Node.js nao encontrado. Instale Node 22.14 ou superior e reabra o terminal.
  goto :failure
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo npm nao encontrado. Verifique a instalacao do Node.js.
  goto :failure
)

where concurrently.cmd >nul 2>&1
if errorlevel 1 (
  echo concurrently nao encontrado.
  echo Execute npm.cmd install -g concurrently antes de iniciar o monitor.
  goto :failure
)

if not exist "frontend\node_modules\.bin\vite.cmd" (
  echo Dependencias do frontend nao instaladas.
  echo Execute npm.cmd ci dentro da pasta frontend.
  goto :failure
)

echo Iniciando Codex Usage Monitor...
echo API: http://127.0.0.1:8765
echo Web: http://127.0.0.1:5177
echo O navegador sera aberto automaticamente. Use Ctrl+C para encerrar.

set "PYTHONPATH=%CD%\backend"
call concurrently --names "Monitor:API,Vite" ".venv\Scripts\python.exe -m codex_monitor" "cd /d frontend && npm.cmd run dev -- --open / %*"
set "SERVERS_EXIT_CODE=%ERRORLEVEL%"
popd
if not "%SERVERS_EXIT_CODE%"=="0" pause
exit /b %SERVERS_EXIT_CODE%

:failure
popd
pause
exit /b 1
