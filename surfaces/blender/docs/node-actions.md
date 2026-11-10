# Geometry node graph actions

Command intents (`brokkr.blender.command_intent.v0`) that build and drive a Geometry Nodes graph.
Owner: `brokkr_bridge/node_actions.py`; the target only dispatches. Every field is validated before
`bpy` is touched; a refused intent is a `failed` receipt naming the rule and leaves the tree as it was.
Design and the parts not built yet: `docs/blender-node-graphs.md` (on `libby/blender-node-graphs-design`).

| action | fields | rule |
|---|---|---|
| `createNodeGroup` | `treeKey`, `interface` `[{inOut, name, type, default?}]` | New geometry node group with `gin` and `gout` nodes. Types: Geometry, Float, Int, Bool, Vector. Refuses an existing group. The receipt lists the interface identifiers (`Socket_N`). |
| `addNode` | `treeKey`, `id`, `blIdname`, `location?`, `label?`, `properties?`, `inputs?` | `id` is Brokkr's key (stored as the node's `brokkr_id`). Type must be a `GeometryNode*`, `FunctionNode*` or `ShaderNode*` name that is not an importer, exporter, script, bake, group, zone, viewer or image-texture node. Properties are enum/bool/int/float node settings (set first, they decide which sockets exist); inputs are unlinked defaults (float, int, bool, vector, colour). At most 500 nodes per group. |
| `linkSockets` | `treeKey`, `fromNode`, `fromSocket`, `toNode`, `toSocket` | Sockets by identifier, or by display name when exactly one available socket has it (Group Input/Output sockets are addressed by interface name). A link Blender calls invalid (field into a single value, type mismatch) is removed and refused. |
| `addModifier` | `objectName`, `treeKey`, `modifierName?` (default `Brokkr GeoNodes`) | `NODES` only. Reuses a modifier of that name; at most 8 per object. |
| `setModifierInput` | `objectName`, `modifierName?`, `socket` (identifier or unique interface name), `value` | Float, Int, Bool, Vector inputs. Written as `getattr(modifier.properties.inputs, id).value = v` (indexing `inputs[id]` yields a raw ID property group without `.value` on 5.2.3), then `object.update_tag()`. |

`setObjectCustomProperty` refuses a property named like an input of a Geometry Nodes modifier on that
object (it never drove the modifier); other custom properties are unchanged.

The host snapshot's object entries carry `evaluated` for mesh objects with modifiers: vertex, edge and
polygon counts, `instanceCount`, bounds, and up to 256 vertex and instance locations (`truncated` when cut).
It is the evaluated result; `mesh` stays the base mesh.

Not built: zones, item sockets, multi-input ordering, removal and unlink actions, library groups,
group-in-group nodes, batches/rollback across intents, an expectedRevision check. Residual risk: values
that make evaluation expensive (a huge `Vertices` count) are bounded only to +-1e9; the snapshot evaluates
every object with modifiers each time it runs.

Live proof: `tests/live/gn_actions.py` (Blender 5.2.3, headless). Unit tests: `tests/test_node_actions.py`.
