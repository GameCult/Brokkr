# Blender node graphs: worked examples

Companion to [`blender-node-graphs.md`](blender-node-graphs.md). Real geometry-node
setups, what each does, how it would be expressed as Brokkr node-graph ops, and what
the design could not say. A design gap is marked **GAP** and numbered; the list, with
what each became, is at the end.

**What was run.** The graph shapes come from sources that were run elsewhere (below). On
2026-11-07 the vocabulary was run on Blender 5.2.3 LTS by
[`node_graph_probe.py`](../surfaces/blender/tests/live/node_graph_probe.py) (37 checks, all
pass): socket and item identifiers, a repeat zone, capture items, multi-input order,
interface fields, a linked essentials group, evaluated counts, and example 2's
`boundary_step` built as ops and evaluated. **No op was applied by the Brokkr adapter (there
is none), and examples 1, 3, 4, 5 and 6 as written were not built end to end**; their node
types and the identifiers they use were checked only where an example says so. Socket names
in the listings are display names; the real identifiers equal them except where the notes say
otherwise (Math's repeats are `Value`, `Value_001`; item sockets are `Value_1`; **interface
sockets of a node group are opaque `Socket_N`**, so `gin.Radius` is shorthand for the
identifier the interface assigned).

## Where the setups came from

- **Searched:** `/opt/commons` holds no `.blend`, node-tree JSON or Python node trees.
  The only node-tree files on the machine are Blender 5.2's own asset libraries under
  the Idunn-managed Blender release (`geometry_nodes_essentials.blend`,
  `geometry_nodes_dynamics_assets.blend`; zstd-compressed). Their node-group *names*
  were read; their internals were not decomposed (that needs Blender).
