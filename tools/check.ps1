$ErrorActionPreference = "Stop"

function Assert-NativeSuccess {
    param([string]$Label)
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    cargo fmt --check
    Assert-NativeSuccess "cargo fmt"
    cargo test --workspace
    Assert-NativeSuccess "cargo test"
    cargo run -p brokkr-daemon -- provider | Out-Null
    Assert-NativeSuccess "cargo provider smoke"
    cargo build -p brokkr-daemon | Out-Null
    Assert-NativeSuccess "cargo build"

    $smokeRoot = Join-Path (Get-Location) ".brokkr-smoke"
    New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null

    $log = Join-Path $smokeRoot "brokkr-daemon.log"
    $out = Join-Path $smokeRoot "brokkr-daemon.out.log"
    Remove-Item $log, $out -ErrorAction SilentlyContinue

    $daemon = Start-Process `
        -FilePath (Join-Path (Get-Location) "target\debug\brokkr-daemon.exe") `
        -ArgumentList @("serve", "--bind", "127.0.0.1:8798") `
        -WorkingDirectory (Get-Location) `
        -RedirectStandardError $log `
        -RedirectStandardOutput $out `
        -WindowStyle Hidden `
        -PassThru

    try {
        Start-Sleep -Milliseconds 500
        $healthText = curl.exe -s http://127.0.0.1:8798/health
        Assert-NativeSuccess "health request"
        $health = $healthText | ConvertFrom-Json
        if ($health.ok -ne $true) {
            throw "Brokkr health smoke failed: $health"
        }

        $snapshotPath = Join-Path $smokeRoot "unity-snapshot.json"
        $snapshot = '{"schema":"gamecult.brokkr.tool_host_snapshot.v0","providerId":"brokkr.unity_editor","toolKind":"unity-editor","projectPath":"E:/Projects/StreamPixelsUnity","observedAt":"2026-06-12T12:00:00.0000000Z","unityVersion":"smoke","productName":"StreamPixelsUnity","activeScenePath":"Assets/Scenes/SampleScene.unity","openSceneCount":1,"selectedObjectNames":["SmokeObject"],"assetCount":42,"capabilities":["host.status.read","scene.tree.read","selection.read","asset.catalog.read","command.palette.read","command.execute","receipt.read"]}'
        [System.IO.File]::WriteAllText($snapshotPath, $snapshot, [System.Text.UTF8Encoding]::new($false))

        $receiptText = curl.exe -s -X POST http://127.0.0.1:8798/hosts/unity/snapshot -H "Content-Type: application/json" --data-binary "@$snapshotPath"
        Assert-NativeSuccess "Unity snapshot request"
        $receipt = $receiptText | ConvertFrom-Json
        if ($receipt.status -ne "accepted") {
            throw "Unity snapshot smoke failed: $receipt"
        }

        $hostsText = curl.exe -s http://127.0.0.1:8798/hosts
        Assert-NativeSuccess "Unity host readback request"
        $hosts = $hostsText | ConvertFrom-Json
        if ($hosts.unity.providerId -ne "brokkr.unity_editor") {
            throw "Unity host readback smoke failed: $hosts"
        }
    }
    finally {
        Stop-Process -Id $daemon.Id -ErrorAction SilentlyContinue
    }
}
finally {
    Pop-Location
}
