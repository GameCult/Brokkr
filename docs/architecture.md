# Brokkr Architecture

## Objective

Expose creative editor runtimes to the Verse through one coherent CultMesh broker
daemon, beginning with Unity and Blender plugin surfaces.

## Current Mechanism

Brokkr starts as a Rust daemon skeleton that can emit a provider advertisement.
Unity and Blender each have a thin plugin scaffold with host-local metadata and
connection settings. The live transport is intentionally not claimed yet; the
first contract establishes owner, inputs, outputs, command policy, and surface
names.

## Invariants

- Editor hosts keep editor truth. Brokkr never becomes the canonical scene,
  asset, object, import, or build database.
- Brokkr owns Verse-facing broker identity, command admission, routing receipts,
  and durable witness publication.
- Unity and Blender commands share the same command envelope and receipt shape.
- Eve/CultUI surfaces are projections over Brokkr/provider state and host
  observations, not separate dashboards with their own truth.
- JSON is tolerated only as a schema/debug/export boundary. Durable state should
  become CultCache `.cc` witnesses as the runtime grows.

## Intended Change

The Unity idea is widened into a general creative-tool broker: Unity and Blender
are peers behind one broker contract. Tool-specific plugins stay boring and
replaceable. Brokkr becomes the stable Verse organ.

## Cut Line

Do not build separate Unity and Blender Verse providers unless a future invariant
proves they need independent authority. Do not give plugins their own discovery
truth, command policy, or dashboard summaries. They delegate to Brokkr.

## Owner Map

Owner: Brokkr owns tool-to-Verse brokerage.

Inputs:

- Host observations from Unity and Blender plugins.
- Operator commands admitted through Brokkr's command policy.
- Odin discovery queries.
- Eve/CultUI surface requests.
- CultCache witness stores.

Outputs:

- `gamecult.brokkr.provider_advertisement.v0`
- `gamecult.brokkr.tool_host_snapshot.v0`
- `gamecult.brokkr.command_request.v0`
- `gamecult.brokkr.command_receipt.v0`
- Eve/CultUI surface documents for host status, selection, assets, scene/object
  trees, command palette, and receipt history.

Derived State:

- Unity package settings are adapter configuration, not Verse authority.
- Blender add-on preferences are adapter configuration, not Verse authority.
- Editor selection and scene summaries are observations until command receipts
  confirm an accepted mutation.

Forbidden Writers:

- Unity editor callbacks cannot write Verse provider truth directly.
- Blender operators cannot write Verse provider truth directly.
- Eve renderers cannot admit commands directly to editor hosts.
- Odin discovery records cannot decide command permissions.

Shared Paths:

- Unity commands, Blender commands, programmatic commands, UI-triggered commands,
  and replayed command receipts must use the same command envelope.
- Host snapshots from all tools must carry host id, tool kind, project path,
  observed-at timestamp, capabilities, and authority owner.

Deletion Line:

If a plugin grows its own command policy, provider advertisement, or durable
state ledger, cut it back into an adapter and move the authority into Brokkr.