- **VibeGeometry history** (`GameCult/VibeGeometry`, before commit `09bff8c`, "Focus on
  vg-csg"): a translation corpus of public Blender geometry-node files into
  [Geometry Script](https://github.com/carson-katri/geometry-script) Python, each
  verified on **Blender 5.1.1** by comparing evaluated mesh counts against the source
  graph (`docs/research/translations/*.md`, `examples/geometry_script/*.py`). The
  grass tuft, index-of-nearest, labyrinth and raycast setups below are from there. Its
  failure notes are design evidence and are used in the gaps.
- **Not usable as sources:** `GameCult/geometry-script` is the DSL fork, not a graph
  library; the `.blend` files VibeGeometry generated (Aetheria Bloom, Lucent Tether)
  are outputs of Python, discussed in example 6.

## Notation

Ops are written as the design's actions, one per line. A node has an `id` (Brokkr's),
a `blIdname`, node-level `properties`, and literal input defaults. A link is
`from.Socket -> to.Socket`. `gin`/`gout` are the group's Group Input / Group Output
nodes. `ref` is a typed reference by name.

## 1. Grass tuft generator (scatter, instance, capture, deform)

**Source:** Blender demo `instance_attribtues.blend`, group `Grass Tuft Generator`;
Geometry Script recreation verified (45 vertices default, 165 wider and curlier; deltas
0). **Does:** builds a small disc, scatters Poisson points over it (denser near the
centre), instances one tapered blade curve on each point, remembers each instance's root
position before realizing, then bends every blade around its own root (more curl toward
the tip and toward the rim) and turns the curves into thin triangular tubes.

```text
createNodeGroup geometry "Grass Tuft Generator" interface=[
  in  Height  Float 0.2   | in Radius Float 0.05 | in Density Float 1.0
  in  Thickness Float 0.01 | in Curl Float 0.5    | in Seed Int 0
  out Geometry Geometry ]

# seed surface
addNode disc     GeometryNodeMeshCircle        properties{fill_type: TRIANGLE_FAN} inputs{Vertices: 12}
addNode sub      GeometryNodeSubdivideMesh     inputs{Level: 3}
addNode pos1     GeometryNodeInputPosition                          # radial distance
addNode pos2     GeometryNodeInputPosition                          # captured on the instance domain
addNode rlen     ShaderNodeVectorMath          properties{operation: LENGTH}
addNode falloff  ShaderNodeMapRange            properties{data_type: FLOAT, interpolation_type: SMOOTHSTEP, clamp: true}
                                               inputs{"From Min": 0, "To Min": 1.0, "To Max": 0.39}
# points
addNode t2       ShaderNodeMath  properties{operation: MULTIPLY} inputs{Value_001: 2.0}
addNode dmin     ShaderNodeMath  properties{operation: DIVIDE}
addNode dmax     ShaderNodeMath  properties{operation: MULTIPLY} inputs{Value_001: 5000.0}
addNode scatter  GeometryNodeDistributePointsOnFaces properties{distribute_method: POISSON}
# one blade
addNode hvec     ShaderNodeCombineXYZ
addNode spine    GeometryNodeMeshLine  properties{mode: END_POINTS, count_mode: TOTAL}
                                       inputs{Count: 5, "Start Location": [0,0,0]}
addNode tocurve  GeometryNodeMeshToCurve properties{mode: EDGES}
addNode sp       GeometryNodeSplineParameter
addNode taper    ShaderNodeMath  properties{operation: SUBTRACT} inputs{Value: 1.0}
addNode blade    GeometryNodeSetCurveRadius
# instance, scale, remember root, realize
addNode inst     GeometryNodeInstanceOnPoints
addNode scl      GeometryNodeScaleInstances       inputs{"Local Space": true}
addNode cap      GeometryNodeCaptureAttribute     properties{domain: INSTANCE}
addNodeItem cap  capture_items VECTOR "Root"                      # GAP 1 (closed): input Value, output Attribute
addNode real     GeometryNodeRealizeInstances
# curl around each root
addNode rnorm    ShaderNodeVectorMath  properties{operation: NORMALIZE}
addNode tan      ShaderNodeVectorRotate properties{rotation_type: Z_AXIS} inputs{Angle: 1.5708}
addNode rlen2    ShaderNodeVectorMath  properties{operation: LENGTH}
addNode cfall    ShaderNodeMapRange    properties{data_type: FLOAT, interpolation_type: SMOOTHSTEP, clamp: true}
                                       inputs{"From Min": 0, "To Min": 0.2, "To Max": 2.0}
addNode c1       ShaderNodeMath  properties{operation: MULTIPLY}
addNode c2       ShaderNodeMath  properties{operation: MULTIPLY}
addNode sp2      GeometryNodeSplineParameter
addNode pos3     GeometryNodeInputPosition
addNode rot      ShaderNodeVectorRotate properties{rotation_type: AXIS_ANGLE}
addNode setpos   GeometryNodeSetPosition
# tube
addNode prof     GeometryNodeCurvePrimitiveCircle properties{mode: RADIUS} inputs{Resolution: 3}
addNode nattr    GeometryNodeInputNamedAttribute  properties{data_type: FLOAT} inputs{Name: "radius"}
addNode rsw      GeometryNodeSwitch               properties{input_type: FLOAT} inputs{False: 1.0}
addNode c2m      GeometryNodeCurveToMesh          inputs{"Fill Caps": false}
addNode smooth   GeometryNodeSetShadeSmooth       properties{domain: FACE} inputs{"Shade Smooth": false}
addNode mat      GeometryNodeSetMaterial
```

Links (the wiring, about 45; the group inputs fan out):

```text
gin.Radius -> disc.Radius          disc.Mesh -> sub.Mesh
pos1.Position -> rlen.Vector       rlen.Value -> falloff.Value        gin.Radius -> falloff."From Max"
gin.Thickness -> t2.Value          t2.Value -> dmin.Value             gin.Density -> dmin.Value_001
gin.Density -> dmax.Value          sub.Mesh -> scatter.Mesh           dmin.Value -> scatter."Distance Min"
dmax.Value -> scatter."Density Max"  falloff.Result -> scatter."Density Factor"   gin.Seed -> scatter.Seed
gin.Height -> hvec.Z               hvec.Vector -> spine.Offset        spine.Mesh -> tocurve.Mesh
sp.Factor -> taper.Value_001       tocurve.Curve -> blade.Curve       taper.Value -> blade.Radius
scatter.Points -> inst.Points      blade.Curve -> inst.Instance       inst.Instances -> scl.Instances
falloff.Result -> scl.Scale        scl.Instances -> cap.Geometry      pos2.Position -> cap.Value
cap.Geometry -> real.Geometry      cap.Attribute -> rnorm.Vector          rnorm.Vector -> tan.Vector
cap.Attribute -> rlen2.Vector          rlen2.Value -> cfall.Value         gin.Radius -> cfall."From Max"
sp2.Factor -> c1.Value             gin.Curl -> c1.Value_001           c1.Value -> c2.Value
cfall.Result -> c2.Value_001       pos3.Position -> rot.Vector        cap.Attribute -> rot.Center
tan.Vector -> rot.Axis             c2.Value -> rot.Angle              real.Geometry -> setpos.Geometry
rot.Vector -> setpos.Position      gin.Thickness -> prof.Radius       nattr.Exists -> rsw.Switch
nattr.Attribute -> rsw.True        setpos.Geometry -> c2m.Curve       prof.Curve -> c2m."Profile Curve"
rsw.Output -> c2m.Scale            c2m.Mesh -> smooth.Mesh            smooth.Mesh -> mat.Geometry
mat.Geometry -> gout.Geometry
```

About 40 nodes and 45 links; the counts are from reading the script, not from Blender.

**Expressible now:** all of it, with `addNodeItem` for the capture item. **What was
checked and what was not:** the capture item (`capture_items.new('VECTOR', name)` gives input
`Value`, output `Attribute`; a second item gives `Value_1`/`Attribute_1`), a capture of a
position stored back as a named attribute, `Scale Instances.Scale` accepting a float link (it
is a vector socket), and the identifiers of Math/Vector Math/Map Range/Switch used above. The
other ~35 nodes were not instantiated, so their identifiers here are display names taken from
the script; the full graph was not built.

- **GAP 1, item sockets: closed** by `addNodeItem`. VibeGeometry hit this: on Blender 5.1 a
  generic capture call did not create the item, and the verified script adds it explicitly.
- **GAP 3, field sockets: closed in design.** `scatter."Density Factor"`, `scl.Scale`,
  `c2.Value` are fields; Brokkr does not model that, `link.is_valid` decides (field into a
  single-value socket is invalid; checked on `Cube.Size` and `Extrude Mesh.Mesh`). Interface
  sockets carry `structure` and `defaultInput`.
- **GAP 8, evaluated read-back: closed in design** by `queryEvaluated`: VibeGeometry judged
  correctness by evaluated vertex/edge/face counts, and `to_mesh()` counts were read back here.

Ordering note, corrected: `scatter`'s Poisson-only sockets (`Distance Min`, `Density Max`,
`Density Factor`) **exist before** `distribute_method` is set and swap `is_unavailable` with the
random-mode `Density` socket when it changes **[verified]**. So identifiers are stable; what
changes is availability. `addNode` still applies properties before inputs, so that setting an
input on a socket that is unavailable under the old mode is not refused by mistake.

