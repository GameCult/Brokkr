# Brokkr Architecture

## Objective

Expose creative editor runtimes to the Verse as live CultMesh mirrors, beginning
with Unity and Blender plugin surfaces.

## Current Mechanism

Brokkr is a provider identity, editor-adapter contract, and sync organ contract.
The Rust daemon emits the discovery document for Odin and the Verse. It owns
sync correspondence and policy documents; it does not own Unity or Blender scene
truth, command queues, or dashboard state.

The Unity package opens a durable CultMesh node backed by a CultCache store at
`.brokkr/unity-editor.ccmp`. Unity writes typed CultCache documents for the
current editor snapshot, command receipts, Quest routes, and future Eve/CultUI
surface projections. Verse-side clients write typed command-intent documents
into the same mirror; Unity watches those intents, mutates the editor, and
publishes receipts plus an updated snapshot.

The Blender add-on uses CultLib's Python CultMesh runtime as its local mirror
node. Blender writes typed host snapshots and command receipts through
registered CultMesh database document definitions, drains command intents from
the same node database, and only uses loose JSON files as optional debug/export
probes. The add-on can serve the node through `CultMesh.serve_node(...)` so
external CultNet/CultMesh clients can request schema catalogs, snapshots, shard
logs, and raw document mutations.

The sync organ owns `brokkr.sync.*` documents: sessions, object bindings, sync
vars, timeline bindings, and receipts. Unity and Blender plugins can publish
those records from editor UI. The daemon's `sync-once` primitive translates
sync records into host command intents; `sync-loop` schedules that primitive on
a polling interval without creating a second sync authority.

## Invariants

- Editor hosts keep editor truth. Brokkr never becomes the canonical scene,
  asset, object, import, or build database.
- CultCache documents are the durable mirror state. CultMesh carries sync,
  watch streams, and Verse visibility.
- Brokkr owns provider identity, mirror schema advertisement, and discovery
  metadata.
- Brokkr owns sync correspondence and policy records. Editor hosts still own
  scene mutation.
- Unity owns Unity editor mutations. A command intent is not truth until Unity
  publishes a receipt and refreshed mirror state.
- Eve/CultUI surfaces are typed projections over the mirror, not renderer-owned
  dashboards.
- JSON is tolerated for schema publication and debug inspection only. It is not
  the load-bearing state lane.

## Intended Change

The old local adapter server has been cut out. The live path is now:

1. Brokkr advertises CultMesh mirror schemas.
2. Unity opens its CultMesh node.
3. Unity captures editor state and writes typed CultCache documents.
4. Verse clients watch mirror state or write command-intent documents.
5. `brokkr-daemon sync-loop` reads Unity and Blender mirrors, applies
   `brokkr.sync.*` policy records, emits host command intents, and writes sync
   receipts.
6. Unity and Blender consume command intents and publish receipts.
7. Eve GUI/TUI clients lower the mirrored interface documents.

## Owner Map

Owner: Brokkr owns tool-to-Verse discovery.

Inputs:

- Host observations from Unity and Blender plugins.
- Command-intent documents written through CultMesh.
- Odin discovery queries.
- Eve/CultUI lowering requests.

Outputs:

- `gamecult.brokkr.provider_advertisement.v0`
- `brokkr.unity.host_snapshot.v0`
- `brokkr.unity.command_intent.v0`
- `brokkr.unity.command_receipt.v0`
- `brokkr.unity.snapshot_receipt.v0`
- `brokkr.unity.quest_route.v0`
- `brokkr.unity.warped_video_frame.v0`
- `brokkr.blender.host_snapshot.v0`
- `brokkr.blender.command_intent.v0`
- `brokkr.blender.command_receipt.v0`
- `brokkr.sync.session.v0`
- `brokkr.sync.object_binding.v0`
- `brokkr.sync.var.v0`
- `brokkr.sync.timeline_binding.v0`
- `brokkr.sync.receipt.v0`
- Eve/CultUI surface documents for host status, selection, assets, scene/object
  trees, component state, command affordances, and receipt history.
- Per-pass daemon reports printed by `sync-once` or `sync-loop`.

Derived State:

- Unity package settings are adapter configuration, not Verse authority.
- Blender add-on preferences are adapter configuration, not Verse authority.
- Blender JSON debug exports are inspection/import probes, not mirror authority.
- Unity and Blender sync UI fields are command/edit affordances; the
  `brokkr.sync.*` documents are the shared sync policy surface.
- Editor selection and scene summaries are observations until command receipts
  confirm an accepted mutation.
- Daemon stdout reports are telemetry, not durable sync state. The durable state
  is the command intent, command receipt, host snapshot, and sync receipt.

Forbidden Writers:

- Discovery metadata cannot mutate editor state.
- Eve renderers cannot admit commands directly to editor hosts.
- Odin discovery records cannot decide command permissions.
- Local debug exports cannot become durable state truth.

Shared Paths:

- Direct Unity commands, programmatic commands, UI-triggered commands, and replayed
  command receipts use the same command-intent and receipt documents.
- Direct Blender commands, UI-triggered commands, and replayed command receipts
  use the same command-intent and receipt documents.
- One-shot and continuous sync use the same `run_sync_once` decision primitive;
  the loop owns scheduling only.
- Host snapshots from all tools carry host id, tool kind, project path,
  observed-at timestamp, capabilities, and authority owner.

Deletion Line:

If a plugin grows its own provider advertisement, command policy, or durable
state ledger outside CultCache/CultMesh, cut it back into an adapter and move
the authority into the mirror contract.
