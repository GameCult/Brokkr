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

## Server Safety

Always on:

- `Start Server` and `Stop Server` purge queued command intents: every
  `brokkr.blender.command_intent.v0` record in the node and every
  `blender/commands/*.json` under `Debug Export Root`. Intents queued before a
  start never run under the new session.
- After `Start Server` the panel shows the bind address, port and the file
  `cultmesh_py` was actually loaded from (its `__file__`, not the preference).
- A `Serve Host` that is not loopback (`0.0.0.0`, a LAN address, a hostname
  other than `localhost`) is refused until `Allow Non-Loopback Bind` is ticked in
  the add-on preferences by hand. While such a server runs the panel shows a
  warning, and unticking the allow stops it.

Opt-in, default off: `Require Session Token`. This is internal infrastructure
and the machine's owner judged per-write access control not worth the friction
by default. When ticked, `Start Server` generates a random token (`secrets`),
the panel offers `Copy Session Token` (the token is never drawn on screen), and the server rejects every document put and delete whose
message lacks it in a top-level `sessionToken` field. It is checked on every
write, not only at connect. Reads stay open. `Stop Server`, quitting, or
disabling the add-on revokes it; it is held in memory only and never saved to
preferences or the cache.

Peer write scope: CultLib's `cultmesh_py` refuses peer writes unless an authority grants them, and the add-on
passes `CultMeshGrantAllWrites()`. A peer that gets past the session token (or any peer, when the token is off) can
therefore put or delete **any registered document** on the served node, not only command intents. That is acceptable
on loopback, the default; a grant scoped to command intents is future work. Do not combine `Allow Non-Loopback Bind`
with the token off.

Run the tests (no Blender needed; `CULTLIB_PACKAGES` adds the real-server tests):

```text
CULTLIB_PACKAGES=F:/Projects/CultLib/packages python -m unittest discover -s surfaces/blender/tests -v
```

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
- `exportGltf`
- `setCamera`
- `setLight`
- `setWorld`
- `renderStill`

Scene action fields (all other keys are ignored; a refused intent changes nothing and
gets a `failed` receipt whose message names the rule):

- `importGltf`: `filepath`, `.gltf` or `.glb`, relative to the add-on preference
  `Import Directory` (absolute paths, `..` and symlinks that resolve outside it are
  refused). Empty `Import Directory` disables the action. Needs Blender's glTF add-on.
- `exportGltf`: `filepath`, `.glb` (binary) or `.gltf` (separate `.bin`), relative to the
  add-on preference `Render Output Directory` (the renderStill rules: no `..`, no links, and an
  existing name, or an existing `.bin` beside a `.gltf`, is refused; there is no overwrite).
  Optional `extras` (custom properties become node `extras`), `yUp`, `applyModifiers`
  (each true by default, must be a boolean) and `selection` (a non-empty list of object
  names; any name not found, or not in the active view layer, refuses the export; the
  selection is touched only when one is given, and restored afterwards). Not checked: texture
  files a `.gltf` export writes beside it (only the `.bin` is), and a link or swap made between the
  check and the write (the same residual as renderStill).
  The receipt message carries the written path and byte size. Needs Blender's glTF add-on.
- `setCamera`: `targetObjectName` (a camera object); optional `lens` (mm),
  `cameraType` (`PERSP`, `ORTHO`, `PANO`), `panoramaType` (for example
  `EQUIRECTANGULAR`; read from the camera, or from `camera.cycles` before Blender 4.2),
  `orthoScale`, `clipStart`, `clipEnd`, `active` (true makes it the scene camera).
  Panoramic cameras render in Cycles.
- `setLight`: `targetObjectName` (a light object); optional `energy` (>= 0),
  `color` (linear `[r, g, b]`, each 0 to 1), `lightType` (`POINT`, `SUN`, `SPOT`, `AREA`).
- `setWorld`: optional `worldName` (default: the scene's world, created if there is
  none), `color` (`[r, g, b]`), `strength`. Edits the world's Background node.
- `assignMaterial`: `targetObjectName` (an object with material slots, such as a mesh);
  optional `materialName` (default `Brokkr Material`; an existing material of that name
  is reused) and `color` (linear `[r, g, b]` or `[r, g, b, a]`, each a finite number 0
  to 1; alpha defaults to 1). `color` sets the Principled BSDF Base Color (the node tree
  is created if the material has none) and `diffuse_color`; a malformed `color` is
  refused naming the field and nothing is created or changed (`"color": null` counts as absent). Without `color` an
  existing material's colour is left as it is. Idempotent per (object, material): if the
  object already has a slot with that material no second slot is added. Other keys are
  ignored, as for every action.
- `renderStill`: `outputPath` relative to the preference `Render Output Directory`,
  ending `.png`, `.jpg` or `.exr` (same containment rules as import); optional
  `engine` (any engine of the running Blender, case-insensitive), `resolutionX`,
  `resolutionY` (whole numbers, 1 to 16384), `cameraName`. Engine, resolution,
  camera, file path and format are restored after the render. The render blocks
  Blender's UI until it finishes.

The scene actions were run against Blender 5.2.3 LTS headless with
`surfaces/blender/tests/live/headless_smoke.py` (usage in its docstring). One real
failure it found: Blender's `engine` enum is dynamic, so `bl_rna` lists only
`BLENDER_EEVEE`; `renderStill` now asks Blender by assignment instead.

### Path rules and the residual race

Both directories take plain relative names only, judged as text the same on every OS:
no drive (`C:`, `C:foo`), UNC or `\\?\` form, leading separator, `..`, NUL, `:` anywhere
(also NTFS streams), trailing dot or space, or Windows device name. No existing component
may be a symlink or junction (Windows' "untrusted mount point" error on a junction counts
as one). `renderStill` refuses any output name that already exists, including symlinks
(even dangling) and hardlinks. `importGltf` parses the `.gltf` JSON (or a `.glb`'s first
chunk) and refuses every `buffers[].uri` / `images[].uri` that is not `data:` or a
relative path inside the import directory; `.gltf` files from the same folder tree work.

**Residual TOCTOU.** The checks run in the add-on, and the path is re-checked (resolved
name, plus size and modification time of the file and its references) immediately before
use, but Blender's own importer and renderer then open the files themselves. Someone who
can write to the import or output directory in that last gap can still swap a file or
link in. The add-on cannot close that window from Python: make both directories writable
only by trusted users, and treat the checks as protection against a malicious *intent*,
not against a hostile local writer. A same-size, same-mtime content swap is also not
detected by the re-check.
