[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$WeaselSetup = "",
    [string]$WeaselRoot = "",
    [string]$RimeUserDir = (Join-Path $env:APPDATA "Rime"),
    [switch]$InstallWeasel,
    [switch]$EnableSystemCapture,
    [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"

function Find-WeaselTool {
    param([string]$Name, [string]$Root)

    $roots = @(
        $Root,
        "C:\Program Files\Rime\weasel",
        "C:\Program Files\Rime",
        "C:\Program Files (x86)\Rime\weasel",
        "C:\Program Files (x86)\Rime"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

    foreach ($candidate in $roots) {
        $tool = Join-Path $candidate $Name
        if (Test-Path -LiteralPath $tool) {
            return (Resolve-Path -LiteralPath $tool).Path
        }
    }
    return $null
}

function Test-RimeLuaSupport {
    param([string]$WeaselDirectory)

    $rimeDll = Join-Path $WeaselDirectory "rime.dll"
    if (-not (Test-Path -LiteralPath $rimeDll)) {
        return $false
    }
    $binaryText = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($rimeDll))
    return $binaryText.Contains("lua_processor")
}

function Add-MirrorMeSchemaRegistration {
    param([string]$Path)

    $marker = "schema: mirrorme_pinyin"
    $registration = "  `"schema_list/@next`":`r`n    - schema: mirrorme_pinyin`r`n"
    $content = if (Test-Path -LiteralPath $Path) {
        Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    } else {
        ""
    }
    $managedNext = '(?m)^  "schema_list/@next":[ \t]*\r?\n    - schema: mirrorme_pinyin[ \t]*\r?\n?'
    $hasExplicitSchemaList = $content -match "(?m)^  schema_list:\s*$"
    $updated = $content

    if ($hasExplicitSchemaList) {
        # Weasel writes a full schema_list in default.custom.yaml. Extend that
        # list directly so a preceding @next patch cannot be overwritten.
        $updated = [regex]::Replace($updated, $managedNext, "")
        if ($updated -match [regex]::Escape($marker)) {
            return $false
        }
        $schemaListPattern = "(?m)^(  schema_list:\s*\r?\n(?:    [^\r\n]*(?:\r?\n|$))*)"
        if (-not [regex]::IsMatch($updated, $schemaListPattern)) {
            throw "Could not locate the existing Rime schema list."
        }
        $updated = [regex]::Replace(
            $updated,
            $schemaListPattern,
            '$1' + "`r`n    - {schema: mirrorme_pinyin}`r`n",
            1
        )
    } elseif ($updated -match [regex]::Escape($marker)) {
        return $false
    } elseif ($updated -match "(?m)^patch:\s*\r?\n") {
        $updated = [regex]::Replace($updated, "(?m)^patch:\s*\r?\n", "patch:`r`n$registration", 1)
    } else {
        $separator = if ($content -and -not $content.EndsWith("`n")) { "`r`n" } else { "" }
        $updated = "$content$separator`r`n# MirrorMe system input method registration.`r`npatch:`r`n$registration"
    }

    if (Test-Path -LiteralPath $Path) {
        $backup = "$Path.bak-$(Get-Date -Format 'yyyyMMddHHmmss')"
        Copy-Item -LiteralPath $Path -Destination $backup
    }
    Set-Content -LiteralPath $Path -Value $updated -Encoding UTF8
    return $true
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$schemaSource = Join-Path $repoRoot "system-ime\rime\mirrorme_pinyin.schema.yaml"
$dictionarySource = Join-Path $repoRoot "system-ime\rime\mirrorme_pinyin.dict.yaml"
$captureSource = Join-Path $repoRoot "system-ime\rime\lua\mirrorme_capture.lua"

if ($InstallWeasel) {
    if (-not $WeaselSetup -or -not (Test-Path -LiteralPath $WeaselSetup)) {
        throw "Pass -WeaselSetup with the locally downloaded WeaselSetup.exe when using -InstallWeasel."
    }
    if ($PSCmdlet.ShouldProcess("Weasel", "Install the external Windows TSF frontend")) {
        & $WeaselSetup "/userdir:$RimeUserDir"
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "Weasel installer exited with code $LASTEXITCODE."
        }
    }
}

$deployer = Find-WeaselTool -Name "WeaselDeployer.exe" -Root $WeaselRoot
if (-not $deployer) {
    throw "Weasel is not installed. Download and install it externally, then rerun with -WeaselRoot or -InstallWeasel -WeaselSetup <path>."
}

if ($PSCmdlet.ShouldProcess($RimeUserDir, "Install MirrorMe Pinyin Rime configuration")) {
    New-Item -ItemType Directory -Force -Path $RimeUserDir | Out-Null
    Copy-Item -LiteralPath $schemaSource -Destination (Join-Path $RimeUserDir "mirrorme_pinyin.schema.yaml") -Force
    Copy-Item -LiteralPath $dictionarySource -Destination (Join-Path $RimeUserDir "mirrorme_pinyin.dict.yaml") -Force
    $installedSchema = Join-Path $RimeUserDir "mirrorme_pinyin.schema.yaml"
    if ($EnableSystemCapture) {
        if (-not (Test-RimeLuaSupport -WeaselDirectory (Split-Path -Parent $deployer))) {
            throw "System capture requires a librime runtime with lua_processor support. Install a compatible librime-lua runtime before rerunning with -EnableSystemCapture."
        }
        $luaDir = Join-Path $RimeUserDir "lua"
        New-Item -ItemType Directory -Force -Path $luaDir | Out-Null
        Copy-Item -LiteralPath $captureSource -Destination (Join-Path $luaDir "mirrorme_capture.lua") -Force
    } else {
        $schemaText = Get-Content -LiteralPath $installedSchema -Raw -Encoding UTF8
        $schemaText = $schemaText -replace '(?m)^    - lua_processor@mirrorme_capture\r?\n', ''
        Set-Content -LiteralPath $installedSchema -Value $schemaText -Encoding UTF8
    }
    $changed = Add-MirrorMeSchemaRegistration -Path (Join-Path $RimeUserDir "default.custom.yaml")
}

if (-not $SkipDeploy -and $PSCmdlet.ShouldProcess("Weasel", "Deploy MirrorMe Pinyin schema")) {
    & $deployer /deploy
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Weasel deployment exited with code $LASTEXITCODE."
    }
}

[pscustomobject]@{
    schema_id = "mirrorme_pinyin"
    schema_name = "MirrorMe Pinyin"
    rime_user_dir = (Resolve-Path -LiteralPath $RimeUserDir).Path
    schema_registered = $changed
    system_capture_enabled = [bool]$EnableSystemCapture
    deployer = $deployer
    deployed = -not $SkipDeploy
    next_step = "Choose MirrorMe Pinyin from the Weasel schema menu, then use the Windows input switcher."
} | ConvertTo-Json -Depth 3
