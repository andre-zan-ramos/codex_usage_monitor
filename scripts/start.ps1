param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ViteArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Ambiente .venv ausente. Siga as instruções do README.'
}
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
$backend = Start-Process -FilePath $python -ArgumentList '-m', 'codex_monitor' -WorkingDirectory $projectRoot -PassThru -WindowStyle Hidden
try {
    Set-Location (Join-Path $projectRoot 'frontend')
    & npm.cmd run dev -- --open / @ViteArgs
}
finally {
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
