$ErrorActionPreference = "Stop"

function Assert-NativeSuccess {
    param([string]$Label)
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Assert-Contains {
    param(
        [string]$Haystack,
        [string]$Needle,
        [string]$Label
    )
    if (-not $Haystack.Contains($Needle)) {
        throw "$Label did not contain '$Needle'"
    }
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    cargo fmt --check
    Assert-NativeSuccess "cargo fmt"
    cargo test --workspace
    Assert-NativeSuccess "cargo test"

    $provider = cargo run -p brokkr-daemon -- provider
    Assert-NativeSuccess "cargo provider smoke"
    $providerText = ($provider | Out-String)
    $providerJson = $providerText | ConvertFrom-Json

    Assert-Contains $providerText '"kind": "cultmesh"' "provider advertisement"
    Assert-Contains $providerText "brokkr.unity.host_snapshot.v0" "provider advertisement"
    Assert-Contains $providerText "brokkr.unity.command_intent.v0" "provider advertisement"
    foreach ($transport in $providerJson.transports) {
        if ($transport.kind -ne "cultmesh") {
            throw "Unexpected provider transport kind: $($transport.kind)"
        }
    }

    $pluginRoot = Join-Path (Get-Location) "surfaces\unity\Packages\com.gamecult.brokkr\Plugins\CultMesh"
    $requiredDlls = @(
        "GameCult.Caching.dll",
        "GameCult.Caching.MessagePack.dll",
        "GameCult.Mesh.dll",
        "GameCult.Networking.dll",
        "MessagePack.dll",
        "R3.dll"
    )

    foreach ($dll in $requiredDlls) {
        $path = Join-Path $pluginRoot $dll
        if (-not (Test-Path $path)) {
            throw "Missing vendored CultMesh Unity dependency: $path"
        }
    }

    $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $bundledPython) {
        $pythonExe = $bundledPython
    }
    else {
        $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
        if ($null -ne $pythonCommand) {
            $pythonExe = $pythonCommand.Source
        }
        else {
            $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
            if ($null -ne $pythonCommand -and $pythonCommand.Source -notlike "*\WindowsApps\python.exe") {
                $pythonExe = $pythonCommand.Source
            }
        }
    }
    if ([string]::IsNullOrWhiteSpace($pythonExe)) {
        throw "Missing Python runtime for Blender adapter syntax check."
    }
    & $pythonExe -m py_compile surfaces\blender\brokkr_bridge\blender_target.py surfaces\blender\brokkr_bridge\__init__.py
    Assert-NativeSuccess "Blender adapter Python compile"

    $cultCachePySrc = "E:\Projects\cultcache-py\src"
    if (Test-Path $cultCachePySrc) {
        & $pythonExe -c "import sys; sys.path.insert(0, r'$cultCachePySrc'); sys.path.insert(0, r'surfaces\blender\brokkr_bridge'); import blender_target; blender_target._load_cultcache(r'$cultCachePySrc')"
        Assert-NativeSuccess "Blender adapter CultCache import"
    }
}
finally {
    Pop-Location
}
