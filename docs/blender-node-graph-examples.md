# Blender node graphs: worked examples

Companion to [`blender-node-graphs.md`](blender-node-graphs.md). Real geometry-node
setups, what each does, how it would be expressed as Brokkr node-graph ops, and what
the design cannot yet say. Nothing here was run in Blender: the graph shapes come from
sources that were (below), the socket names are Blender's display names written where
the real **identifiers** must be read back first (identifiers are usually equal to the
names, with `_001` suffixes on repeats such as Math's three `Value` inputs), and no op
was applied to a live tree. A design gap is marked **GAP** and numbered; the list is at
the end.

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
addNode pos1     GeometryNodeInputPosition
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
addItem cap      VECTOR "Value"                                   # GAP 1: not an action yet
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

Links (the wiring, 44 in all; the group inputs fan out):

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
cap.Geometry -> real.Geometry      cap.Value -> rnorm.Vector          rnorm.Vector -> tan.Vector
cap.Value -> rlen2.Vector          rlen2.Value -> cfall.Value         gin.Radius -> cfall."From Max"
sp2.Factor -> c1.Value             gin.Curl -> c1.Value_001           c1.Value -> c2.Value
cfall.Result -> c2.Value_001       pos3.Position -> rot.Vector        cap.Value -> rot.Center
tan.Vector -> rot.Axis             c2.Value -> rot.Angle              real.Geometry -> setpos.Geometry
rot.Vector -> setpos.Position      gin.Thickness -> prof.Radius       nattr.Exists -> rsw.Switch
nattr.Attribute -> rsw.True        setpos.Geometry -> c2m.Curve       prof.Curve -> c2m."Profile Curve"
rsw.Output -> c2m.Scale            c2m.Mesh -> smooth.Mesh            smooth.Mesh -> mat.Geometry
mat.Geometry -> gout.Geometry
```

(`pos2` is a third `GeometryNodeInputPosition` evaluated on the instance domain; it and
the omitted node lines follow the same pattern.) About 38 nodes and 44 links.

**Expressible:** everything except the capture item. **Needs:**

- **GAP 1, item sockets.** Capture Attribute's `Value` is an *item* the node grows
  (`capture_items.new(type, name)`), not a property or an input default. VibeGeometry
  hit this directly: on Blender 5.1 a generic capture call did not create the item, and
  the verified script adds it explicitly. The design's `setNodeProperty` cannot make it.
- **GAP 3, field sockets.** `scatter."Density Factor"`, `scl.Scale`, `c2.Value` are
  *fields*; whether a socket accepts one, and an interface socket's field-ness, is not
  in the document.
- **Verification.** VibeGeometry judged correctness by evaluated vertex/edge/face
  counts. The design has no way to read the evaluated result (**GAP 8**).

Ordering note: `scatter` has Poisson-only sockets (`Distance Min`, `Density Max`) that
exist only after `distribute_method` is set, so `addNode` must apply properties before
inputs (the design already says so) and the client must treat identifiers as valid only
after the properties are applied.

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

**Expressible:** the helper groups, all of them, as plain graphs. **Needs:**

- **GAP 2, zones.** The thing that makes them a simulation (Simulation Input/Output, or
  Repeat) is excluded in v1. Without it the helpers are inert; with it they are the
  point of the setup.
- **GAP 3, field-valued group outputs.** `update_velocity` returns a field and takes
  field inputs. An interface socket must say its structure (single value, field, or
  dynamic) and may default to an implicit field such as `POSITION`.
- **Harnesses.** VibeGeometry could only observe `update_velocity` by wiring its vector
  into `Set Position` of a test point cloud; the same trick is how any Brokkr test of a
  field-only group works (**GAP 8** again).

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

**Expressible:** all three helpers. **Needs:** **GAP 2** (one Cast Rays per bounce lives
in a Repeat zone in the full graph); **GAP 6** for the object reference
(`ref(object)` is in the design, but an Object Info node's *object* input is a socket
default the document must type as a reference, which it does, so this one is covered);
the legacy **Euler vector socket** `rotation_type` enum differs by node type (verify).

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
addNode cap1   GeometryNodeCaptureAttribute  properties{domain: EDGE}    + addItem BOOLEAN   # GAP 1
addNode carve  GeometryNodeSubdivideMesh -> GeometryNodeDeleteGeometry (selected points)
addNode paths2 GeometryNodeInputShortestEdgePaths (on the carved graph, farthest X point)
addNode curves GeometryNodeEdgePathsToCurves
addNode ends   GeometryNodeInstanceOnPoints (sphere markers) -> capture instance index "Start/End"
addNode trim   GeometryNodeTrimCurve  (Solve) -> capture curve-domain "Path" boolean
addNode fillet GeometryNodeFilletCurve -> GeometryNodeSetCurveRadius -> GeometryNodeCurveToMesh
addNode join   GeometryNodeJoinGeometry   # markers + tubes + base grid
```

**Expressible:** every node is a plain node; the sequencing is plain links.
**Needs:** **GAP 1** (capture items, three of them), **GAP 4** (Join Geometry is a
*multi-input* socket: many links into one socket, where order is meaningful, and the
design says a link "replaces an existing link into a single-link input", which is wrong
for this socket). VibeGeometry's note on this graph is a design requirement for Brokkr:
"anonymous `Value` nodes are easy for converter output to misassign" - a translation
that trusted generated variable names built the right topology at the wrong size. The
document must carry values by node `id` and socket identifier (it does), never by
inferred names.

## 5. Library node groups: scatter, tube, array from Blender's essentials

**Source:** Blender 5.2's `geometry_nodes_essentials.blend` ships these as node groups
(names read from the file): `Scatter on Surface`, `Instance on Elements`, `Randomize
Transforms`, `Random Rotation`, `Array`, `Curve to Tube`, `Smooth by Angle`, `Displace
Geometry`, `Box Selection`, `Sphere Selection`, `Normal Selection`, `Smooth Geometry`,
`Project with Depth`, `Screen to 3D Space`, `Curve UV`, `Is Edge Boundary`, `Is Edge
Loose`, `Is Edge Manifold`, `Is Edge UV Seam`, and cylindrical/spherical combine and
separate helpers (35 groups). `geometry_nodes_dynamics_assets.blend` ships 59 more
(XPBD Simulation, Collider, Gravity, Pin Positions, Hair Dynamics, Edge Length
Constraint, `For Each Sim Geometry`, `For Each Typed Bundle`). **Does:** a user
composes a scatter in two nodes instead of thirty.

```text
createNodeGroup geometry "Rock Field" interface=[in Geometry Geometry | in Density Float 5 | out Geometry Geometry]
addNode scatter GeometryNodeGroup group="Scatter on Surface"      # a library group, not in this file
addNode rotate  GeometryNodeGroup group="Random Rotation"
gin.Geometry->scatter.Geometry   gin.Density->scatter.Density   scatter.Geometry->gout.Geometry
assignNodeTree geometry "Rock Field" objectName="Terrain"
```

**Needs:** **GAP 5.** The design lets a group node reference only a tree that exists in
the current file (`group_not_found` otherwise). Blender's essentials are *assets in a
library*: the group must first be linked or appended. An action that links a named
asset from a configured asset library is the highest-value missing piece for geometry
nodes: it turns the 35 essentials into building blocks. It is also a file read, so it
takes the same confinement as `importGltf` (the asset library is a configured directory,
or the Blender-shipped essentials path).

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

| # | gap | seen in | smallest fix |
|---|---|---|---|
| 1 | **Item sockets**: Capture Attribute items, Repeat/Simulation state items, Menu and Index Switch items, Join/Bundle items are grown by the node, not set as properties | 1, 4 | `addNodeItem` (`nodeId`, `kind`, `socketType`, `name`) in the batch; items appear in the document as ordered `items`; identifiers valid only after |
| 2 | **Zones**: Simulation, Repeat, For Each Element come as paired input/output nodes; no action pairs them | 2, 3, essentials | A `addZone` op that creates the pair and links the state items; read-back carries `pairedWith` |
| 3 | **Field-ness and implicit defaults**: whether a socket takes a field, and an interface socket's structure, default input (`POSITION`, `NORMAL`, `INDEX`), domain, hide-value, panels | 1, 2 | Extend `InterfaceSocket` with `structure`, `defaultInput`, `attributeDomain`, `hideValue`, `panel` |
| 4 | **Multi-input sockets** (Join Geometry): many links, order matters, the replace rule is wrong | 4 | `Socket.multiInput`; `linkSockets` takes `position`; no replace on multi-input sockets |
| 5 | **Library/asset groups**: essentials are linked assets, not present in the file | 5 | `linkNodeGroupAsset` from a configured asset-library directory, confined like `importGltf` |
| 6 | **Socket types beyond the design's list**: Menu (enum-valued socket; VibeGeometry's third patch "tolerate menu socket defaults"), Bundle, Closure, List | essentials (`For Each Typed Bundle`, `String to List`) | Add `menu`, `bundle`, `closure`, `list` to `Socket.type` and `Value` (menu as `enum`) |
| 7 | **Authoring at scale**: hundreds of nodes; the DSL compresses with loops | 6 | Recipes (cut 5) promoted to required; batch size cap raised for generated graphs, or documents applied by `applyNodeGraph` |
| 8 | **No evaluated read-back**: VibeGeometry verified every translation by evaluated vertex/edge/face counts; the design reads only the tree | 1-4 | `queryEvaluatedGeometry`: counts per component, bounding box, attribute names, for an object's evaluated result |
| 9 | **Baking and caches** (Bake node, simulation bake, geometry caches in the dynamics assets) | 2, essentials | Out of scope for v1; needs its own action and a confined cache directory |
| 10 | **Drivers and animation** on node values (a keyframed `Value` node is how many setups animate) | common | Out of scope by safety rule 2; keyframes (data only) could be added without drivers |
| 11 | **Node parenting and frames, labels, colours**: `NodeFrame` is allowed but `Node` has no `parent` or colour | readable graphs | Add `parent`, `color` to `Node` |

## Lessons carried into the design

- VibeGeometry verified on **Blender 5.1.1**; the machine here has **5.2.3 LTS** (Steam).
  The design's version matrix still says "confirm" for the 5.x rows; these sources
  support: group interface through `tree.interface`, capture items explicit, menu
  socket defaults need tolerance, nested tree-group references behave differently on 4.x
  (their patch 0001 fixes `Geometry Script` for it).
- Verify against *evaluated geometry*, not only the tree (gap 8).
- Address everything by `id` and `identifier`, never by position or generated name
  (example 4).
- Large graphs need a compression layer above the document (example 6, gap 7).
