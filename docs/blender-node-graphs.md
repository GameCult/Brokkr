# Blender node graphs: design

Status: design only, no code. Draft for review. Nothing here is implemented; every
Blender API claim comes from Blender's documented Python API and has **not** been
run against a live Blender (none is installed on the machines that wrote this).

## Why

The scene actions (`importGltf`, `setCamera`, `setLight`, `setWorld`, `renderStill`)
move objects and settings. The generative power in Blender is in node graphs:
shader/material trees and, above all, geometry nodes. This design gives Brokkr
enough hooks to **create and configure** those graphs from typed intents and to
**read them back**, with the same posture as the rest of the add-on: Blender owns
the mutation, Brokkr carries typed documents, intents are validated whole before
`bpy` is touched, and every refused intent produces a `failed` receipt that names the
rule.

Non-goals for this cut series: node *authoring UX* (layout beyond a location),
animation/driver authoring on node values, simulation and repeat *zones* (they need
paired nodes; see Open questions), baking, add-on node packs, and anything that
executes user code.

## Tree kinds and owners

A **tree** is addressed by `treeKind` and `treeKey`. The owner decides where the
tree lives in Blender.

| `treeKind` | Blender type | owner (`treeKey` is) | create via |
|---|---|---|---|
| `material` | `ShaderNodeTree` on a material | material name | `bpy.data.materials.new`, `use_nodes = True` |
| `world` | `ShaderNodeTree` on a world | world name | `bpy.data.worlds.new`, `use_nodes = True` |
| `geometry` | `GeometryNodeTree` node group | node group name | `bpy.data.node_groups.new(name, 'GeometryNodeTree')` |
| `compositor` | `CompositorNodeTree` | scene name | scene compositor tree |
| `shaderGroup` | `ShaderNodeTree` node group | node group name | `node_groups.new(name, 'ShaderNodeTree')` |

A geometry tree reaches the scene only by being assigned to a Geometry Nodes
modifier (`assignNodeTree`, below). Material trees are assigned by the existing
`assignMaterial`. Where Blender versions disagree, the target adapts and the version
matrix at the end records it.

## The typed graph document

`brokkr.blender.node_graph.v0` is a CultCache document (one record per tree, key
`blender/node_graphs/{treeKind}/{treeKey}`), published into the Blender mirror the
way `brokkr.blender.host_snapshot.v0` is. Persisted and carried as typed state, not
JSON; a JSON debug export may exist under the debug root like the other mirror
documents, as glue only.

```text
NodeGraph
  schema         "brokkr.blender.node_graph.v0"
  treeKind       material | world | geometry | compositor | shaderGroup
  treeKey        string
  revision       integer, increments on every change Brokkr or the user makes
  contentHash    hash of nodes+links+interface (canonical order), for no-op detection
  interface      [InterfaceSocket]      groups only (geometry, shaderGroup): the tree's own inputs/outputs
  nodes          [Node]
  links          [Link]
  truncated      bool, true when a cap below cut the read-back short
Node
  id             string, Brokkr-owned, unique in the tree, 1..63 chars [A-Za-z0-9._-]
  blIdname       string, e.g. "ShaderNodeBsdfPrincipled", "GeometryNodeMeshCube"
  label          string, optional
  location       [x, y] floats
  properties     map name -> PropertyValue   node-level settings (not sockets): operation, data_type, blend_type...
  inputs         [Socket]
  outputs        [Socket]                    read-back only; carries no default
  group          string, for group nodes: treeKey of the referenced node group
  mute           bool
Socket
  identifier     string, Blender's socket identifier (stable; names repeat, e.g. the three "Value" inputs of Math)
  name           string, display name
  type           Float | Int | Bool | Vector | Color | String | Object | Collection | Material | Image | Geometry | Shader | Rotation | Matrix ...
  default        Value, inputs only, absent when the socket has no stored default (Geometry, Shader)
  linked         bool, read-back only
Link
  fromNode, fromSocket (identifier)   ->   toNode, toSocket (identifier)
InterfaceSocket
  identifier, name, inOut (Input|Output), type, default, min, max, subtype
Value
  tagged: number | integer | bool | string | vector3 | rgba | ref(kind, name)
PropertyValue
  tagged: number | integer | bool | string | enum(identifier) | ref(kind, name)
```

