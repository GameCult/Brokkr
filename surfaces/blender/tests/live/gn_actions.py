"""Live proof of the node-graph actions: rebuild three geometry-node setups through Brokkr actions only.

  BROKKR_ADDON=<path to surfaces/blender/brokkr_bridge> \
    blender -b --factory-startup --python gn_actions.py -- result.json

Each native tree is built with bpy as the reference and evaluated with the depsgraph. The Brokkr side
uses BrokkrBlenderTarget.execute_command for every build step and capture_snapshot().objects[].evaluated
for every read: no bpy call touches the Brokkr-built scene except the harness's own reference trees.
Exit status is non-zero if any check fails.
"""
import bpy, sys, os, json, types, math
from pathlib import Path

ADDON = Path(os.environ["BROKKR_ADDON"]).resolve()
pkg = types.ModuleType("brokkr_bridge"); pkg.__path__ = [str(ADDON)]
sys.modules["brokkr_bridge"] = pkg
from brokkr_bridge import blender_target as bt

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "gn_actions_result.json"
R = {"blender": bpy.app.version_string, "checks": []}

def check(name, ok, detail=None):
    R["checks"].append({"name": name, "ok": bool(ok), "detail": detail}); print("CHECK", "ok  " if ok else "FAIL", name, detail if not ok else "", flush=True)

def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bt.BrokkrBlenderTarget(bpy)

N = [0]
def act(t, **cmd):
    N[0] += 1; cmd.setdefault("commandId", "c%d" % N[0])
    r = t.execute_command(bpy.context, cmd)
    if r["status"] != "accepted": print("REFUSED", cmd["action"], r["message"], flush=True)
    return r

def ok(t, **cmd):
    r = act(t, **cmd); check("%s %s" % (cmd["action"], cmd.get("id") or cmd.get("treeKey") or cmd.get("objectName") or ""), r["status"] == "accepted", r["message"]); return r

def evaluated(t, name):
    snap = t.capture_snapshot(bpy.context)
    return [o for o in snap["objects"] if o["name"] == name][0]["evaluated"]

def native_tree(build):
    g = bpy.data.node_groups.new("native", "GeometryNodeTree")
    g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gout = g.nodes.new("NodeGroupOutput"); build(g, gout)
    me = bpy.data.meshes.new("nm"); ob = bpy.data.objects.new("native_host", me); bpy.context.scene.collection.objects.link(ob)
    ob.modifiers.new("GN", "NODES").node_group = g
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    ev = ob.evaluated_get(dg); m = ev.to_mesh()
    verts = sorted(tuple(round(c, 5) for c in v.co) for v in m.vertices); ev.to_mesh_clear()
    inst = sorted(tuple(round(c, 5) for c in i.matrix_world.translation) for i in dg.object_instances if i.is_instance)
    bpy.data.objects.remove(ob); bpy.data.node_groups.remove(g); bpy.data.meshes.remove(me)
    return verts, inst

def srt(rows): return sorted(tuple(r) for r in rows)

def host(t, name, tree, mod="GN"):
    ok(t, action="createObject", objectType="MESH", name=name)
    ok(t, action="addModifier", objectName=name, modifierName=mod, treeKey=tree)

def graph(t, tree, interface, nodes, links):
    ok(t, action="createNodeGroup", treeKey=tree, interface=interface)
    for n in nodes: ok(t, action="addNode", treeKey=tree, **n)
    for a, b, c, d in links: ok(t, action="linkSockets", treeKey=tree, fromNode=a, fromSocket=b, toNode=c, toSocket=d)

GEO_OUT = [{"inOut": "OUTPUT", "name": "Geometry", "type": "Geometry"}]

# ---- 1. ring of instances
def ring(g, gout):
    c = g.nodes.new("GeometryNodeMeshCircle"); c.inputs["Vertices"].default_value = 8; c.inputs["Radius"].default_value = 2.0
    cu = g.nodes.new("GeometryNodeMeshCube"); cu.inputs["Size"].default_value = (0.3, 0.3, 0.3)
    i = g.nodes.new("GeometryNodeInstanceOnPoints")
    g.links.new(c.outputs["Mesh"], i.inputs["Points"]); g.links.new(cu.outputs["Mesh"], i.inputs["Instance"]); g.links.new(i.outputs["Instances"], gout.inputs["Geometry"])
nv, ni = native_tree(ring)
t = fresh(); N[0] = 0
graph(t, "Ring", GEO_OUT,
      [dict(id="circle", blIdname="GeometryNodeMeshCircle", inputs={"Vertices": 8, "Radius": 2.0}),
       dict(id="cube", blIdname="GeometryNodeMeshCube", inputs={"Size": [0.3, 0.3, 0.3]}),
       dict(id="iop", blIdname="GeometryNodeInstanceOnPoints")],
      [("circle", "Mesh", "iop", "Points"), ("cube", "Mesh", "iop", "Instance"), ("iop", "Instances", "gout", "Geometry")])
