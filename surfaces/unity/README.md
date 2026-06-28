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

The vendor script intentionally copies the MessagePack runtime as
`MessagePack.CultMesh.dll` and removes any sibling `MessagePack.dll`. Unity
projects can already contain a `MessagePack.asmdef`, and importing a DLL with
the same filename makes Unity resolve the wrong assembly identity. Keep
`MessagePack.CultMesh.dll` and `MessagePack.Annotations.dll` on the same
MessagePack package version as CultMesh.

The script also removes `System.Numerics.Vectors.dll`. Unity provides that
facade assembly through its reference assemblies, so the package should not
ship a second facade DLL with a different identity.

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
8. To migrate a Unity prefab into Blender-owned authoring, fill `Prefab Asset
   Path`, optionally set `Blender Collection`, then click
   `Mirror Prefab To Blender`. This writes
   `brokkr.unity.prefab_mirror_snapshot.v0` to the mirror. In Blender, use
   `Import Unity Prefab Mirror` to create the authoring collection.
9. To instantiate or variant a prefab through the mirror for legacy/editor
   command testing, fill `Prefab Asset Path`, optional `Instance Name`, and
   optional `Variant Path`, then click the matching prefab command. These
   commands are not the CDN deploy path.
10. To publish object sync policy, select a GameObject, set the object lane
   toggles including transform, parent, active state, material, and property
   lanes, then click `Publish Object Sync`.
11. Click `Refresh Sync Policy` to inspect the object bindings, timeline
   bindings, and sync vars currently published in the Unity mirror.
12. With the mirror running, run `brokkr-daemon sync-once` or `sync-loop`, then
   click `Poll Sync Receipt` or leave the window open to show the latest daemon
   sync pass receipt.
13. To publish an ad hoc sync variable, fill `Ad Hoc Sync Var` with a binding id
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

## CDN Prefab Migration

The CultMesh CDN does not consume Unity prefabs directly. Unity's role is to
publish a bootstrap mirror snapshot for existing prefabs:

```text
prefabs/unity-mirrors/{snapshotId}
```

That document records render requirements discovered from Unity: hierarchy,
transforms, components, mesh assets, material assets, and texture assets.
Brokkr Blender imports it into a collection, and Blender becomes the authoring
ground truth. The Blender add-on then publishes `brokkr.prefab.snapshot.v0`
deploy snapshots for a CDN deployer to lower into CultMesh CDN artifacts and
`CultMeshEntityPrefabPackage` records.

Players may later receive those packages through CultMesh's visible mesh asset
sharing system. That is runtime CDN behavior, not Unity editor ownership.

The Unity plugin is still an adapter. Unity owns Unity editor truth; Brokkr owns
provider discovery; CultCache and CultMesh own the live mirror lane.