## 2. Index of nearest: constraint helpers for a point simulation

**Source:** Blender demo `index_of_nearest.blend`; helper groups `boundary_step`,
`update_velocity`, `collision_step`, `collider_step`, verified on 5.1.1 by driving each
field output into `Set Position` and comparing point positions. **Does:** keeps points in
a circular table (`boundary_step`), limits and smooths their velocity (`update_velocity`),
pushes a point off its nearest neighbour when they overlap (`collision_step`), and pushes
points out of an obstacle object (`collider_step`). The *main* group wraps these in a
Simulation zone that advances them every frame.

`boundary_step` complete (8 nodes):

```text
createNodeGroup geometry "Boundary Step" interface=[
  in Geometry Geometry | in Vector Vector (0,0,0) | in B Float 0.05 | out Geometry Geometry ]
addNode pos     GeometryNodeInputPosition
addNode rel     ShaderNodeVectorMath properties{operation: SUBTRACT}
addNode dist    ShaderNodeVectorMath properties{operation: LENGTH}
addNode outside FunctionNodeCompare  properties{data_type: FLOAT, mode: ELEMENT, operation: GREATER_THAN}
addNode dir     ShaderNodeVectorMath properties{operation: NORMALIZE}
addNode edge    ShaderNodeVectorMath properties{operation: SCALE}
addNode flat    ShaderNodeVectorMath properties{operation: MULTIPLY} inputs{Vector_001: [1,1,0]}
addNode setpos  GeometryNodeSetPosition
pos.Position->rel.Vector   gin.Vector->rel.Vector_001   rel.Vector->dist.Vector
dist.Value->outside.A      gin.B->outside.B             rel.Vector->dir.Vector
dir.Vector->edge.Vector    gin.B->edge.Scale            edge.Vector->flat.Vector
gin.Geometry->setpos.Geometry  outside.Result->setpos.Selection  flat.Vector->setpos.Position
setpos.Geometry->gout.Geometry
```