host(t, "RingHost", "Ring")
ev = evaluated(t, "RingHost")
check("ring instances equal native", srt(ev["instanceLocations"]) == ni and ev["instanceCount"] == 8, {"brokkr": ev["instanceLocations"], "native": ni})
# parameter change by setModifierInput on an exposed input: rebuild with an exposed Count
t = fresh()
graph(t, "RingN", GEO_OUT + [{"inOut": "INPUT", "name": "Count", "type": "Int", "default": 8}],
      [dict(id="circle", blIdname="GeometryNodeMeshCircle", inputs={"Radius": 2.0}),
       dict(id="cube", blIdname="GeometryNodeMeshCube"), dict(id="iop", blIdname="GeometryNodeInstanceOnPoints")],
      [("gin", "Count", "circle", "Vertices"), ("circle", "Mesh", "iop", "Points"), ("cube", "Mesh", "iop", "Instance"), ("iop", "Instances", "gout", "Geometry")])
host(t, "RingHost", "RingN")
before = evaluated(t, "RingHost")["instanceCount"]
ok(t, action="setModifierInput", objectName="RingHost", modifierName="GN", socket="Count", value=12)
after = evaluated(t, "RingHost")["instanceCount"]
check("setModifierInput changes evaluated instances", (before, after) == (8, 12), (before, after))
r = act(t, action="setObjectCustomProperty", targetObjectName="RingHost", propertyName="Count", value=3)
check("custom property on a modifier input is refused", r["status"] == "failed" and "setModifierInput" in r["message"], r["message"])
check("refused custom property changed nothing", evaluated(t, "RingHost")["instanceCount"] == 12)
r = act(t, action="setObjectCustomProperty", targetObjectName="RingHost", propertyName="tag", value=3)
check("other custom properties still accepted", r["status"] == "accepted", r["message"])

# ---- 2. boundary step
B = 0.5
def boundary(g, gout):
    ln = g.nodes.new("GeometryNodeMeshLine"); ln.inputs["Count"].default_value = 3; ln.inputs["Offset"].default_value = (2, 0, 0)
    pos = g.nodes.new("GeometryNodeInputPosition")
    d = g.nodes.new("ShaderNodeVectorMath"); d.operation = "LENGTH"
    c = g.nodes.new("FunctionNodeCompare"); c.data_type = "FLOAT"; c.operation = "GREATER_THAN"; c.inputs["B"].default_value = B
    nm = g.nodes.new("ShaderNodeVectorMath"); nm.operation = "NORMALIZE"
    sc = g.nodes.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.inputs["Scale"].default_value = B
    sp = g.nodes.new("GeometryNodeSetPosition")
    g.links.new(pos.outputs[0], d.inputs[0]); g.links.new(d.outputs["Value"], c.inputs["A"]); g.links.new(pos.outputs[0], nm.inputs[0]); g.links.new(nm.outputs[0], sc.inputs[0])
    g.links.new(ln.outputs["Mesh"], sp.inputs["Geometry"]); g.links.new(c.outputs["Result"], sp.inputs["Selection"]); g.links.new(sc.outputs[0], sp.inputs["Position"]); g.links.new(sp.outputs["Geometry"], gout.inputs["Geometry"])
nv, ni = native_tree(boundary)
t = fresh()
graph(t, "Boundary", GEO_OUT,
      [dict(id="line", blIdname="GeometryNodeMeshLine", inputs={"Count": 3, "Offset": [2, 0, 0]}),
       dict(id="pos", blIdname="GeometryNodeInputPosition"),
       dict(id="len", blIdname="ShaderNodeVectorMath", properties={"operation": "LENGTH"}),
       dict(id="gt", blIdname="FunctionNodeCompare", properties={"data_type": "FLOAT", "operation": "GREATER_THAN"}, inputs={"B": B}),
       dict(id="nrm", blIdname="ShaderNodeVectorMath", properties={"operation": "NORMALIZE"}),
       dict(id="edge", blIdname="ShaderNodeVectorMath", properties={"operation": "SCALE"}, inputs={"Scale": B}),
       dict(id="set", blIdname="GeometryNodeSetPosition")],
      [("pos", "Position", "len", "Vector"), ("len", "Value", "gt", "A"), ("pos", "Position", "nrm", "Vector"), ("nrm", "Vector", "edge", "Vector"),
       ("line", "Mesh", "set", "Geometry"), ("gt", "Result", "set", "Selection"), ("edge", "Vector", "set", "Position"), ("set", "Geometry", "gout", "Geometry")])
