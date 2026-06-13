# Brokkr Blender Adapter

Install `surfaces/blender/brokkr_bridge` as a Blender add-on directory during
local development.

The add-on adds a Brokkr panel to the 3D View sidebar and exposes a Blender
target surface for host snapshots, admitted command intents, and command
receipts.

Until a Python CultMesh/CultCache binding is available inside Blender, the
adapter writes debug mirror documents under `.brokkr/blender-editor`. That export
is inspection glue, not durable state authority. The target module owns the
document shape so the debug writer can be replaced by a real CultMesh writer
without changing Blender command ownership.

## Local Smoke

1. Install and enable `brokkr_bridge`.
2. Open `View3D > Sidebar > Brokkr`.
3. Click `Capture Snapshot`.
4. Inspect `.brokkr/blender-editor/blender/host/current.json`.
5. Drop a command intent JSON file into
   `.brokkr/blender-editor/blender/commands/{commandId}.json`.
6. Click `Drain Commands`.
7. Inspect `.brokkr/blender-editor/blender/receipts/{commandId}.json`.

Admitted command actions:

- `createObject`
- `deleteObject`
- `setObjectTransform`
- `selectObject`
- `assignMaterial`