Rules:

- **`id` is Brokkr's key, not Blender's.** The adapter stores it as a custom property
  (`node["brokkr_id"]`) and also sets `node.name` to it when free, so the Blender UI
  shows it. A user renaming a node does not break addressing, because lookup is by the
  custom property. A node without `brokkr_id` (made by hand in the UI) reads back with
  a derived id `bl:{name}` and is addressable under it; touching it stamps a real id.
- **Sockets are addressed by `identifier`,** never by name or index. Names repeat and
  indices shift when Blender adds sockets for an enum change.
- **Values are tagged and typed**; no stringly-typed numbers. A Vector default is
  exactly three finite floats, a Color exactly four (linear, alpha included).
  References (`Object`, `Material`, `Collection`, `Image`) are by name and must
  resolve in `bpy.data` at apply time.
- **Enums are properties, not socket values,** and are validated against the running
  Blender's own enum items (read from `bl_rna`), the way `renderStill` validates
  `engine`. The adapter never keeps a hard-coded enum table.
- **Group nodes** reference a node group by `treeKey`; the referenced tree must exist
  (create it first with `createNodeGroup`). A group may not contain itself, directly
  or through other groups (refused, see Errors).

## Read-back

`brokkr.blender.node_graph.v0` records are published on the same triggers as the host
snapshot (capture, and after any node action), for trees the host snapshot's
material/world/modifier lists name, plus any tree a node action touched. Caps keep the
mirror bounded: at most 500 nodes and 2000 links per tree, and the whole set respects
the server's `max_snapshot_documents`/`max_snapshot_bytes`. Over the cap the record is
cut at a node boundary and `truncated = true`; the writer reads `truncated` before
trusting a missing node. Read-back is the only way to learn socket identifiers and
group interface identifiers, so a client creating a graph follows the pattern
**create node → read back → link by identifier**, or uses the stable identifiers
documented per node type (below).

`revision` and `contentHash` give clients optimistic concurrency: every node action
may carry `expectedRevision`; a mismatch is refused (`stale_revision`) rather than
merged. Absent means "do not check".

## Actions

All are `brokkr.blender.command_intent.v0` intents with the existing receipt flow. Each
action addresses a tree by `treeKind` + `treeKey` and may carry `expectedRevision`.
Receipts keep `accepted`/`failed`, with `message` naming the rule; the receipt's
`objectName` carries the node id or tree key touched.

| action | fields | effect |
|---|---|---|
| `createNodeTree` | `treeKind`, `treeKey`, optional `owner` | Creates the tree (and its owning material/world if absent). No-op `accepted` if it exists with the same kind. |
| `createNodeGroup` | `treeKind` (`geometry`/`shaderGroup`), `treeKey`, `interface` | Creates a node group and its interface sockets (`tree.interface.new_socket` on Blender 4+). Same name+kind: converges the interface (below). |
| `addNode` | tree, `id`, `blIdname`, `location`, optional `label`, `properties`, `inputs` (identifier -> Value), `group` | Creates the node if `id` is free; applies properties then input defaults. |
| `removeNode` | tree, `id` | Removes the node and its links. Absent `id`: `accepted` (already gone). |
| `setNodeInput` | tree, `id`, `socket` (identifier), `value` | Sets an unlinked input's default. Refused if the socket is linked or has no default. |
| `setNodeProperty` | tree, `id`, `property`, `value` | Sets a node-level property from the node type's allowlist. |
| `linkSockets` | tree, `fromNode`, `fromSocket`, `toNode`, `toSocket` | Links outputs to an input. Replaces an existing link into a single-link input. |
| `unlinkSockets` | tree, `toNode`, `toSocket`, optional `fromNode`, `fromSocket` | Removes links into an input (all, or the one matching). None to remove: `accepted`. |
| `assignNodeTree` | `treeKind` (`geometry`), `treeKey`, `objectName`, optional `modifierName` | Adds or reuses a Geometry Nodes modifier named `modifierName` (default `Brokkr GeoNodes`) on the object and sets its `node_group`. `setModifierInput` below sets its exposed inputs. |
| `setModifierInput` | `objectName`, `modifierName`, `socket` (interface identifier), `value` | Sets a Geometry Nodes modifier input (`modifier[identifier]`), validated against the group's interface type. |

