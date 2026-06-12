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
- `surfaces/blender/brokkr_bridge`: Blender add-on scaffold.
- `brokkr-daemon`: Rust daemon skeleton that emits Brokkr's provider
  advertisement and command policy.

## First Smoke

```powershell
cargo run -p brokkr-daemon -- provider
```

The first smoke prints the typed provider advertisement. That is deliberately
small: discovery shape first, live sockets second.

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
