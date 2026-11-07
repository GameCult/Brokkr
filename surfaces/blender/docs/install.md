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