(`rel` has two vector inputs, `Vector` and `Vector_001`, hence the identifier suffixes.)

`collision_step` adds `GeometryNodeIndexOfNearest` and `GeometryNodeFieldAtIndex`
(Evaluate at Index) plus a `GeometryNodeInputRadius` field; `collider_step` takes an
object (`ref(object, name)`) through `GeometryNodeObjectInfo`. `update_velocity` has *no
geometry input at all*: it is a pure field function returning a vector.

**Expressible now:** the helper groups, all of them, as plain graphs, and the zone around
them. **Run:** `boundary_step` above was built as ops by the probe (with `Vector Math` operation
set before links, `Vector_001` as the second vector, interface sockets resolved from names to
`Socket_N`) and evaluated on a three-point line (x = 0, 2, 4, B = 0.5): the centre point stayed, the two outside points were pulled to x = 0.5. Its outputs
were not compared to the Blender demo's result, so this shows the ops are valid, not that the
translation is faithful. The other three helpers were not built.

- **GAP 2, zones: closed in design** (`addZone`, `addNodeItem` on the output node, zones are
  v1 in the main doc). The simulation wrapper is, in ops:

```text
addZone simulation inId=simIn outId=simOut          # Simulation Input / Output, paired; item Geometry = Item_0
addNodeItem simOut state_items VECTOR "Velocity"    # adds Item_1 on both halves
gin.Geometry -> simIn.Item_0        simIn.Item_0 -> step.Geometry   step.Geometry -> simOut.Item_0
simOut.Item_0 -> gout.Geometry      simIn."Delta Time" -> (collision step)
```

  The pairing, item identifiers, `Delta Time` and `Skip` sockets were checked; **a simulation
  was not evaluated** (the probe ran a repeat zone instead, 3 then 5 iterations).
- **GAP 3, field-valued group outputs: closed in design.** `update_velocity` returns a field
  and takes field inputs; `InterfaceSocket.structure` (`FIELD` set and read back, a field
  linked into a group's FIELD input and evaluated per element) and `defaultInput` (`POSITION`
  and `NORMAL` set and read back) cover it. A field-valued **output** socket was not built.
- **Harnesses.** VibeGeometry could only observe `update_velocity` by wiring its vector
  into `Set Position` of a test point cloud; with `queryEvaluated` that harness is a normal
  Brokkr test: build, assign, read back counts and the bounding box.

## 3. Raycast minigame: ray pipeline helpers

**Source:** Blender demo `raycast-minigame.blend`; helper groups `Initial Direction`,
`Line to be Casted`, `Cast Rays`. **Does:** makes a ray direction from Euler angles,
builds a polyline of N points starting at a position, then for each bounce casts a ray
from the previous point into a target mesh, places the next point just short of the hit
(0.999 of the distance), reflects the direction off the hit normal and accumulates the
travelled distance.

```text
createNodeGroup shaderGroup "Initial Direction" interface=[in Rotation Vector (0,0,0) | out Direction Vector]
addNode fwd  FunctionNodeInputVector   properties{vector: [1,0,0]}
addNode turn ShaderNodeVectorRotate    properties{rotation_type: EULER_XYZ}
fwd.Vector->turn.Vector   gin.Rotation->turn.Rotation   turn.Vector->gout.Direction
```

