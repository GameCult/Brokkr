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
        $snapshot = '{"schema":"gamecult.brokkr.tool_host_snapshot.v0","providerId":"brokkr.unity_editor","toolKind":"unity-editor","projectPath":"E:/Projects/StreamPixelsUnity","observedAt":"2026-06-12T12:00:00.0000000Z","unityVersion":"smoke","productName":"StreamPixelsUnity","activeScenePath":"Assets/Scenes/SampleScene.unity","openSceneCount":1,"selectedObjectNames":["SmokeObject"],"assetCount":42,"capabilities":["host.status.read","scene.tree.read","selection.read","asset.catalog.read","command.palette.read","command.execute","receipt.read"],"sceneObjects":[{"objectId":"scene-object-1","name":"SmokeObject","path":"SmokeObject","scenePath":"Assets/Scenes/SampleScene.unity","activeSelf":true,"tag":"Untagged","layer":0,"childCount":0,"parentId":"","components":[{"componentId":"component-1","typeName":"UnityEngine.Transform","assemblyQualifiedName":"UnityEngine.Transform, UnityEngine.CoreModule","enabled":true,"properties":[{"path":"m_LocalPosition.x","displayName":"X","propertyType":"Float","value":"0","editable":true}]}]}],"assets":[{"path":"Assets/Smoke.prefab","guid":"smoke-guid","typeName":"UnityEngine.GameObject","isPrefab":true}]}'
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

        $scene = curl.exe -s http://127.0.0.1:8798/unity/scene
        Assert-NativeSuccess "Unity scene read request"
        $scene = $scene | ConvertFrom-Json
        if ($scene.providerId -ne "brokkr.unity_editor") {
            throw "Unity scene read smoke failed: $scene"
        }

        $command = '{"schema":"gamecult.brokkr.unity_command.v0","commandId":"smoke-create","action":"createGameObject","name":"BrokkrSmokeObject"}'
        $queued = $command | curl.exe -s -X POST http://127.0.0.1:8798/commands/unity -H "Content-Type: application/json" --data-binary "@-"
        Assert-NativeSuccess "Unity command queue request"
        $queued = $queued | ConvertFrom-Json
        if ($queued.commandId -ne "smoke-create") {
            throw "Unity command queue smoke failed: $queued"
        }

        $next = curl.exe -s http://127.0.0.1:8798/hosts/unity/commands/next
        Assert-NativeSuccess "Unity command next request"
        $next = $next | ConvertFrom-Json
        if ($next.command.commandId -ne "smoke-create") {
            throw "Unity command next smoke failed: $next"
        }

        $commandReceipt = '{"schema":"gamecult.brokkr.unity_command_receipt.v0","commandId":"smoke-create","status":"accepted","message":"smoke","objectId":"smoke-object","observedAt":"2026-06-12T12:00:00.0000000Z"}'
        $postedReceipt = $commandReceipt | curl.exe -s -X POST http://127.0.0.1:8798/hosts/unity/commands/receipt -H "Content-Type: application/json" --data-binary "@-"
        Assert-NativeSuccess "Unity command receipt request"
        $postedReceipt = $postedReceipt | ConvertFrom-Json
        if ($postedReceipt.status -ne "accepted") {
            throw "Unity command receipt smoke failed: $postedReceipt"
        }

        $gui = curl.exe -s http://127.0.0.1:8798/eve/unity/gui
        Assert-NativeSuccess "Unity Eve GUI request"
        $gui = $gui | ConvertFrom-Json
        if ($gui.schema -ne "gamecult.eve.surface.v1") {
            throw "Unity Eve GUI smoke failed: $gui"
        }

        $tui = curl.exe -s http://127.0.0.1:8798/eve/unity/tui
        Assert-NativeSuccess "Unity Eve TUI request"
        $tui = $tui | ConvertFrom-Json
        if ($tui.mode -ne "tui") {
            throw "Unity Eve TUI smoke failed: $tui"
        }
    }
    finally {
        Stop-Process -Id $daemon.Id -ErrorAction SilentlyContinue
    }
}
finally {
    Pop-Location
}
