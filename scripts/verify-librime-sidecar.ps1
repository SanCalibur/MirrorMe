param(
    [string]$Binary = $env:MIRRORME_RIME_BINARY,
    [string]$Schema = "luna_pinyin",
    [string]$InputText = "ni hao",
    [string]$DbPath = ".mirrorme\verify-librime-sidecar.db"
)

$ErrorActionPreference = "Stop"

if (-not $Binary) {
    throw "MIRRORME_RIME_BINARY is not set. Pass -Binary or run scripts\setup-librime-sidecar.ps1 first."
}
if (-not (Test-Path -LiteralPath $Binary)) {
    throw "Sidecar binary does not exist: $Binary"
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$schemaRequest = @{
    method = "schema"
    params = @{ schema = $Schema }
} | ConvertTo-Json -Compress

$composeRequest = @{
    method = "compose"
    params = @{ schema = $Schema; text = $InputText }
} | ConvertTo-Json -Compress

$schemaResult = $schemaRequest | & $Binary
$composeResult = $composeRequest | & $Binary

$env:MIRRORME_RIME_BINARY = (Resolve-Path -LiteralPath $Binary).Path
$probe = uv run python -m mirrorme.cli ime probe
$verification = uv run python -m mirrorme.cli ime verify $InputText --require-native
$capture = uv run python -m mirrorme.cli --db $DbPath ime capture $InputText --project MirrorMe --tag rime-smoke --force

[pscustomobject]@{
    binary = $env:MIRRORME_RIME_BINARY
    schema = $schemaResult | ConvertFrom-Json
    compose = $composeResult | ConvertFrom-Json
    probe = $probe | ConvertFrom-Json
    verification = $verification | ConvertFrom-Json
    capture = $capture | ConvertFrom-Json
} | ConvertTo-Json -Depth 8