Material and world trees need no `assign` action: `assignMaterial` and `setWorld`
already attach them. Compositor trees belong to the scene and need none.

**Batches.** A geometry graph is dozens of nodes and links; one intent per node is
slow and unsafe half-way. Recommended and part of this design: an `editNodeTree`
intent carrying an ordered `ops` list whose elements are the actions above (minus the
common tree fields), **validated entirely first, then applied, and rolled back as a
whole if any op fails at apply time** (Blender's undo stack is not used from a timer;
rollback is by recorded inverse operations, see Open questions). A single-op action is
an `editNodeTree` of one.

### Idempotency, by node id

The rule: **replaying any intent leaves the tree as it was after the first
application.**

- `addNode` with an existing `id` of the same `blIdname`: **converges**; location,
  label, properties and listed inputs are set to the intent's values; unlisted inputs
  and links are untouched; receipt `accepted` with message `exists, updated`. A
  different `blIdname` under that `id` is refused (`id_type_conflict`); the node is
  not replaced silently (replacing would drop its links).
- `removeNode` of a missing `id`: `accepted`.
- `setNodeInput`/`setNodeProperty`: absolute values, so replay is a no-op.
- `linkSockets` of an existing identical link: `accepted`, no duplicate. A different
  source into a single-link input replaces the link and says so in the message.
- `unlinkSockets` with nothing to remove: `accepted`.
- `createNodeTree`/`createNodeGroup`: same key and kind converges; same key,
  different kind is refused. An existing group's interface is converged by socket
  `identifier`: changed type/default/range updated, missing added, **extra sockets are
  kept unless the intent says `pruneInterface: true`** (removing them unlinks users).
- Command ids already dedupe replays of the same intent at the queue (the drain
  deletes an intent after executing it); id-based convergence covers re-sent intents
  with new command ids, which is the realistic case for a retrying client.

## Error cases

Each is a `failed` receipt, raised before any change when it can be detected from the
intent plus the current tree; at apply time inside a batch it rolls the batch back.
The code is a stable slug at the start of `message`, for clients to branch on.

| slug | when |
|---|---|
| `tree_not_found` / `tree_kind_mismatch` | `treeKey` absent for the action, or exists with another kind |
| `owner_not_found` | `createNodeTree` names a material/world/scene that cannot be created or found |
| `id_invalid` / `id_duplicate` | `id` fails the pattern or repeats within one batch |
| `id_type_conflict` | `addNode` for an existing `id` with another `blIdname` |
| `node_not_found` | an action names an `id` that is not in the tree (except the idempotent no-ops above) |
| `node_type_unknown` | `blIdname` is not a node type of the running Blender |
| `node_type_not_allowed` | `blIdname` is on the exclusion list, or not valid in this `treeKind` (see Safety) |
| `socket_not_found` | `identifier` does not exist on the node (message lists the valid ones) |
| `socket_type_mismatch` | a `Value` does not fit the socket's type (vector length, non-finite, wrong tag) |
| `socket_has_no_default` | `setNodeInput` on Geometry/Shader sockets |
| `socket_linked` | `setNodeInput` on a linked input (unlink first) |
| `property_not_allowed` / `property_value_invalid` | not on the node type's allowlist; or value not in the enum or out of range |
| `reference_not_found` | a `ref` names an object/material/collection/image not in `bpy.data` |
| `link_invalid` | Blender reports the link invalid (`link.is_valid` false): type conversion not allowed, or field-to-non-field |
| `link_cycle` | the link would create a cycle |
| `group_cycle` | a group would contain itself, directly or through other groups |
| `group_not_found` | a group node names a `treeKey` that does not exist |
| `stale_revision` | `expectedRevision` differs from the tree's `revision` |
| `limit_exceeded` | the batch or the tree would pass a cap (500 nodes, 2000 links, 256 ops per batch) |
| `path_outside_directory` | a property that names a file (image path) is outside the configured import directory |
| `version_unsupported` | the running Blender lacks an API the action needs (e.g. group interface on Blender < 4.0) |

