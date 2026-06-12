# Brokkr Unity Adapter

This package lets the Unity Editor publish its scene, component, asset, command,
receipt, Quest, and Eve/CultUI state as typed CultCache documents synced through
CultMesh.

## Install By Local Path

Add this package to a Unity project's `Packages/manifest.json`:

```json
"com.gamecult.brokkr": "file:E:/Projects/Brokkr/surfaces/unity/Packages/com.gamecult.brokkr"
```

Vendor the CultMesh runtime DLLs before opening Unity:

```powershell
.\tools\vendor-cultmesh-unity.ps1
```

Then open `GameCult > Brokkr`.

## Local Smoke

In Unity:

1. Open `GameCult > Brokkr`.
2. Confirm `Broker URI` is `cultmesh://brokkr`.
3. Confirm `CultMesh Cache` points at `.brokkr/unity-editor.ccmp`.
4. Click `Start CultMesh Mirror`.
5. Click `Capture Snapshot`.
6. Click `Publish Mirror`.

The Unity adapter writes the latest editor snapshot to:

```text
unity/host/current
```

Verse-side command clients write `brokkr.unity.command_intent.v0` documents to:

```text
unity/commands/{commandId}
```

Unity watches those command intents, mutates the editor, and publishes receipts
to:

```text
unity/receipts/{commandId}
```

The Unity plugin is still an adapter. Unity owns Unity editor truth; Brokkr owns
provider discovery; CultCache and CultMesh own the live mirror lane.
