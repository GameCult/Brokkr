# Blender node graphs: design

Status: design only, no add-on code. Draft for review. Nothing here is implemented in the
add-on. Every Blender API claim is marked **[verified 5.2.3]** when
[`surfaces/blender/tests/live/node_graph_probe.py`](../surfaces/blender/tests/live/node_graph_probe.py)
ran it headless on Blender 5.2.3 LTS (37 checks, result in `node_graph_probe.result.json`),
and is otherwise from the documented Python API and **unverified**. The probe is a throwaway
op interpreter, not the adapter; it proves the vocabulary maps onto the real API, not that
the adapter exists. What was and was not verified is tabulated in "Verification status".

## Why

The scene actions (`importGltf`, `setCamera`, `setLight`, `setWorld`, `renderStill`)
move objects and settings. The generative power in Blender is in node graphs:
shader/material trees and, above all, geometry nodes. This design gives Brokkr
enough hooks to **create and configure** those graphs from typed intents and to
**read them back**, with the same posture as the rest of the add-on: Blender owns
the mutation, Brokkr carries typed documents, intents are validated whole before
`bpy` is touched, and every refused intent produces a `failed` receipt that names the
rule.

Non-goals for this cut series: node *authoring UX* (layout beyond a location, parent and
colour), animation/driver authoring on node values, baking and simulation caches, add-on
node packs, and anything that executes user code. Zones (simulation, repeat, for-each) are
**in** v1 (below).

Worked examples from real setups, with the design gaps they exposed, are in
[`blender-node-graph-examples.md`](blender-node-graph-examples.md). Its gaps 1 to 6 and 8
(item sockets, zones, field-ness on interface sockets, multi-input sockets, library groups,
socket types, evaluated read-back) and 11 (parent, colour) are folded into this document;
gaps 7, 9 and 10 stay open and are listed under Open questions.

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
  interface      [InterfaceItem]        groups only (geometry, shaderGroup): the tree's own inputs/outputs and panels, in order
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
  group          GroupRef, for group nodes: the referenced node group
  items          [NodeItem]                  nodes that grow sockets (capture, zones, menu/index switch, bundles): ordered
  pairedWith     string, zone input nodes: the Node.id of the paired zone output (and back); read-back
  parent         string, optional: Node.id of a NodeFrame this node sits in
  color          [r, g, b], optional: custom node colour (use_custom_color)
  mute           bool
NodeItem
  collection     string, the node's item collection: capture_items | repeat_items | state_items | main_items | generation_items | input_items ...
  name           string, unique within the collection
  socketType     the item's data type (tagged as for Socket.type; 'VECTOR', 'FLOAT', 'GEOMETRY' ...)
  identifier     string, read-back only: the socket identifier(s) the item produced, in/out (see "Item sockets")
GroupRef
  treeKey        string
  library        string, optional: absent for a tree in this file, else the Library.id from linkNodeGroupAsset
Socket
  identifier     string, Blender's socket identifier (stable; names repeat, e.g. the three "Value" inputs of Math)
  name           string, display name
  type           Float | Int | Bool | Vector | Color | String | Object | Collection | Material | Image | Geometry | Shader | Rotation | Matrix | Menu | Bundle | Closure | List ...
  default        Value, inputs only, absent when the socket has no stored default (Geometry, Shader)
  linked         bool, read-back only
  multiInput     bool, read-back only: the socket takes many links (Join Geometry); `linked` counts them
  structure      read-back only: the socket's inferred structure (SINGLE | FIELD | GRID | LIST ...); the tree evaluator decides
  available      bool, read-back only: false when the node's current properties hide the socket
Link
  fromNode, fromSocket (identifier)   ->   toNode, toSocket (identifier)
  order          integer, read-back; for a multi-input target the position among its links (0 = first created)
InterfaceItem
  tagged: InterfaceSocket | InterfacePanel
