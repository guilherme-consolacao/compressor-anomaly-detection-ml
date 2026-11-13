$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Split-Path $PSScriptRoot -Parent) 'reports/private/metabase-runtime'
$jar = Join-Path $runtime 'metabase.jar'
if (-not (Test-Path -LiteralPath $jar)) { throw 'Metabase JAR ausente na pasta do painel.' }

$pidFile = Join-Path $runtime 'metabase.pid'
if (Test-Path -LiteralPath $pidFile) {
    $process = Get-Process -Id ([int](Get-Content -LiteralPath $pidFile)) -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -eq 'java') {
        Write-Output 'Metabase local já iniciado em http://127.0.0.1:3000'
        return
    }
}

$java = Get-ChildItem -LiteralPath $runtime -Filter java.exe -Recurse -File | Select-Object -First 1
if (-not $java) {
    Expand-Archive -LiteralPath (Join-Path $runtime 'java25.zip') -DestinationPath $runtime
    $java = Get-ChildItem -LiteralPath $runtime -Filter java.exe -Recurse -File | Select-Object -First 1
}
if (-not $java) { throw 'Java portátil ausente na pasta do painel.' }

$env:MB_JETTY_HOST = '127.0.0.1'
$env:MB_JETTY_PORT = '3000'
$env:MB_DB_FILE = Join-Path $runtime 'metabase-app'
$env:MB_ANON_TRACKING_ENABLED = 'false'
$process = Start-Process -FilePath $java.FullName -WorkingDirectory $runtime -WindowStyle Hidden `
    -ArgumentList '-Xmx2g','--add-opens','java.base/java.nio=ALL-UNNAMED','-jar','metabase.jar' `
    -RedirectStandardOutput (Join-Path $runtime 'metabase.log') `
    -RedirectStandardError (Join-Path $runtime 'metabase-error.log') -PassThru
Set-Content -LiteralPath $pidFile -Value $process.Id
Write-Output 'Metabase iniciando em http://127.0.0.1:3000'
