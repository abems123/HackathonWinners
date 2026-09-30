$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskCli = Join-Path $PSScriptRoot 'tailwindcss.exe'
if (-not (Test-Path -LiteralPath $taskCli)) {
    Invoke-WebRequest -Uri 'https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-windows-x64.exe' -OutFile $taskCli
}
Push-Location $taskRoot
try {
    & $taskCli -i tools/tailwind-input.css -o core/static/core/tailwind.css --minify
    if ($LASTEXITCODE -ne 0) { throw 'Tailwind build failed.' }
} finally { Pop-Location }
