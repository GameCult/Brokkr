# Brokkr Architecture

## Objective

Expose creative editor runtimes to the Verse as live CultMesh mirrors, beginning
with Unity and Blender plugin surfaces.

## Current Mechanism

Brokkr is a provider identity and editor-adapter contract. The Rust daemon emits
the discovery document for Odin and the Verse. It does not own Unity scene
truth, command queues, or dashboard state.

The Unity package opens a durable CultMesh node backed by a CultCache store at
`.brokkr/unity-editor.ccmp`. Unity writes typed CultCache documents for the
current editor snapshot, command receipts, Quest routes, and future Eve/CultUI
surface projections. Verse-side clients write typed command-intent documents
into the same mirror; Unity watches those intents, mutates the editor, and
publishes receipts plus an updated snapshot.

## Invariants

- Editor hosts keep editor truth. Brokkr never becomes the canonical scene,
  asset, object, import, or build database.
- CultCache documents are the durable mirror state. CultMesh carries sync,
  watch streams, and Verse visibility.
- Brokkr owns provider identity, mirror schema advertisement, and discovery
  metadata.
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
5. Unity consumes command intents and publishes receipts.
6. Eve GUI/TUI clients lower the mirrored interface documents.

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
- Eve/CultUI surface documents for host status, selection, assets, scene/object
  trees, component state, command affordances, and receipt history.

Derived State:

- Unity package settings are adapter configuration, not Verse authority.
- Blender add-on preferences are adapter configuration, not Verse authority.
- Editor selection and scene summaries are observations until command receipts
  confirm an accepted mutation.

Forbidden Writers:

- Discovery metadata cannot mutate editor state.
- Eve renderers cannot admit commands directly to editor hosts.
- Odin discovery records cannot decide command permissions.
- Local debug exports cannot become durable state truth.

Shared Paths:

- Direct Unity commands, programmatic commands, UI-triggered commands, and replayed
  command receipts use the same command-intent and receipt documents.
- Host snapshots from all tools carry host id, tool kind, project path,
  observed-at timestamp, capabilities, and authority owner.

Deletion Line:

If a plugin grows its own provider advertisement, command policy, or durable
state ledger outside CultCache/CultMesh, cut it back into an adapter and move
the authority into the mirror contract.
