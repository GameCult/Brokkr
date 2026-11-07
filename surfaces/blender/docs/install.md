# Brokkr Blender Adapter

Install `surfaces/blender/brokkr_bridge` as a Blender add-on directory during
local development.

The add-on adds a Brokkr panel to the 3D View sidebar and exposes a Blender
target surface for host snapshots, admitted command intents, and command
receipts.

The adapter writes its mirror documents through CultLib's Python CultMesh node.
If `cultcache-py`, `cultnet-py` and `cultmesh-py` are not installed into
Blender's Python, point `CultLib Python Source` at the CultLib packages
directory; the add-on puts each package's `src` on `sys.path`:

```text
F:/Projects/CultLib/packages
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
13. To publish an ad hoc sync variable, fill the `Ad Hoc Sync Var` fields in
    the sidebar or add-on preferences and click `Publish Sync Var`.

Admitted command actions:

- `createObject`
- `deleteObject`
- `setObjectTransform`
- `setObjectVisibility`
- `setObjectParent`
- `setObjectCustomProperty`
- `selectObject`
- `assignMaterial`
- `importGltf`
- `setCamera`
- `setLight`
- `setWorld`
- `renderStill`

Scene action fields (all other keys are ignored; a refused intent changes nothing and
gets a `failed` receipt whose message names the rule):

- `importGltf`: `filepath`, `.gltf` or `.glb`, relative to the add-on preference
  `Import Directory` (absolute paths, `..` and symlinks that resolve outside it are
  refused). Empty `Import Directory` disables the action. Needs Blender's glTF add-on.
- `setCamera`: `targetObjectName` (a camera object); optional `lens` (mm),
  `cameraType` (`PERSP`, `ORTHO`, `PANO`), `panoramaType` (for example
  `EQUIRECTANGULAR`; read from the camera, or from `camera.cycles` before Blender 4.2),
  `orthoScale`, `clipStart`, `clipEnd`, `active` (true makes it the scene camera).
  Panoramic cameras render in Cycles.
- `setLight`: `targetObjectName` (a light object); optional `energy` (>= 0),
  `color` (linear `[r, g, b]`, each 0 to 1), `lightType` (`POINT`, `SUN`, `SPOT`, `AREA`).
- `setWorld`: optional `worldName` (default: the scene's world, created if there is
  none), `color` (`[r, g, b]`), `strength`. Edits the world's Background node.
- `renderStill`: `outputPath` relative to the preference `Render Output Directory`,
  ending `.png`, `.jpg` or `.exr` (same containment rules as import); optional
  `engine` (any engine of the running Blender, case-insensitive), `resolutionX`,
  `resolutionY` (whole numbers, 1 to 16384), `cameraName`. Engine, resolution,
  camera, file path and format are restored after the render. The render blocks
  Blender's UI until it finishes.