host(t, "BoundaryHost", "Boundary")
ev = evaluated(t, "BoundaryHost")
check("boundary_step vertices equal native", srt(ev["vertexLocations"]) == nv, {"brokkr": ev["vertexLocations"], "native": nv})

# ---- 3. seeded scatter
def scatter(g, gout):
    gr = g.nodes.new("GeometryNodeMeshGrid"); gr.inputs["Size X"].default_value = 3; gr.inputs["Size Y"].default_value = 3
    di = g.nodes.new("GeometryNodeDistributePointsOnFaces"); di.distribute_method = "RANDOM"; di.inputs["Density"].default_value = 4; di.inputs["Seed"].default_value = 7
    co = g.nodes.new("GeometryNodeMeshCone"); co.inputs["Radius Bottom"].default_value = 0.05; co.inputs["Depth"].default_value = 0.4
    i = g.nodes.new("GeometryNodeInstanceOnPoints")
    g.links.new(gr.outputs["Mesh"], di.inputs["Mesh"]); g.links.new(di.outputs["Points"], i.inputs["Points"]); g.links.new(co.outputs["Mesh"], i.inputs["Instance"]); g.links.new(i.outputs["Instances"], gout.inputs["Geometry"])
nv, ni = native_tree(scatter)
t = fresh()
graph(t, "Scatter", GEO_OUT + [{"inOut": "INPUT", "name": "Seed", "type": "Int", "default": 7}],
      [dict(id="grid", blIdname="GeometryNodeMeshGrid", inputs={"Size X": 3, "Size Y": 3}),
       dict(id="dist", blIdname="GeometryNodeDistributePointsOnFaces", properties={"distribute_method": "RANDOM"}, inputs={"Density": 4, "Seed": 7}),
       dict(id="cone", blIdname="GeometryNodeMeshCone", inputs={"Radius Bottom": 0.05, "Depth": 0.4}),
       dict(id="iop", blIdname="GeometryNodeInstanceOnPoints")],
      [("grid", "Mesh", "dist", "Mesh"), ("dist", "Points", "iop", "Points"), ("cone", "Mesh", "iop", "Instance"), ("iop", "Instances", "gout", "Geometry")])
host(t, "ScatterHost", "Scatter")
ev = evaluated(t, "ScatterHost")
check("scatter instances equal native", srt(ev["instanceLocations"]) == ni and ev["instanceCount"] == len(ni), {"brokkr": ev["instanceCount"], "native": len(ni)})
ok(t, action="setModifierInput", objectName="ScatterHost", modifierName="GN", socket="Seed", value=7)  # exposed but unwired: no effect
check("unwired exposed input leaves result", srt(evaluated(t, "ScatterHost")["instanceLocations"]) == ni)

# ---- refusals on the real API
r = act(t, action="addNode", treeKey="Scatter", id="bad", blIdname="GeometryNodeMeshCube", inputs={"Nope": 1}); check("unknown input refused", r["status"] == "failed", r["message"])
check("refused addNode left no node", not any(n.get("brokkr_id") == "bad" for n in bpy.data.node_groups["Scatter"].nodes))
r = act(t, action="addNode", treeKey="Scatter", id="bad2", blIdname="GeometryNodeMeshCube", properties={"nope": 1}); check("unknown property refused", r["status"] == "failed", r["message"])
r = act(t, action="addNode", treeKey="Scatter", id="bad3", blIdname="GeometryNodeImportOBJ"); check("file-reading node refused", r["status"] == "failed", r["message"])
r = act(t, action="addNode", treeKey="Scatter", id="bad4", blIdname="GeometryNodeNoSuchThing"); check("unknown node type refused", r["status"] == "failed", r["message"])
r = act(t, action="linkSockets", treeKey="Scatter", fromNode="cone", fromSocket="Mesh", toNode="dist", toSocket="Density"); check("invalid link refused and removed", r["status"] == "failed" and not any(l.to_socket.name == "Density" for l in bpy.data.node_groups["Scatter"].links), r["message"])
r = act(t, action="setModifierInput", objectName="ScatterHost", modifierName="GN", socket="Seed", value="x"); check("wrong value type refused", r["status"] == "failed", r["message"])
r = act(t, action="addNode", treeKey="Scatter", id="grid", blIdname="GeometryNodeMeshCube"); check("duplicate id refused", r["status"] == "failed", r["message"])

json.dump(R, open(out, "w"), indent=1, default=str)
bad = [c for c in R["checks"] if not c["ok"]]
print("DONE", len(R["checks"]), "checks,", len(bad), "failed")
sys.exit(1 if bad else 0)
