# Codex Usage Monitor

Monitor local e read-only dos JSONL em `%USERPROFILE%\.codex\sessions`. Não usa banco, telemetria, API externa ou modelo. O estado é reconstruído dos logs e mantido apenas em memória.

## Executar no Windows

Requer Python 3.11+ e Node 22.14+.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Set-Location frontend
npm.cmd install
Set-Location ..
.\servers.bat
```

O navegador abre automaticamente em `http://127.0.0.1:5177`. O inicializador executa FastAPI em `127.0.0.1:8765` e Vite em `127.0.0.1:5177`. Use `Ctrl+C` na janela para encerrar ambos.

Também é possível chamar diretamente `scripts\start.ps1`; o `servers.bat` apenas oferece o inicializador consistente com os demais projetos Windows.

Para gerar um build servido pelo backend:

```powershell
Set-Location frontend
npm.cmd run build
Set-Location ..
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m codex_monitor
```

O topo do dashboard mostra `Allowance Burn`: a velocidade real da cota global de 5h e semanal, baseada nos snapshots `used_percent` registrados pelo Codex. `Thread Health` e WCI permanecem abaixo como diagnóstico estrutural para decidir se vale continuar uma thread; eles não estimam créditos.

O monitor continua sem banco, telemetria ou escrita nos JSONL. A timeline é reconstruída na inicialização e atualizada incrementalmente em polling. Detalhes de formato, algoritmo, reset e limitações estão em [docs/log-format.md](docs/log-format.md).