InterfaceSocket
  identifier     string, Blender's, read-back only and OPAQUE (`Socket_0`, `Socket_4`...), never the name
  name, inOut (Input|Output), type, default, min, max, subtype
  structure      AUTO | DYNAMIC | FIELD | GRID | LIST | SINGLE        (RNA `structure_type`)
  defaultInput   VALUE | INDEX | ID_OR_INDEX | NORMAL | POSITION | INSTANCE_TRANSFORM | HANDLE_LEFT | HANDLE_RIGHT |
                 SCENE_FRAME | UNIFORM_IMAGE_COORDINATES | SELF_OBJECT   (RNA `default_input`; enum read from the running Blender)
  attributeDomain POINT | EDGE | FACE | CORNER | CURVE | INSTANCE | LAYER   (RNA `attribute_domain`, output sockets)
  hideValue      bool; also hideInModifier, forceNonField, optionalLabel, defaultAttributeName
  panel          string, optional: name of the InterfacePanel that holds it
InterfacePanel
  name, defaultClosed, description; position is its order in `interface`
Value
  tagged: number | integer | bool | string | vector3 | rgba | menu(item) | ref(kind, name)
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
- **Group nodes** reference a node group by `GroupRef`; the referenced tree must exist
  (create it first with `createNodeGroup`, or link it with `linkNodeGroupAsset`). A group
  may not contain itself, directly or through other groups (refused, see Errors).
- **Interface identifiers are opaque. [verified 5.2.3]** A new group's interface sockets get
  `Socket_0`, `Socket_1`... in creation order, not their names; the Group Input/Output node
  sockets and every Group node instance use those identifiers (verified, including a linked
  library group, whose `Scatter on Surface` inputs are `Socket_0`, `Socket_30`...). So the
  examples' `gin.Radius` is shorthand: the op layer resolves an interface **name** to its
  identifier when the name is unique among that side's sockets (else `socket_ambiguous`), the
  receipt of `createNodeGroup` and the read-back return the identifiers, and a stored
  document always carries identifiers. Only identifiers are stable under a rename.
