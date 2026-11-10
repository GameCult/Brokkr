"""Recreate geometry-node setups through the Brokkr scene/object actions and compare with the native result.

  BROKKR_ADDON=<path to surfaces/blender/brokkr_bridge> \
    blender -b --factory-startup --python gn_recreation.py -- result.json

Each setup is built twice: natively (geometry-nodes tree via bpy, evaluated) and through
BrokkrBlenderTarget.execute_command using only the actions that exist. Prints GAP lines where an
action that would be needed is refused or has no effect. Not part of the unittest run (needs Blender).
"""
import bpy, sys, os, json, types, math, random
from pathlib import Path
from mathutils import Vector

ADDON = Path(os.environ["BROKKR_ADDON"]).resolve()
pkg = types.ModuleType("brokkr_bridge"); pkg.__path__ = [str(ADDON)]
sys.modules["brokkr_bridge"] = pkg
from brokkr_bridge import blender_target as bt

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "gn_result.json"
R = {"blender": bpy.app.version_string, "setups": {}, "gaps": {}}

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bt.BrokkrBlenderTarget(bpy)

def act(t, **cmd):
    cmd.setdefault("commandId", "c%d" % act.n); act.n += 1
    return t.execute_command(bpy.context, cmd)
act.n = 0

def gap(key, **detail):
    R["gaps"][key] = detail; print("GAP", key, json.dumps(detail), flush=True)

# --- native helpers ---------------------------------------------------------------------
def tree(name, extra_out=True):
    t = bpy.data.node_groups.new(name, "GeometryNodeTree")
    t.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gout = t.nodes.new("NodeGroupOutput")
    return t, gout

def host(name, gtree, mesh=None):
    me = mesh or bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    m = ob.modifiers.new("GN", "NODES"); m.node_group = gtree
    return ob

def evaluated_instances(ob):
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    return [tuple(round(c, 5) for c in inst.matrix_world.translation) for inst in dg.object_instances if inst.is_instance]

def evaluated_verts(ob):
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    me = ob.evaluated_get(dg).to_mesh()
    v = [tuple(round(c, 5) for c in p.co) for p in me.vertices]; ob.evaluated_get(dg).to_mesh_clear(); return v

def brokkr_positions(prefix):
    bpy.context.view_layer.update()   # matrix_world of the last-edited object is stale until then
    return sorted(tuple(round(c, 5) for c in o.matrix_world.translation) for o in bpy.data.objects if o.name.startswith(prefix))

# =========================================================================================
# 1. Ring of instances (essentials-style array: Mesh Circle -> Instance on Points)
# =========================================================================================
t = reset(); N, RAD = 8, 2.0
g, gout = tree("Ring")
circ = g.nodes.new("GeometryNodeMeshCircle"); circ.inputs["Vertices"].default_value = N; circ.inputs["Radius"].default_value = RAD
cube = g.nodes.new("GeometryNodeMeshCube"); cube.inputs["Size"].default_value = (0.3, 0.3, 0.3)
iop = g.nodes.new("GeometryNodeInstanceOnPoints")
g.links.new(circ.outputs["Mesh"], iop.inputs["Points"]); g.links.new(cube.outputs["Mesh"], iop.inputs["Instance"])
g.links.new(iop.outputs["Instances"], gout.inputs["Geometry"])
ob = host("RingHost", g)
native = sorted(evaluated_instances(ob))
bpy.data.objects.remove(ob)
acts = 0; fails = 0
for i in range(N):
    a = 2 * math.pi * i / N
    r1 = act(t, action="createObject", objectType="MESH", name="Ring.%d" % i, size=0.3); acts += 1
    r2 = act(t, action="setObjectTransform", targetObjectName="Ring.%d" % i, location=[RAD * math.cos(a), RAD * math.sin(a), 0]); acts += 1
    fails += (r1["status"] != "accepted") + (r2["status"] != "accepted")