`Line to be Casted`: `GeometryNodeCurvePrimitiveLine` (zero length) -> `GeometryNodeSetPosition`
(offset `Start Pos`) -> `GeometryNodeResampleCurve` (count `Line Size`) -> out. `Cast Rays`:
`GeometryNodeSampleIndex` (previous point), `GeometryNodeRaycast` (target geometry from a
`GeometryNodeObjectInfo` of `ref(object, ...)`, ray direction, `Hit Position`/`Normal`/
`Distance`), `ShaderNodeVectorMath` SCALE 0.999, `GeometryNodeSetPosition` at `Hit Index`,
`ShaderNodeVectorMath` REFLECT, `ShaderNodeMath` ADD and `+1` for the index.

**Expressible now:** all three helpers, including the target object, which is a
`ref(object, name)` default on the Object Info node, and the bounce loop as a Repeat zone
(`addZone repeat`; state items for position, direction and distance; `Iterations` = the
bounce count). The repeat mechanics were run (a Set Position repeated 3 and 5 times); **this
graph was not built**, so `Raycast`, `Sample Index` and Object Info identifiers are unchecked.
The Euler/axis `rotation_type` enum values differ by node type and are read from the running
Blender, not assumed. **GAP 2 closed in design.**

## 4. Shortest-path labyrinth

**Source:** Blender demo `labyrinth-shortest_path-simon_thommes.blend`, group `Solvable
Labyrinth Generator`; verified on 5.1.1 (22,730 vertices unsolved, 25,484 solved, deltas
0). **Does:** builds a grid, randomly closes edges, keeps the walkable graph, finds the
shortest path from a start to the farthest reachable point, then builds wall tubes and a
solution tube (revealed by a `Solve` value) with start and end markers.

Stages as ops (the full graph is about 40 nodes; the shape is what matters):

```text
addNode grid   GeometryNodeMeshGrid             # square grid, UVs stored on the corner domain
addNode uv     GeometryNodeStoreNamedAttribute  properties{data_type: FLOAT2, domain: CORNER}
addNode cost   ...random edge costs from edge-neighbour counts + random boolean
addNode sep    GeometryNodeInputEdgeNeighbors ; FunctionNodeRandomValue
addNode paths  GeometryNodeInputShortestEdgePaths   # root = vertex index 0
addNode sel    GeometryNodeEdgePathsToSelection
addNode cap1   GeometryNodeCaptureAttribute  properties{domain: EDGE}    + addNodeItem capture_items BOOLEAN   # GAP 1
addNode carve  GeometryNodeSubdivideMesh -> GeometryNodeDeleteGeometry (selected points)
addNode paths2 GeometryNodeInputShortestEdgePaths (on the carved graph, farthest X point)
addNode curves GeometryNodeEdgePathsToCurves
addNode ends   GeometryNodeInstanceOnPoints (sphere markers) -> capture instance index "Start/End"
addNode trim   GeometryNodeTrimCurve  (Solve) -> capture curve-domain "Path" boolean
addNode fillet GeometryNodeFilletCurve -> GeometryNodeSetCurveRadius -> GeometryNodeCurveToMesh
addNode join   GeometryNodeJoinGeometry   # markers + tubes + base grid
```

**Expressible now, not built.** Every node is a plain node; the sequencing is plain links.
**GAP 1** (capture items, three of them) is `addNodeItem`. **GAP 4** (Join Geometry is a
*multi-input* socket: many links, order meaningful) is closed in design: the socket reports
`is_multi_input`, `linkSockets` appends into it instead of replacing, and `position` reorders.
Checked on 5.2.3: three links gave sort ids 0, 1, 2 in creation order, the sort id is read-only,
an identical second link is not created, and the evaluated result begins with the **last**
linked input (so a client that wants a given geometry first links it last). The labyrinth
graph itself was not built. VibeGeometry's note on this graph is a design requirement for Brokkr:
"anonymous `Value` nodes are easy for converter output to misassign" - a translation
that trusted generated variable names built the right topology at the wrong size. The
document must carry values by node `id` and socket identifier (it does), never by
inferred names.

