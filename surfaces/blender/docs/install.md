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
6. Click `Drain Commands`.
7. Inspect `.brokkr/blender-editor.ccmp` or the optional debug export
   at `.brokkr/blender-editor-debug/blender/receipts/{commandId}.json`.
8. Click `Start Server`.
9. Use the reported `cultnet://host:port` endpoint from a CultMesh/CultNet
   client to read snapshots or write command intents.
10. Select a Blender object and click `Object Sync` to publish a
    `brokkr.sync.object_binding.v0` plus per-lane `brokkr.sync.var.v0` records.
11. Click `Timeline Sync` to publish a `brokkr.sync.timeline_binding.v0` for
    Blender frame/action data and Unity Timeline/Cinemachine lanes.

Admitted command actions:

- `createObject`
- `deleteObject`
- `setObjectTransform`
- `setObjectVisibility`
- `selectObject`
- `assignMaterial`