bro = brokkr_positions("Ring.")
ok = native == bro
R["setups"]["ring"] = {"native_instances": len(native), "brokkr_objects": len(bro), "positions_equal": ok, "actions": acts, "failed_actions": fails}
print("SETUP ring", R["setups"]["ring"]); print("RING native", native); print("RING brokkr", bro)
# size parity
cube_dim = bpy.data.objects["Ring.0"].dimensions[:]
R["setups"]["ring"]["brokkr_object_dimensions"] = [round(d, 4) for d in cube_dim]
# live-ness: the native ring re-evaluates when Count changes; the Brokkr one needs N more actions.
# GAP: any node-graph action
for aname, extra in (("createNodeGroup", {}), ("addModifier", {"modifierType": "NODES"}), ("addNode", {}), ("setModifierInput", {"socket": "Socket_2", "value": 12})):
    r = act(t, action=aname, targetObjectName="Ring.0", **extra)
    R["gaps"].setdefault("no_node_actions", {})[aname] = [r["status"], r["message"]]
print("GAP no_node_actions", R["gaps"]["no_node_actions"])
# GAP: instances need one object each; no instancing/collection-instance action; mesh primitive is cube only
gap("no_primitive_choice", createObject_MESH="always primitive_cube_add; 'size' only",
    repro="createObject objectType=MESH name=C -> verts=%d" % len(bpy.data.objects["Ring.0"].data.vertices))
# GAP: setObjectCustomProperty cannot drive a modifier input
g2, go2 = tree("Param")
circ2 = g2.nodes.new("GeometryNodeMeshCircle")
g2.interface.new_socket("N", in_out="INPUT", socket_type="NodeSocketInt")
gi = g2.nodes.new("NodeGroupInput"); g2.links.new(gi.outputs["N"], circ2.inputs["Vertices"])
g2.links.new(circ2.outputs["Mesh"], go2.inputs["Geometry"])
hob = host("ParamHost", g2)
ident = [s.identifier for s in g2.interface.items_tree if s.item_type == "SOCKET" and s.in_out == "INPUT"][0]
getattr(hob.modifiers["GN"].properties.inputs, ident).__setattr__("value", 5)   # inputs[ident] is a raw IDPropertyGroup with no .value
before = len(evaluated_verts(hob))
r = act(t, action="setObjectCustomProperty", targetObjectName="ParamHost", propertyName=ident, value=12)
after = len(evaluated_verts(hob))
snap = t.capture_snapshot(bpy.context)
ho = [o for o in snap["objects"] if o["name"] == "ParamHost"][0]
gap("custom_property_does_not_drive_modifier", receipt=r["status"], verts_before=before, verts_after=after, identifier=ident,
    snapshot_modifier=ho["modifiers"], snapshot_mesh=ho["mesh"],
    repro="setObjectCustomProperty on a GN host object -> accepted, evaluated vertex count unchanged; snapshot reports base mesh counts and no modifier inputs")
bpy.data.objects.remove(hob)

# =========================================================================================
# 2. Boundary step (example 2): pull points outside radius B back to the circle
# =========================================================================================
t = reset(); B = 0.5; XS = [0.0, 2.0, 4.0]
g, gout = tree("Boundary")
line = g.nodes.new("GeometryNodeMeshLine"); line.inputs["Count"].default_value = 3
line.inputs["Start Location"].default_value = (0, 0, 0); line.inputs["Offset"].default_value = (2, 0, 0)
pos = g.nodes.new("GeometryNodeInputPosition")
dist = g.nodes.new("ShaderNodeVectorMath"); dist.operation = "LENGTH"
cmp_ = g.nodes.new("FunctionNodeCompare"); cmp_.data_type = "FLOAT"; cmp_.operation = "GREATER_THAN"; cmp_.inputs[1].default_value = B
nrm = g.nodes.new("ShaderNodeVectorMath"); nrm.operation = "NORMALIZE"
sc = g.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.inputs["Scale"].default_value = B
sp = g.nodes.new("GeometryNodeSetPosition")
g.links.new(pos.outputs[0], dist.inputs[0]); g.links.new(dist.outputs["Value"], cmp_.inputs[0])
g.links.new(pos.outputs[0], nrm.inputs[0]); g.links.new(nrm.outputs[0], sc.inputs[0])
g.links.new(line.outputs["Mesh"], sp.inputs["Geometry"]); g.links.new(cmp_.outputs["Result"], sp.inputs["Selection"])
g.links.new(sc.outputs[0], sp.inputs["Position"]); g.links.new(sp.outputs["Geometry"], gout.inputs["Geometry"])
ob = host("BoundaryHost", g); native = sorted(evaluated_verts(ob)); bpy.data.objects.remove(ob)
acts = 0
for i, x in enumerate(XS):
    v = Vector((x, 0, 0)); nv = v if v.length <= B else v.normalized() * B   # the *client* does the field math
    act(t, action="createObject", objectType="EMPTY", name="P.%d" % i); act(t, action="setObjectTransform", targetObjectName="P.%d" % i, location=list(nv)); acts += 2
