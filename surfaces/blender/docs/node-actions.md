# Geometry node graph actions

Command intents (`brokkr.blender.command_intent.v0`) that build and drive a Geometry Nodes graph.
Owner: `brokkr_bridge/node_actions.py`; the target only dispatches. Every field is validated before
`bpy` is touched; a refused intent is a `failed` receipt naming the rule and leaves the tree as it was.
Design and the parts not built yet: the design document lives in PR #3 (branch `libby/blender-node-graphs-design`), not in this tree.

| action | fields | rule |
|---|---|---|
| `createNodeGroup` | `treeKey`, `interface` `[{inOut, name, type, default?}]` | New geometry node group with `gin` and `gout` nodes. Types: Geometry, Float, Int, Bool, Vector. Refuses an existing group. The receipt lists the interface identifiers (`Socket_N`). |
| `addNode` | `treeKey`, `id`, `blIdname`, `location?`, `label?`, `properties?`, `inputs?` | `id` is Brokkr's key (stored as the node's `brokkr_id`). Type must be a `GeometryNode*`, `FunctionNode*` or `ShaderNode*` name that is not an importer, exporter, script, bake, group, zone, viewer or image-texture node. Properties are enum/bool/int/float node settings (set first, they decide which sockets exist); inputs are unlinked defaults (float, int, bool, vector, colour). At most 500 nodes per group. |
| `removeNode` | `treeKey`, `id` | Removes the node and its links. Absent id: accepted. `gin` and `gout` stay. |
| `linkSockets` | `treeKey`, `fromNode`, `fromSocket`, `toNode`, `toSocket` | Sockets by identifier, or by display name when exactly one available socket has it (Group Input/Output sockets are addressed by interface name). A link Blender calls invalid (field into a single value, type mismatch) is removed and refused, and the single link it displaced is put back. A valid link into a single-link input replaces the old one (Blender's behaviour); a link that would close a cycle, or link a node to itself, is refused before Blender is asked. |
| `unlinkSockets` | `treeKey`, `toNode`, `toSocket`, `fromNode?`, `fromSocket?` | Removes the links into an input, or only the one from the given source. None to remove: accepted. |
| `addModifier` | `objectName`, `treeKey`, `modifierName?` (default `Brokkr GeoNodes`) | `NODES` only. Reuses a modifier of that name; at most 8 per object. |
| `removeModifier` | `objectName`, `modifierName?` | Geometry Nodes modifiers only (a Subdivision or other modifier is refused). Absent: accepted. |
| `setModifierInput` | `objectName`, `modifierName?`, `socket` (identifier or unique interface name), `value` | Float, Int, Bool, Vector inputs. Written as `getattr(modifier.properties.inputs, id).value = v` (indexing `inputs[id]` yields a raw ID property group without `.value` on 5.2.3), then `object.update_tag()`. |

`setObjectCustomProperty` refuses a property whose name is the identifier (`Socket_N`) of an input of a Geometry
Nodes modifier on that object; a custom property never drives a modifier input. A name that only equals an
input's display name is an ordinary custom property.

The host snapshot's object entries carry `evaluated` for mesh objects with modifiers: vertex, edge and
polygon counts, `instanceCount`, and up to 256 vertex and instance locations (`truncated` when cut). Vertex
positions and `vertexBounds*` are in the object's local space; instance locations and `instanceBounds*` are
world space. Above 1,000,000 vertices only counts are read (`positionsSkipped`); a non-finite coordinate sets
`nonFinite` and drops the positions and bounds. The instances come from one depsgraph scan per capture.
`instancesComplete` is false when the depsgraph scan stopped at 100,000 items (`instanceCount` and the instance bounds are then lower bounds); the scan is what costs time (about 5 microseconds per instance in Python), so a 2000 x 2000 grid instanced on points captures in 1.4 s on the test machine where an unbounded scan took 22 s. `instanceCount` is `null` for an object the stopped scan never reached (unknown, not zero); the 100,000 budget is shared across all objects in depsgraph order, so a host after a heavy one can be starved. Otherwise `instanceCount` counts evaluated instances whose parent is the object, so a curve, point or volume result
also reads as one instance. `mesh` stays the base mesh.

Known edges: a node duplicated by hand copies its `brokkr_id`, so id lookups act on the first match; `gin`/`gout` are protected by id, and a group whose output node was deleted by hand cannot get a new one through `addNode`; removing a group's last modifier does not delete the group (it may stay in the file until it is saved and reloaded; `addModifier` can reuse it); `removeModifier` takes any modifier name Blender allows because it only looks the modifier up.

Not built: zones, item sockets, multi-input ordering, library groups, group-in-group nodes, batches/rollback across
intents, an expectedRevision check, per-node cost estimates. Int values are capped at +-4096 and floats at +-1e9,
which bounds a request but not the cost of a graph: Blender evaluates what it is given, and the snapshot evaluates
every mesh with modifiers on each capture (mesh grids measured: 16.7M vertices evaluate and read in 0.4 s).
`addModifier` refuses object types that take no modifiers.

Live proof: `tests/live/gn_actions.py` (Blender 5.2.3, headless). Unit tests: `tests/test_node_actions.py`.