- **Item sockets. [verified 5.2.3]** Some nodes grow sockets from an item collection.
  Identifiers are valid only after the item exists, and are not all alike: Capture Attribute
  item 1 gives input `Value` / output `Attribute`, item 2 `Value_1` / `Attribute_1` (single
  underscore, unlike Math's `Value_001`); Repeat and Simulation items are `Item_0`, `Item_1`...
  on both the input and the output node. Items are created by `addNodeItem`, listed in
  `Node.items`, and their socket identifiers are read back, never computed by the client.
- **Field-ness is the tree evaluator's, not a Brokkr rule. [verified 5.2.3]** `link.is_valid`
  is false for a field (Input Normal) into a single-value socket (`Mesh Cube.Size`) and into
  a geometry socket (`Extrude Mesh.Mesh`), and true for field-to-field, a field into a group
  node's `FIELD` input, and a float into a vector socket (`Scale Instances.Scale`); Brokkr maps
  invalid to `link_invalid` and does not try to model structure itself. The document reports
  each socket's inferred structure read-only, and an interface socket's declared `structure`
  and `defaultInput` are settable and round-trip.
- **Multi-input sockets. [verified 5.2.3]** Join Geometry's `Geometry` input has
  `is_multi_input` true and a `link_limit` above 1. Links into it keep a `multi_input_sort_id`
  (read-only in the API) assigned in creation order, 0 first; a second identical link is not
  created. On 5.2.3 the result starts with the **last**-created link and ends with the
  first: three transformed meshes linked in the order b, a, c gave a first vertex from c and a
  last vertex from b (only the ends were checked, not the middle). The order is therefore
  link-creation order, and the only way to change it is to unlink and relink (see
  `linkSockets`).

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
| `addNodeItem` | tree, `id`, `collection`, `socketType`, `name` | Adds an item to a node's item collection (`capture_items.new`, `repeat_items.new`, `state_items.new`, ...) and returns the new socket identifiers in the receipt. The collection must be on a per-node-type allowlist (below). Existing item of that name and type: `accepted`, converges. |
| `removeNodeItem` | tree, `id`, `collection`, `name` | Removes an item (and its links). Absent: `accepted`. |
| `addZone` | tree, `kind` (`simulation` / `repeat` / `foreach_geometry_element`), `inId`, `outId`, `location` | Creates both zone nodes and pairs them (`input.pair_with_output(output)`); each carries its default Geometry item. Items are then added to the **output** node with `addNodeItem`. Each half is addressed by its own `id`; read-back carries `pairedWith`. |
| `removeZone` | tree, `inId` or `outId` | Removes both halves and their links. `removeNode` on one half is refused (`zone_half`). |
| `linkSockets` | tree, `fromNode`, `fromSocket`, `toNode`, `toSocket`, optional `position` | Links outputs to an input. Replaces an existing link into a single-link input. Into a **multi-input** socket it appends (no replacement); `position` (0 = created first) inserts at that place by unlinking the later links and relinking them, because the sort id is read-only in the API. |
| `unlinkSockets` | tree, `toNode`, `toSocket`, optional `fromNode`, `fromSocket` | Removes links into an input (all, or the one matching). None to remove: `accepted`. |
| `linkNodeGroupAsset` | `library`, `groupName`, optional `link` (default true), optional `localName` | Brings a node group from an allowed library `.blend` into this file (`bpy.data.libraries.load(path, link=link, assets_only=True)`), see "Library node groups". Already present: `accepted`. |
| `queryEvaluated` | `objectName`, optional `frame` | Publishes a `brokkr.blender.evaluated_geometry.v0` record for the object's evaluated result, see "Evaluated read-back". Read-only. |
| `assignNodeTree` | `treeKind` (`geometry`), `treeKey`, `objectName`, optional `modifierName` | Adds or reuses a Geometry Nodes modifier named `modifierName` (default `Brokkr GeoNodes`) on the object and sets its `node_group`. `setModifierInput` below sets its exposed inputs. |
| `setModifierInput` | `objectName`, `modifierName`, `socket` (interface identifier), `value` | Sets a Geometry Nodes modifier input, validated against the group's interface type. **On Blender 5.2.3 the access is `modifier.properties.inputs.<identifier>.value = v` [verified]; `modifier[identifier]` raises (the modifier no longer supports ID properties), so an implementation that follows the documented 4.x idiom fails.** Object/material inputs use the same `value`; attribute-name inputs use `attribute_name`. The adapter then calls `object.update_tag()`: without it a headless re-evaluation returned the previous result **[verified]**. |

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
- `linkSockets` of an existing identical link: `accepted`, no duplicate (Blender itself
  creates none into a multi-input socket **[verified]**). A different source into a
  single-link input replaces the link and says so in the message; into a multi-input socket
  it appends, so a replayed `linkSockets` with a `position` converges by checking whether
  that source already sits at that position.
- `addNodeItem`/`addZone`: an item of that name and type, or a zone whose `inId`/`outId`
  exist and are paired, is `accepted` (`exists`). An item of the same name and another type
  is refused (`item_type_conflict`).
- `linkNodeGroupAsset` of a group already linked from that library: `accepted`. Blender
  logs `ID ... is already linked` for repeated loads **[verified]**; the adapter checks
  `bpy.data.node_groups` first and does not rely on the warning.
- `unlinkSockets` with nothing to remove: `accepted`.
- `createNodeTree`/`createNodeGroup`: same key and kind converges; same key,
  different kind is refused. An existing group's interface is converged by socket
  `identifier`: changed type/default/range updated, missing added, **extra sockets are
  kept unless the intent says `pruneInterface: true`** (removing them unlinks users).
- Command ids already dedupe replays of the same intent at the queue (the drain
  deletes an intent after executing it); id-based convergence covers re-sent intents
  with new command ids, which is the realistic case for a retrying client.

## Zones (simulation, repeat, for-each)

Zones are paired nodes, and without them most generative graphs are inert (the index-of-nearest
and raycast examples are helpers with nothing to drive them). They are in v1 as `addZone` /
`removeZone` plus `addNodeItem` on the zone's output node.

What Blender 5.2.3 does **[verified]**:

- `GeometryNodeRepeatInput`/`Output`, `GeometryNodeSimulationInput`/`Output` and
  `GeometryNodeForeachGeometryElementInput`/`Output` are created separately by `nodes.new`;
  `input.pair_with_output(output)` returns `True` and the input node then reports
  `paired_output`. Before pairing, the two halves have different sockets; after, the input node
  mirrors the output's items. A fresh Repeat/Simulation pair has one item, `Geometry`, as `Item_0`.
- Repeat: the input node's outputs are `Iteration` then the items; its inputs are `Iterations`
  then the items (`Item_0`...). The output node's sockets are the items. Simulation: the input
  node has an output `Delta Time`; the output node has an input `Skip`. Items are added with
  `repeat_items.new(type, name)` / `state_items.new(type, name)` on the **output** node and appear
  on both halves as `Item_N`. For-each has three collections on the output node (`input_items`,
  `main_items`, `generation_items`); only their existence was checked.
- Every zone node carries a trailing virtual socket (`__extend__`, type `NodeSocketVirtual`;
  for-each has `__extend__main`/`__extend__generation`). **Read-back skips virtual sockets**:
  they are not document sockets and cannot be linked to by identifier.
- A link from a repeat input's `Item_0` to its output's `Item_0` is valid.
- A repeat zone ran: a one-vertex mesh through `Set Position (0,0,1)` inside a repeat with
  `Iterations` 3 evaluated to z = 3, then 5 after `setModifierInput` (and `update_tag`).

Not verified: simulation behaviour across frames (the evaluation is stateful and a headless
read-back at frame N needs the frames before it stepped), deletion rules for one half, a for-each
graph that evaluates, whether `pair_with_output` is idempotent on an already-paired node. So
`removeNode` on one half is refused rather than guessed (`zone_half`).

## Library node groups

Blender 5.2 ships node groups as assets in `datafiles/assets/nodes/` under the Blender install
(`geometry_nodes_essentials.blend`, `geometry_nodes_dynamics_assets.blend`) **[verified]**.
`bpy.data.libraries.load(path, link=True, assets_only=True)` listed **28** asset node groups in
essentials (Scatter on Surface, Instance on Elements, Randomize Transforms, Random Rotation,
Array, Curve to Tube, Smooth by Angle, Displace Geometry, Box/Sphere/Normal Selection, Edge
Length, Geometry Input, Capture Rest Geometry, Transform and Project, Project with Depth,
Screen/3D space conversions, the cylindrical/spherical combine and separate helpers, Is Edge
Boundary/Loose/Manifold, Is UV Split, Face Corner Angle) and **6** in dynamics (Set Effector,
Hair Dynamics, Custom Force, Custom Effector, Collider, Cloth Dynamics (Experimental)). The
examples' earlier counts (35 and 59) were a guess at file totals, not the asset list, and are
withdrawn.

`linkNodeGroupAsset` brings one of them into the file:

- **Library argument.** `library` names an allowed library, never a path: the shipped
  `assets/nodes/*.blend` files (resolved from `bpy.utils.system_resource('DATAFILES')`
  **[verified]**) plus the directories in `preferences.filepaths.asset_libraries` (readable;
  one "User Library" on the test machine **[verified]**). The final file is the library
  directory plus a relative name, confined with the same rules `importGltf` uses (no absolute,
  drive, UNC or `..`, resolved path re-checked before use, no symlink out). The allowed set is
  configuration, empty by default except the shipped assets.
- **Loading.** `link=True` (default) keeps the group read-only and tied to the library file
  (`group.library` set, `is_editable` false **[verified]**). `link=False` appends a local editable
  copy (unverified). Dependencies are pulled in: linking `Array` also linked dot-named helper
  groups such as `.curve_UV` and `.half_spheres` **[verified]**; a repeated load logs `already linked`.
- **Use.** A Group node then takes `GroupRef{treeKey, library}`. The linked group's interface
  is readable and its identifiers are opaque `Socket_N` (`Scatter on Surface` exposes `Socket_0`
  for `Mesh`, `Socket_30` for the `Density Method` menu...); the client matches on interface name
  and type from read-back. Its inputs include menu sockets (`NodeSocketMenu`), so `Socket.type`
  carries `Menu` **[verified]**; setting a menu value was not tried. A group node on `Array`
  evaluated to a mesh **[verified]**.
- **Safety.** A `.blend` can carry Python text blocks and drivers. After loading, the adapter
  walks the group and everything it nests and applies the exclusion list (Script nodes,
  file-touching nodes); if anything is excluded it removes the new datablocks and answers
  `node_type_not_allowed` with the offending node. Whether linking can run a library's scripts
  depends on `preferences.filepaths.use_scripts_auto_execute`: refusing to link while that is on
  is the planned guard and is **not verified**. Every node action on a linked tree is refused
  (`tree_read_only`).

## Evaluated read-back

The tree read-back says what was built; it says nothing about what Blender made of it. Every
translation in the VibeGeometry corpus was judged by evaluated counts. `queryEvaluated` makes
Blender evaluate the object (after `view_layer.update()`, optionally at a `frame`) and publishes
`brokkr.blender.evaluated_geometry.v0`, key `blender/evaluated/{objectName}`:

```text
EvaluatedGeometry
  schema, objectName, frame, revision of every tree the object's modifiers use
  mesh           { vertices, edges, faces, corners, bboxMin, bboxMax, attributes: [name] }   present only for a mesh result
  components     names of the non-empty result components (curves, pointcloud, instances, volume ...)
  instances      integer, count of instances (source unverified)
  warnings       [string], node warnings of each Geometry Nodes modifier
```

**[verified 5.2.3]:** a cube graph evaluates to 8/12/6/24 (vertices/edges/faces/corners) via
`object.evaluated_get(depsgraph).to_mesh()`, with attribute names `position`, `.corner_vert`,
`.corner_edge`, `sharp_face`, `.edge_verts`; the evaluated object has `bound_box`; a curve result
has an empty evaluated mesh while `evaluated_geometry()` exposes a curves component;
`modifier.node_warnings` exists (empty); after changing a modifier input headless the result stays
stale until `object.update_tag()` is called. **Not verified:** attribute domain and data type
(only names were read), the instances count, point-cloud and volume counts, grease pencil,
evaluation from a timer in an interactive session (the probe ran `-b`), and frame stepping for
simulations.

Budget: evaluating runs the graph on Blender's main thread and cannot be interrupted, so a heavy
or unbounded graph freezes the host until it finishes. The read is therefore an explicit action
(never part of the periodic snapshot), one object at a time, reads counts through `to_mesh()`
and clears it at once (`to_mesh_clear`), and is refused (`eval_limit`) while an earlier
evaluation of the same object has not returned.

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
| `item_collection_not_allowed` / `item_type_conflict` | `addNodeItem` names a collection not on the node type's allowlist; or an item of that name exists with another type |
| `zone_half` / `zone_unpaired` | `removeNode` on one zone half; `addNodeItem`/links address a zone node whose pair is missing |
| `socket_ambiguous` | an interface **name** matches more than one socket on that side of the group |
| `multi_input_position` | `position` is past the number of links currently in the multi-input socket |
| `library_not_allowed` / `asset_not_found` | `library` is not on the configured allow-list of library files; the library has no asset node group of that name |
| `tree_read_only` | a node action addresses a tree linked from a library |
| `eval_limit` | `queryEvaluated` refused because the evaluation budget rules below say so |
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
   output is already confined. `linkNodeGroupAsset` reads a `.blend` from an allow-listed
   asset library only, never a client-supplied path, and re-applies rules 1 and 4 to the loaded group.
5. **Whole-intent validation first.** No partial application of a refused intent. A
   batch is validated, then applied, and a failure at apply time restores the tree.
6. **Caps.** 500 nodes, 2000 links and 256 ops per batch keep a single intent from
   becoming a resource attack; nested groups are capped at depth 8. Zones add an amplifier
   the structural caps do not see: a Repeat's `Iterations` is data. A literal above 10 000 on a
   Repeat `Iterations` input, or on a short list of known amplifiers (Mesh Grid and Subdivide
   levels, Duplicate Elements amount), is refused (`limit_exceeded`); a value arriving by link or
   by modifier input is not bounded by Brokkr, and evaluation cannot be interrupted
   (see "Evaluated read-back"). That residual risk belongs to Geometry Nodes, not to this
   design, and is stated rather than hidden.
7. **Authority.** These actions ride the same admission path as the other Blender
   intents. The server hardening (optional session token, bind guard, intent purge) is
   unchanged and covers them.

## Testable without Blender, and what needs it

Without Blender (stdlib only, in the style of `server_guard.py` and `scene_actions.py`):

- The graph document types and their canonical (de)serialization, including
  `contentHash` stability under reordering (links into a multi-input socket hash by `order`,
  items by their collection order, not sorted by name).
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
- What `node_graph_probe.py` already covers (item identifiers, zone pairing, a repeat zone
  evaluating, multi-input order, interface structure and default round-trip, a field into a
  group, a linked essentials group evaluating, the modifier input API, evaluated counts) is
  not re-proved by the adapter's live tests; they cover what the adapter adds.
- Round trip: build a tree from actions, read it back, apply the read-back to a fresh
  tree, read again; the two read-backs must be equal. This is the one test that proves
  the document is a faithful model of the tree.

## Version matrix (to verify on a live Blender)

| area | Blender 3.x | 4.0 to 4.x | 5.x |
|---|---|---|---|
| group interface | `tree.inputs/outputs` | `tree.interface.new_socket(...)` | same as 4.x **[verified 5.2.3]**, plus `new_panel`, `structure_type`, `default_input`, `attribute_domain`, `hide_value`; identifiers are `Socket_N` |
| modifier inputs | `modifier[id]` | `modifier[id]` | `modifier.properties.inputs.<id>.value`; `modifier[id]` raises **[verified 5.2.3]**; earlier 5.x unverified |
| item sockets | none | `capture_items.new(type, name)` (4.2+) | **[verified 5.2.3]**; 4.x availability unverified |
| material/world tree | `use_nodes = True` then `node_tree` | same | `use_nodes` is deprecated and trees may always exist; confirm |
| compositor tree | `scene.use_nodes`, `scene.node_tree` | same | the scene's tree becomes a node group on the scene (`compositing_node_group`); confirm |
| geometry nodes zones | none | 3.6 simulation, 4.0 repeat | `pair_with_output`, `repeat_items`/`state_items` **[verified 5.2.3]**; for-each element zone present, only listed |
| library groups | n/a | `bpy.data.libraries.load` | assets under `datafiles/assets/nodes` link and evaluate **[verified 5.2.3]** |

The add-on declares `blender: (4, 0, 0)` today, so v1 supports 4.0+ and answers
`version_unsupported` below it. Only 5.2.3 was run: the 4.x rows, the shader/world/compositor
rows and the "confirm" rows are claims this document could not check. Capture items need 4.2,
repeat zones 4.0 and simulation 3.6 (documented, unverified), so `addNodeItem` and `addZone`
answer `version_unsupported` below those.

## Cut plan

Each cut is its own PR with tests that fail when its rule breaks.

1. **Document and guards, no bpy.** Types (including items, `GroupRef`, interface structure,
   multi-input `order`, evaluated record), canonical form, hash; id/identifier/value
   validation; exclusion and allowlist; caps including the `Iterations` literal cap. Pure tests.
2. **Pure graph engine.** In-memory graph, idempotent apply of the action set including
   `addNodeItem`, `addZone` and multi-input `position` (relink-to-reorder), batch
   validate-then-apply with inverse-op rollback, cycle checks. Pure tests, including replay and
   rollback properties.
3. **Adapter to Blender.** Reads a `bpy` node tree into the document (virtual sockets skipped,
   opaque interface identifiers) and applies ops to it; fake-`bpy` tests; `assignNodeTree`,
   `setModifierInput` through `modifier.properties.inputs`. Read-back publishing.
4. **Live smoke.** Extends `node_graph_probe.py` into the round-trip test; version matrix
   filled for the rows still unverified (4.x, shader/world/compositor).
5. **Library groups and evaluated read-back.** `linkNodeGroupAsset` with library allow-list and
   post-load exclusion scan; `queryEvaluated`. Separate PR: both touch the file system or run
   the graph, so each gets its own safety review.
6. **Node recipes (optional).** Named, tested graph builders (a procedural scatter, a
   PBR material) expressed as documents, so clients do not rediscover identifiers. Promoted from
   optional by example 6 if generated graphs stay large (open question 5).

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
3. **Zone deletion and simulation frames.** Zones are in v1 (`addZone`). Still open:
   whether `removeNode` on one half should be allowed (the design refuses it), and how a
   headless `queryEvaluated` at frame N should step a Simulation zone from its start (the
   probe did not run a simulation).
4. **Where node ids are stored** if a future Blender removes custom properties on
   nodes: fall back to `node.name` only and accept that a UI rename breaks addressing.
5. **Packaging of the exclusion list** as a versioned typed document the daemon can
   read, so the policy is advertised as a capability and not only enforced in the
   add-on.
6. **Authoring at scale** (examples gap 7), **baking and caches** (gap 9) and **drivers and
   keyframes on node values** (gap 10) are not designed here. Gap 7 is the one with a decision
   attached: recipes (cut 6) against `applyNodeGraph` (question 1) for graphs of hundreds of nodes.
7. **Menu-socket values and appended libraries.** `Socket.type` carries `Menu`, but setting a
   menu socket's value (and a group node's menu input) was not run; `linkNodeGroupAsset
   link=false` was not run.

