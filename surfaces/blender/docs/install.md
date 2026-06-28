# Brokkr Blender Adapter

Install `surfaces/blender/brokkr_bridge` as a Blender add-on directory during
local development.

The add-on adds a Brokkr panel to the 3D View sidebar and exposes a Blender
target surface for host snapshots, admitted command intents, and command
receipts.

The adapter writes its mirror documents through CultLib's Python CultMesh node.
If `cultcache-py`/`cultmesh_py` is not installed into Blender's Python, point
`CultLib Python Source` at:

```text
E:/Projects/CultLib-main-work/packages/cultcache-py/src
```

The default node cache is:

```text
.brokkr/blender-editor.ccmp
```

The panel can also serve that node through CultMesh Python. Leave `Serve Port`
at `0` to bind a free local port, or set a fixed port when another runtime needs
a stable endpoint. The panel reports the active `cultnet://host:port` endpoint
after `Start Server`.

`Debug Export Root` may still emit readable JSON probe files under
`.brokkr/blender-editor-debug`, but those files are debug/import glue. CultMesh
owns the mirror state.

## Local Smoke

1. Install and enable `brokkr_bridge`.
2. Open `View3D > Sidebar > Brokkr`.
3. Click `Capture Snapshot`.
4. Inspect `.brokkr/blender-editor.ccmp`.
5. Drop a command intent JSON file into
   `.brokkr/blender-editor-debug/blender/commands/{commandId}.json`.
6. Click `Drain Commands`, or enable `Auto Drain Commands` to poll command
   intents once per second while the add-on is loaded.
7. Inspect `.brokkr/blender-editor.ccmp` or the optional debug export
   at `.brokkr/blender-editor-debug/blender/receipts/{commandId}.json`.
8. Click `Start Server`.
9. Use the reported `cultnet://host:port` endpoint from a CultMesh/CultNet
   client to read snapshots or write command intents.
10. In the `Object Sync` section, set the Unity object id/path and lane toggles,
    select a Blender object, then click `Object Sync` to publish a
    `brokkr.sync.object_binding.v0` plus per-lane `brokkr.sync.var.v0` records
    for transform, parent, visibility, material, and custom property sync.
11. In the `Timeline / Cinemachine` section, set the Unity Timeline and
    Cinemachine targets, then click `Timeline Sync` to publish a
    `brokkr.sync.timeline_binding.v0` for Blender frame/action data and Unity
    Timeline/Cinemachine lanes.
12. After running `brokkr-daemon sync-once` or `sync-loop`, click
    `Refresh Sync Receipt` to show the latest daemon sync pass observed in the
    Blender mirror. Keep `Auto Drain Commands` enabled while `sync-loop` is
    running if Blender should continuously consume daemon command intents.
13. Click `Refresh Sync Policy` to inspect the object bindings, timeline
    bindings, and sync vars currently published in the Blender mirror.
14. To publish an ad hoc sync variable, fill the `Ad Hoc Sync Var` fields in
    the sidebar or add-on preferences and click `Publish Sync Var`.

## CDN Prefab Authoring

Brokkr Blender is the authoring side of the CultMesh CDN prefab pipeline.
Existing Unity prefabs are mirrored into Blender once; after that, Blender owns
the renderable entity configuration.

1. In Unity, click `Mirror Prefab To Blender` for the legacy prefab.
2. In Blender, click `Import Unity Prefab Mirror`. The add-on reads the latest
   `brokkr.unity.prefab_mirror_snapshot.v0` document from the shared mirror and
   creates or updates a collection.
3. Configure the collection in Blender: meshes, transforms, materials, sockets,
   custom properties, and runtime component metadata.
4. Click `Publish Prefab Snapshot`. The add-on writes a
   `brokkr.prefab.snapshot.v0` record containing the collection-scoped deploy
   snapshot.
5. A deployer consumes that snapshot, publishes binary payloads as CultMesh CDN
   artifacts, and writes a `CultMeshEntityPrefabPackage`.

The Blender deploy snapshot is not a Unity prefab file and not an FBX dump. It
is a portable authoring snapshot that downstream Unity and TypeScript clients
can receive through CultMesh CDN and lower into their own runtime object model.

Admitted command actions:

- `createObject`
- `deleteObject`
- `setObjectTransform`
- `setObjectVisibility`
- `setObjectParent`
- `setObjectCustomProperty`
- `selectObject`
- `assignMaterial`
