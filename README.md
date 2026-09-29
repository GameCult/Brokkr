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
- `brokkr-command`: .NET CLI that writes one Unity command intent through the
  project's directory store and reports the editor's receipt (`docs/provider-contract.md`).
- `brokkr-daemon`: Rust CLI that emits Brokkr's provider advertisement and
  command policy and runs the Unity/Blender sync pass.

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

## Commands

`brokkr-daemon` is a command-line tool over cache files, not a running service.
It has four subcommands:

- `provider` (alias `smoke`): print the provider advertisement.
- `sync-contract`: print the sync contract.
- `sync-once --unity-cache PATH --blender-cache PATH [--dry-run]`: run one sync
  pass between the two editor caches.
- `sync-loop --unity-cache PATH --blender-cache PATH [--interval-ms N]
  [--max-passes N] [--dry-run]`: repeat the sync pass.

## Unity Install

Add the Unity package by local path, alongside `org.gamecult.cultlib` (see
`surfaces/unity/README.md`):

```json
"com.gamecult.brokkr": "file:F:/Projects/Brokkr/surfaces/unity/Packages/com.gamecult.brokkr"
```

Then open `GameCult > Brokkr` in Unity. The window mirrors editor state to a
CultMesh cache file in the project.