## Verification status

What the headless probe (`surfaces/blender/tests/live/node_graph_probe.py`, Blender 5.2.3 LTS on
Starfire, 37 checks, all passing) established, and what it did not.

| area | verified | not verified |
|---|---|---|
| Item sockets | `capture_items.new('VECTOR','Pos')` creates `Value`/`Attribute`; second item `Value_1`/`Attribute_1`; capture round-trips an attribute | `move`/`remove` of items; menu, index-switch, bundle items |
| Zones | repeat/simulation pairing, `Item_N`, `Iterations`, `Iteration`, `Delta Time`, `Skip`; a repeat zone runs 3 then 5 iterations; for-each collection names | simulation across frames; deleting one half; a running for-each |
| Interface | `structure_type` FIELD, `default_input` POSITION/NORMAL, `hide_value` set and read; panels with `parent`; opaque `Socket_N` identifiers; a field flows into a group's FIELD input | `attribute_domain` effect; a `DYNAMIC` or `GRID` socket |
| Multi-input | `is_multi_input`, `link_limit`, sort ids 0,1,2, read-only sort id, duplicate suppression, reversed result order (ends only) | order of the middle links; reorder via unlink and relink |
| Library | 28 + 6 asset groups listed; link with dependencies; read-only linked group; opaque interface ids incl. Menu; group node evaluates | append (`link=False`); a user library; autoexec guard; menu value setting |
| Evaluated | mesh counts, attribute names, `bound_box`, curves component present, `node_warnings` present, stale until `update_tag` | attribute domain/type, instances count, interactive-session timing |
| Socket facts | Math `Value`/`Value_001`/`Value_002`; Vector Math `Vector`/`Vector_001`/`Vector_002`/`Scale`; Map Range `From_Min_FLOAT3`...; Switch `Switch`/`False`/`True` for FLOAT and GEOMETRY; Compare `A`/`B` for FLOAT and INT; node `parent`, `use_custom_color` and `color` exist; Poisson sockets exist before the property is set and flip `is_unavailable` | most other node types' identifiers |
| Modifier | `modifier.properties.inputs.<id>.value`; `modifier[id]` raises | `bake_*`, panel state setters |
| Not run at all | the add-on, any batch/rollback behaviour, shader/world/compositor trees, Blender 4.x | |