## 5. Library node groups: scatter, tube, array from Blender's essentials

**Source:** Blender 5.2.3's `geometry_nodes_essentials.blend`, read **by Blender** with
`bpy.data.libraries.load(..., assets_only=True)`: **28** asset node groups, among them `Scatter
on Surface`, `Instance on Elements`, `Randomize Transforms`, `Random Rotation`, `Array`, `Curve
to Tube`, `Smooth by Angle`, `Displace Geometry`, `Box Selection`, `Sphere Selection`, `Normal
Selection`, `Smooth Geometry`, `Project with Depth`, `Is Edge Boundary`, `Is Edge Loose`, `Is
Edge Manifold`, `Is UV Split`, `Edge Length`, `Geometry Input`, `Capture Rest Geometry` and the
cylindrical/spherical combine and separate helpers. `geometry_nodes_dynamics_assets.blend`
lists **6** (Set Effector, Hair Dynamics, Custom Force, Custom Effector, Collider, Cloth
Dynamics (Experimental)). The earlier revision's "35" and "59" (and names such as `Curve UV`,
`XPBD Simulation`, `For Each Typed Bundle`) were not produced by Blender's asset listing
(`Curve UV` is a hidden dot-named helper, not an asset): withdrawn. **Does:** a user composes a scatter in two nodes instead of thirty.

```text
createNodeGroup geometry "Rock Field" interface=[in Geometry Geometry | in Density Float 5 | out Geometry Geometry]
linkNodeGroupAsset library="essentials" groupName="Scatter on Surface"     # GAP 5 (closed)
linkNodeGroupAsset library="essentials" groupName="Random Rotation"
addNode scatter GeometryNodeGroup group{treeKey: "Scatter on Surface", library: "essentials"}
addNode rotate  GeometryNodeGroup group{treeKey: "Random Rotation",   library: "essentials"}
gin.Geometry -> scatter.<identifier of "Mesh">     scatter.<identifier of "Instances"> -> gout.Geometry
assignNodeTree geometry "Rock Field" objectName="Terrain"
```

**Run:** the probe linked `Array` from essentials, instantiated it as a Group node, linked a
cube into its geometry input and its geometry output to the group output, and evaluated a mesh.
Linking `Scatter on Surface` and reading its interface worked; it was not evaluated. Findings
that change the sketch above: the linked group's interface identifiers are opaque (`Socket_0`
is `Mesh`, `Socket_30` is the `Density Method` **menu**), so ops address them by interface name
resolved from read-back; the group is read-only; linking pulls dot-named helper groups with it.
The exact input names of `Scatter on Surface` (`Density`, `Distribution Method`...) were read
from its interface, but `Rock Field` as written was not built.

**GAP 5, closed in design** as `linkNodeGroupAsset`: a library is a configured allow-listed
directory or the shipped `assets/nodes` files, never a client path, with the same confinement
as `importGltf`, and the loaded group is scanned for excluded nodes (Script nodes) before it
is kept.

## 6. Scripted habitats (Aetheria Bloom, Lucent Tether)

**Source:** VibeGeometry's own studies: a rotating-cylinder habitat with spiralling
spokes, terraces, roads and noise-driven slums (`aetheria_bloom_habitat.py`), and a
tethered habitat. **Do:** build a whole station from layered cylindrical coordinates.
They are hundreds of nodes, written as *Python with loops and helper functions*, and
saved as `.blend` outputs.

**Not practical as ops today.** Each node as an op is hundreds of intents; the Python
form is shorter because functions and loops are the compression. Two honest readings:

- The document is the *compiled* form. The authoring tool for large graphs stays a DSL
  like Geometry Script (which runs Python, and so is exactly what Brokkr must not
  expose), and what Brokkr carries is the graph it emits, applied as one `editNodeTree`
  batch. That keeps Python out of the add-on's surface and still lets an agent author.
- **GAP 7, recipes.** The design's optional cut 5 (named graph builders over the
  document) becomes necessary here, not optional: otherwise a client re-derives
  hundreds of nodes per habitat.

## Design gaps found