bro = brokkr_positions("P.")
R["setups"]["boundary_step"] = {"native": native, "brokkr": bro, "equal": native == bro, "actions": acts,
                                "note": "equality needs the client to evaluate the field; Brokkr only carries the result"}
print("SETUP boundary_step", R["setups"]["boundary_step"])
gap("no_field_evaluation", repro="no action takes an expression/field; boundary_step's per-element rule must be computed by the caller and sent as N setObjectTransform")

# =========================================================================================
# 3. Seeded scatter (grass-tuft front half): Distribute Points on Faces -> Instance on Points
# =========================================================================================
t = reset(); SEED = 7
g, gout = tree("Scatter")
grid = g.nodes.new("GeometryNodeMeshGrid"); grid.inputs["Size X"].default_value = 3; grid.inputs["Size Y"].default_value = 3
dis = g.nodes.new("GeometryNodeDistributePointsOnFaces"); dis.distribute_method = "RANDOM"
dis.inputs["Density"].default_value = 4; dis.inputs["Seed"].default_value = SEED
cone = g.nodes.new("GeometryNodeMeshCone"); cone.inputs["Radius Bottom"].default_value = 0.05; cone.inputs["Depth"].default_value = 0.4
iop = g.nodes.new("GeometryNodeInstanceOnPoints")
g.links.new(grid.outputs["Mesh"], dis.inputs["Mesh"]); g.links.new(dis.outputs["Points"], iop.inputs["Points"])
g.links.new(cone.outputs["Mesh"], iop.inputs["Instance"]); g.links.new(iop.outputs["Instances"], gout.inputs["Geometry"])
ob = host("ScatterHost", g); native = sorted(evaluated_instances(ob))
# what Brokkr can see of that object
snap = t.capture_snapshot(bpy.context); so = [o for o in snap["objects"] if o["name"] == "ScatterHost"][0]
gap("snapshot_not_evaluated", brokkr_sees=so["mesh"], modifiers=so["modifiers"], evaluated_instances=len(native),
    repro="host object with Distribute->InstanceOnPoints: snapshot mesh.vertexCount=0, no instance count, no positions")
# (a) replay the native points through actions (needs a side channel that is not Brokkr)
bpy.data.objects.remove(ob); acts = 0
for i, p in enumerate(native):
    act(t, action="createObject", objectType="MESH", name="S.%d" % i, size=0.1); act(t, action="setObjectTransform", targetObjectName="S.%d" % i, location=list(p)); acts += 2
R["setups"]["scatter_replay"] = {"native_instances": len(native), "equal": brokkr_positions("S.") == native, "actions": acts,
                                  "note": "positions were read with bpy depsgraph, not through any Brokkr surface"}
# (b) recreate from the seed with the caller's own RNG: does not match Blender's point hash
random.seed(SEED)
mine = sorted((round(random.uniform(-1.5, 1.5), 5), round(random.uniform(-1.5, 1.5), 5), 0.0) for _ in native)
R["setups"]["scatter_own_rng"] = {"count_equal": len(mine) == len(native), "positions_equal": mine == [(a, b, 0.0) for a, b, _ in native] or mine == native}
print("SETUP scatter", R["setups"]["scatter_replay"], R["setups"]["scatter_own_rng"])
gap("no_seed_parity", repro="Distribute Points on Faces seed=7 density=4 on a 3x3 grid: positions are Blender's hash; only reading them back (not offered) reproduces them")
# --- render check: the Brokkr scene still renders under the existing actions
act(t, action="createObject", objectType="CAMERA", name="Cam", location=[0, -6, 4]); act(t, action="setCamera", targetObjectName="Cam", active=True, lens=35)
os.makedirs(os.environ.get("BROKKR_RUN", "."), exist_ok=True)
t.configure_action_dirs(os.environ.get("BROKKR_RUN", "."), os.environ.get("BROKKR_RUN", "."))
r = act(t, action="renderStill", outputPath="scatter_replay.png", engine="BLENDER_WORKBENCH", resolutionX=64, resolutionY=64, cameraName="Cam")
R["setups"]["scatter_replay"]["render"] = [r["status"], r["message"]]
json.dump(R, open(out, "w"), indent=1, default=str)
print("DONE", out)
