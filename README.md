# Brokkr

Brokkr is the GameCult creative-tool broker daemon: a CultMesh service that lets
Unity, Blender, and future editor runtimes expose their live authoring surfaces
to the Verse without pretending those runtimes are the same machine.

The name earns its keep twice. Brokkr is the dwarf at the forge bellows in the
Eddic treasure contest, holding the work steady while the artifact takes shape.
Brokkr is also the broker: the daemon that routes typed editor observations,
capabilities, commands, and Eve/CultUI surfaces between tool runtimes and the
Verse.

## Authority

- Brokkr owns the broker contract, provider advertisement, routing policy, and
  typed command receipts.
- Unity owns Unity editor truth: scenes, assets, selection, play mode, imports,
  build settings, and editor-side side effects.
- Blender owns Blender editor truth: scenes, objects, assets, operators, add-ons,
  render settings, and editor-side side effects.
- Eve owns rendering of Brokkr surfaces.
- Odin owns discovery of Brokkr as a Verse provider.
- CultCache owns durable `.cc` witnesses and command receipts.

Plugins are adapters. They do not own Verse state. They connect their host editor
to Brokkr, publish editor observations, and execute admitted commands from the
broker.

## Surfaces

- `surfaces/unity/Packages/com.gamecult.brokkr`: Unity editor package scaffold.
- `surfaces/blender/brokkr_bridge`: Blender add-on target backed by
  CultLib's Python CultMesh node/server, with optional debug export/import
  probes.
- `brokkr-daemon`: Rust daemon skeleton that emits Brokkr's provider
  advertisement and command policy.

## First Smoke

```powershell
cargo run -p brokkr-daemon -- provider
```

The first smoke prints the typed provider advertisement. That is deliberately
small: discovery shape first, live sockets second.

## Sync Contract

```powershell
cargo run -p brokkr-daemon -- sync-contract
```

The sync contract advertises Brokkr-owned sessions, object bindings, sync vars,
timeline bindings, and receipts. Unity and Blender editor plugins publish those
documents through CultMesh so a daemon sync loop can translate them into
host-owned command intents without stealing scene truth.

## Prefab CDN Pipeline

Brokkr is the authoring front-end for CultMesh's distributed CDN entity prefab
pipeline. Unity prefabs are migration input only. The intended flow is:

1. In Unity, open `GameCult > Brokkr`, enter a prefab asset path, and click
   `Mirror Prefab To Blender`.
2. Unity writes a `brokkr.unity.prefab_mirror_snapshot.v0` document containing
   the prefab hierarchy, transforms, components, mesh requirements, material
   requirements, and texture requirements.
3. In Blender, click `Import Unity Prefab Mirror` to create a Blender collection
   from that snapshot. From this point forward, Blender owns the renderable
   entity authoring state.
4. In Blender, configure meshes, transforms, materials, metadata, sockets, and
   runtime component hints in the collection.
5. Click `Publish Prefab Snapshot` to write a collection-scoped
   `brokkr.prefab.snapshot.v0` document.
6. A deployer consumes the Brokkr prefab snapshot, publishes referenced binary
   payloads as CultMesh CDN artifacts, and writes a
   `CultMeshEntityPrefabPackage`.
7. Unity, TypeScript, and later runtimes consume the same CultMesh package and
   lower it into native runtime objects.

The CDN is content-addressed and signed at the CultMesh layer. Brokkr does not
turn players into authority for assets; it produces deploy snapshots that the
CDN can distribute through central servers, LAN peers, or visible opt-out peer
asset sharing.

## Unity Smoke

```powershell
cargo run -p brokkr-daemon -- serve
```

Add the Unity package by local path:

```json
"com.gamecult.brokkr": "file:E:/Projects/Brokkr/surfaces/unity/Packages/com.gamecult.brokkr"
```

Then open `GameCult > Brokkr` in Unity and publish a snapshot to the local
daemon.