Status as of the 2026-11-07 revision. "Closed in design" means the main doc now specifies it and
the Blender API behind it was run where the doc says **[verified 5.2.3]**; none is implemented.

| # | gap | seen in | status | where |
|---|---|---|---|---|
| 1 | **Item sockets**: Capture Attribute items, Repeat/Simulation state items, Menu and Index Switch items, Join/Bundle items are grown by the node | 1, 4 | **closed in design.** `addNodeItem`/`removeNodeItem`, `Node.items`; capture and repeat/simulation items verified, menu/index-switch/bundle items not | "Item sockets" |
| 2 | **Zones**: Simulation, Repeat, For Each Element come as paired nodes | 2, 3, essentials | **closed in design, in v1.** `addZone`/`removeZone`, `pairedWith`; repeat evaluated, simulation and for-each not | "Zones" |
| 3 | **Field-ness and implicit defaults** on interface sockets | 1, 2 | **closed in design.** `structure`, `defaultInput`, `attributeDomain`, `hideValue`, panels; verified except `attributeDomain` effect | `InterfaceSocket` |
| 4 | **Multi-input sockets**: many links, order matters | 4 | **closed in design.** `multiInput`, `Link.order`, `linkSockets position`; verified except the middle of the order and reorder-by-relink | "Multi-input sockets" |
| 5 | **Library/asset groups** | 5 | **closed in design.** `linkNodeGroupAsset`, `GroupRef.library`; link and evaluate verified, append and user libraries not | "Library node groups" |
| 6 | **Socket types beyond the list**: Menu, Bundle, Closure, List | essentials | **partly closed.** `Menu` seen on a real interface; `Bundle`/`Closure`/`List` added to `Socket.type` by name only (Closure/List node types exist in the 5.2.3 type list, none instantiated); setting values unverified | `Socket.type` |
| 7 | **Authoring at scale**: hundreds of nodes | 6 | **open.** Recipes (cut 6) against `applyNodeGraph`; no decision | Open questions 1, 6 |
| 8 | **No evaluated read-back** | 1-4 | **closed in design.** `queryEvaluated`, `brokkr.blender.evaluated_geometry.v0`; counts, attribute names, `bound_box` verified | "Evaluated read-back" |
| 9 | **Baking and caches** | 2, essentials | **open, out of scope for v1.** Needs its own action and a confined cache directory; `GeometryNodeBake` exists | non-goals |
| 10 | **Drivers and animation** on node values | common | **open, out of scope** by safety rule 2; keyframes (data only) could be added | non-goals |
| 11 | **Node parenting, frames, colours** | readable graphs | **closed in design.** `Node.parent`, `Node.color`; the properties exist on the node, setting them was not run | `Node` |

New gaps this revision found, none in the original list:

| # | gap | status |
|---|---|---|
| 12 | **Interface identifiers are opaque** (`Socket_N`): group ops cannot address `gin.Radius` | resolved in design: name to identifier at apply time, `socket_ambiguous`, identifiers in read-back |
| 13 | **`modifier[identifier]` does not exist on 5.2.3**: `setModifierInput` as first written would fail | corrected: `modifier.properties.inputs.<id>.value`, plus `update_tag` |
| 14 | **Zone nodes and item nodes carry virtual `__extend__` sockets** that must not enter the document | read-back skips `NodeSocketVirtual` |
| 15 | **Evaluation can run unbounded work** (Repeat `Iterations` is data) | literal cap and an explicit, serialized `queryEvaluated`; link-fed values stay a stated residual risk |

## Lessons carried into the design

- VibeGeometry verified on **Blender 5.1.1**; the probe ran on **5.2.3 LTS** (Steam). Group
  interface through `tree.interface`, explicit capture items and zone pairing now have a 5.2.3
  run behind them; menu socket defaults still need tolerance; nested tree-group references
  behave differently on 4.x (their patch 0001 fixes `Geometry Script` for it), unverified here.
- Verify against *evaluated geometry*, not only the tree (gap 8).
- Address everything by `id` and `identifier`, never by position or generated name
  (example 4).
- Large graphs need a compression layer above the document (example 6, gap 7).