## Safety: what must not be exposed

The surface exists to build node graphs, not to run code. The rules, each testable
without Blender:

1. **Script nodes are excluded.** `ShaderNodeScript` (OSL, from an external file or an
   internal text datablock) is not creatable and not settable; reading one back reports
   it as an opaque node with no properties. Any `blIdname` containing `Script` is
   refused, and the exclusion list is checked **before** the Blender type lookup, so a
   future Blender node of that kind needs an explicit allow, not a missing deny.
2. **No Python reaches the tree through values.** `Value` and `PropertyValue` are tagged
   data; strings are only accepted for sockets and properties whose type is string, and
   are never evaluated. Driver and keyframe creation on node values is not an action;
   driver expressions (which Blender evaluates as Python) cannot be set by any intent
   here.
3. **Allowlist by node namespace and tree kind, then by property.** A `blIdname` must
   exist in the running Blender, belong to the `treeKind`'s namespace (`ShaderNode*`,
   `GeometryNode*`, `CompositorNode*`, plus `NodeGroup*`, `NodeReroute`, `NodeFrame`),
   and not be on the exclusion list. A node-level property is settable only if it is
   in the plain-data kinds Blender exposes via `bl_rna` (bool, int, float, string, enum)
   or a `ref` kind from a short list (object, material, collection, image, node group),
   and not on a per-node-type denylist of properties that name a file or text datablock.
4. **File-touching nodes are confined or excluded.** Nodes that name a file get the same
   treatment as `importGltf`/`renderStill`: an image path (`ShaderNodeTexImage` image
   source) must resolve inside the configured Import Directory; geometry-node *importer*
   nodes (OBJ/STL/PLY/CSV import, version permitting) and compositor *writer* nodes
   (File Output) are excluded in v1. Compositor output stays with `renderStill`, whose
   output is already confined.
5. **Whole-intent validation first.** No partial application of a refused intent. A
   batch is validated, then applied, and a failure at apply time restores the tree.
6. **Caps.** 500 nodes, 2000 links and 256 ops per batch keep a single intent from
   becoming a resource attack; nested groups are capped at depth 8.
7. **Authority.** These actions ride the same admission path as the other Blender
   intents. The server hardening (optional session token, bind guard, intent purge) is
   unchanged and covers them.

## Testable without Blender, and what needs it

Without Blender (stdlib only, in the style of `server_guard.py` and `scene_actions.py`):

- The graph document types and their canonical (de)serialization, including
  `contentHash` stability under reordering.
- Id and identifier patterns, value tagging and range checks, enum checks against a
  supplied enum table, reference tagging.
- The exclusion list, namespace/tree-kind allowlist, property allowlist, path
  confinement, caps, depth limit.
- Pure graph algorithms on the document: link cycle detection, group-cycle detection,
  idempotent convergence (`addNode` on existing, `linkSockets` replace), batch
  validation and ordering, and **rollback by inverse ops** over an in-memory graph.
