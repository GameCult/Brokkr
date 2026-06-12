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
}
finally {
    Pop-Location
}
