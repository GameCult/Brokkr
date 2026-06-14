# Brokkr Blender Adapter

Install `surfaces/blender/brokkr_bridge` as a Blender add-on directory during
local development.

The add-on adds a Brokkr panel to the 3D View sidebar and exposes a Blender
target surface for host snapshots, admitted command intents, and command
receipts.

The adapter writes its mirror documents through `cultcache-py`. If `cultcache-py`
is not installed into Blender's Python, point `CultCache Python Source` at:

```text
E:/Projects/cultcache-py/src
```

The default store is:

```text
.brokkr/blender-editor.cultcache.jsonl
```

`Debug Export Root` may still emit readable JSON probe files under
`.brokkr/blender-editor-debug`, but those files are debug/import glue. CultCache
owns the mirror state.

## Local Smoke

1. Install and enable `brokkr_bridge`.
2. Open `View3D > Sidebar > Brokkr`.
3. Click `Capture Snapshot`.
4. Inspect `.brokkr/blender-editor.cultcache.jsonl`.
5. Drop a command intent JSON file into
   `.brokkr/blender-editor-debug/blender/commands/{commandId}.json`.
6. Click `Drain Commands`.
7. Inspect `.brokkr/blender-editor.cultcache.jsonl` or the optional debug export
   at `.brokkr/blender-editor-debug/blender/receipts/{commandId}.json`.

Admitted command actions:

- `createObject`
- `deleteObject`
- `setObjectTransform`
- `selectObject`
- `assignMaterial`
