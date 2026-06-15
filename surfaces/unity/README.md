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
7. To create a ScriptableObject through the mirror, fill `ScriptableObject Type`,
   `Asset Name`, and `Asset Path`, then click `Create ScriptableObject Asset`.
8. To instantiate or variant a prefab through the mirror, fill `Prefab Asset
   Path`, optional `Instance Name`, and optional `Variant Path`, then click the
   matching prefab command.
9. To publish object sync policy, select a GameObject, set the object lane
   toggles including transform, parent, active state, material, and property
   lanes, then click `Publish Object Sync`.
10. With the mirror running, run `brokkr-daemon sync-once` or `sync-loop`, then
   click `Poll Sync Receipt` or leave the window open to show the latest daemon
   sync pass receipt.
11. To publish an ad hoc sync variable, fill `Ad Hoc Sync Var` with a binding id
    or leave it blank for a generated id, set kind/paths/authority/interpolation,
    then click `Publish Sync Var`.

The Unity adapter writes the latest editor snapshot to:

```text
unity/host/current
```

Brokkr daemon sync receipts are read from:

```text
sync/receipts/{receiptId}
```

Ad hoc sync variables are written to:

```text
sync/vars/{syncVarId}
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

Recognized Unity asset commands include:

- `instantiatePrefab`
- `createPrefabVariant`
- `createScriptableObject`

The Unity plugin is still an adapter. Unity owns Unity editor truth; Brokkr owns
provider discovery; CultCache and CultMesh own the live mirror lane.