- The adapter against a **fake `bpy` node tree** (nodes, sockets, links as plain
  objects), the way `test_scene_actions.py` fakes `bpy`: it proves the adapter's
  sequence of calls and its refusals, not Blender's behaviour.

Needs a live Blender (a smoke script run headless with `blender -b --python`, kept in
the repo, run by a human or on a runner with Blender):

- That `nodes.new(type=...)` accepts every `blIdname` the allowlist admits, and that
  socket identifiers and enum item sets match what the fake assumes.
- `link.is_valid` semantics (field/non-field, type conversion), and link replacement.
- Group interface creation and the converge-by-identifier rule on Blender 4.0 through
  the current release; geometry nodes modifier assignment and input setting.
- Where the compositor tree lives (see matrix), and `use_nodes` behaviour.
- Round trip: build a tree from actions, read it back, apply the read-back to a fresh
  tree, read again; the two read-backs must be equal. This is the one test that proves
  the document is a faithful model of the tree.

## Version matrix (to verify on a live Blender)

| area | Blender 3.x | 4.0 to 4.x | 5.x |
|---|---|---|---|
| group interface | `tree.inputs/outputs` | `tree.interface.new_socket(...)` | same as 4.x |
| material/world tree | `use_nodes = True` then `node_tree` | same | `use_nodes` is deprecated and trees may always exist; confirm |
| compositor tree | `scene.use_nodes`, `scene.node_tree` | same | the scene's tree becomes a node group on the scene (`compositing_node_group`); confirm |
| geometry nodes zones | none | 3.6 simulation, 4.0 repeat | same |

The add-on declares `blender: (4, 0, 0)` today, so v1 supports 4.0+ and answers
`version_unsupported` below it. Rows marked "confirm" are claims this document could
not check.

## Cut plan

Each cut is its own PR with tests that fail when its rule breaks.

1. **Document and guards, no bpy.** Types, canonical form, hash; id/identifier/value
   validation; exclusion and allowlist; caps. Pure tests.
2. **Pure graph engine.** In-memory graph, idempotent apply of the action set, batch
   validate-then-apply with inverse-op rollback, cycle checks. Pure tests, including
   replay and rollback properties.
3. **Adapter to Blender.** Reads a `bpy` node tree into the document and applies ops
   to it; fake-`bpy` tests; `assignNodeTree`, `setModifierInput`. Read-back publishing.
4. **Live smoke.** Headless Blender script and the round-trip test; version matrix
   filled in with what Blender actually does.
5. **Node recipes (optional).** Named, tested graph builders (a procedural scatter, a
   PBR material) expressed as documents, so clients do not rediscover identifiers.

## Open questions

1. **Declarative apply vs actions.** An `applyNodeGraph` intent that converges a tree to
   a whole `NodeGraph` document is the natural fit for a generated graph and for the
   round-trip test, and the fine-grained actions could be defined over it. Recommended:
   build both on the same engine; ship `editNodeTree` (ordered ops) first. Confidence
   moderate; node-editing tools elsewhere (Blender MCP servers surveyed in
   `docs/research/blender-mcp-capability-bar.md`) mostly offer per-node calls, which is
   the weakest option for atomicity.
2. **Rollback mechanism.** Recorded inverse ops (recommended) against restoring from a
   pre-apply read-back document. Inverse ops avoid touching unrelated state;
   restoring from the document is simpler and uses the engine twice. Needs the live
   smoke to see which is more faithful.
3. **Zones.** Simulation and repeat zones come as input/output node pairs
   (`pair_with_output`). Excluded in v1; admitting them needs a paired-add op and a
   paired-remove rule.
4. **Where node ids are stored** if a future Blender removes custom properties on
   nodes: fall back to `node.name` only and accept that a UI rename breaks addressing.
5. **Packaging of the exclusion list** as a versioned typed document the daemon can
   read, so the policy is advertised as a capability and not only enforced in the
   add-on.
