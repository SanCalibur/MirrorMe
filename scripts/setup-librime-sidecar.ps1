param(
    [string]$RimeRoot = "",
    [string]$RimeIncludeDir = "",
    [string]$RimeLibrary = "",
    [string]$RimeSharedDataDir = "",
    [string]$RimeUserDataDir = "",
    [string]$BuildDir = ".mirrorme\build\librime-json-stdio",
    [string]$Generator = "Ninja",
    [string]$Configuration = "Release",
    [switch]$PersistUserEnv
)

$ErrorActionPreference = "Stop"

function Resolve-FirstPath {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Find-FirstFile {
    param(
        [string[]]$Roots,
        [string[]]$Names
    )
    foreach ($root in $Roots) {
        if (-not $root -or -not (Test-Path -LiteralPath $root)) {
            continue
        }
        foreach ($name in $Names) {
            $found = Get-ChildItem -Path $root -Recurse -Filter $name -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($found) {
                return $found.FullName
            }
        }
    }
    return $null
}

function Set-OptionalUserEnv {
    param([string]$Name, [string]$Value)
    if (-not $Value) {
        return
    }
    Set-Item -Path "Env:$Name" -Value $Value
    if ($PersistUserEnv) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    }
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$candidateRoots = @(
    $RimeRoot,
    "D:\Tools\Rime",
    "D:\Tools\librime",
    "C:\Tools\Rime",
    "C:\Tools\librime",
    "$env:LOCALAPPDATA\Rime",
    "$env:ProgramFiles\Rime"
) | Where-Object { $_ }

if (-not $RimeIncludeDir) {
    $header = Find-FirstFile -Roots $candidateRoots -Names @("rime_api.h")
    if ($header) {
        $RimeIncludeDir = Split-Path -Parent $header
    }
}

if (-not $RimeLibrary) {
    $RimeLibrary = Find-FirstFile -Roots $candidateRoots -Names @("rime.lib", "librime.lib")
}

if (-not $RimeSharedDataDir) {
    $sharedCandidates = @()
    if ($RimeRoot) {
        $sharedCandidates += Join-Path $RimeRoot "share"
        $sharedCandidates += Join-Path $RimeRoot "data"
    }
    $sharedCandidates += @(
        "D:\Tools\Rime\share",
        "D:\Tools\Rime\data",
        "C:\Tools\Rime\share",
        "C:\Tools\Rime\data"
    )
    $RimeSharedDataDir = Resolve-FirstPath $sharedCandidates
}

if (-not $RimeUserDataDir) {
    $RimeUserDataDir = Join-Path $env:APPDATA "MirrorMe\rime"
}

if (-not $RimeIncludeDir -or -not (Test-Path -LiteralPath (Join-Path $RimeIncludeDir "rime_api.h"))) {
    throw "rime_api.h was not found. Pass -RimeIncludeDir or -RimeRoot."
}
if (-not $RimeLibrary -or -not (Test-Path -LiteralPath $RimeLibrary)) {
    throw "rime.lib/librime.lib was not found. Pass -RimeLibrary or -RimeRoot."
}

New-Item -ItemType Directory -Force -Path $RimeUserDataDir | Out-Null

$cmake = Get-Command cmake -ErrorAction SilentlyContinue
if (-not $cmake) {
    $cmakePath = "C:\Program Files\CMake\bin\cmake.exe"
    if (-not (Test-Path -LiteralPath $cmakePath)) {
        throw "CMake was not found in PATH or C:\Program Files\CMake\bin."
    }
    $cmakeExe = $cmakePath
} else {
    $cmakeExe = $cmake.Source
}

$cmakeArgs = @(
    "--fresh",
    "-S", "sidecars\librime-json-stdio",
    "-B", $BuildDir,
    "-G", $Generator,
    "-DRIME_INCLUDE_DIR=$RimeIncludeDir",
    "-DRIME_LIBRARY=$RimeLibrary"
)

& $cmakeExe @cmakeArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $cmakeExe --build $BuildDir --config $Configuration
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$exe = Get-ChildItem -Path $BuildDir -Recurse -Filter "mirrorme-librime-json-stdio.exe" |
    Select-Object -First 1
if (-not $exe) {
    throw "Build succeeded but mirrorme-librime-json-stdio.exe was not found under $BuildDir."
}

Set-OptionalUserEnv -Name "MIRRORME_RIME_BINARY" -Value $exe.FullName
Set-OptionalUserEnv -Name "MIRRORME_RIME_SHARED_DATA_DIR" -Value $RimeSharedDataDir
Set-OptionalUserEnv -Name "MIRRORME_RIME_USER_DATA_DIR" -Value $RimeUserDataDir

[pscustomobject]@{
    binary = $exe.FullName
    include_dir = (Resolve-Path -LiteralPath $RimeIncludeDir).Path
    library = (Resolve-Path -LiteralPath $RimeLibrary).Path
    shared_data_dir = $RimeSharedDataDir
    user_data_dir = $RimeUserDataDir
    persisted_user_env = [bool]$PersistUserEnv
} | ConvertTo-Json -Depth 3
