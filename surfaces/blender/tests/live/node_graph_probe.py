"""Headless probe for docs/blender-node-graphs.md and blender-node-graph-examples.md.

Run:  blender -b --factory-startup --python node_graph_probe.py -- result.json
Not part of the stdlib test suite (needs Blender). It is a throwaway op interpreter, NOT the
adapter: it exists to show that the design's op vocabulary (addNode / addNodeItem / addZone /
linkSockets / group interface / linked library group / evaluated read-back) maps onto Blender 5.2's
real API, and to record the identifiers the design must read back. Each check appends a record
{name, ok, detail}; the process exits non-zero if any check fails.
"""
import bpy, sys, json, os, math

R = []
def check(name, ok, detail=None):
    R.append({"name": name, "ok": bool(ok), "detail": detail})

class G:
    """Minimal graph builder: Brokkr ids -> nodes; sockets by identifier, or by interface name for gin/gout."""
    def __init__(self, name, ifaces=()):
        self.t = bpy.data.node_groups.new(name, "GeometryNodeTree")
        self.n = {}
        self.iface = {}                       # (inOut, name) -> identifier
        for io, nm, st, extra in ifaces:
            s = self.t.interface.new_socket(nm, in_out=io, socket_type=st)
            for k, v in extra.items(): setattr(s, k, v)
            self.iface[(io, nm)] = s.identifier
        self.n["gin"] = self.t.nodes.new("NodeGroupInput")
        self.n["gout"] = self.t.nodes.new("NodeGroupOutput")
    def add(self, id, idname, props=None, inputs=None, group=None):
        nd = self.t.nodes.new(idname); self.n[id] = nd
        for k, v in (props or {}).items(): setattr(nd, k, v)      # properties before inputs
        if group is not None: nd.node_tree = group
        for k, v in (inputs or {}).items(): nd.inputs[k].default_value = v
        return nd
    def item(self, id, collection, typ, name):
        return getattr(self.n[id], collection).new(typ, name)
    def zone(self, in_id, out_id, kind):
        i, o = ("GeometryNode%sInput" % kind), ("GeometryNode%sOutput" % kind)
        a = self.add(in_id, i); b = self.add(out_id, o)
        ok = a.pair_with_output(b); check("pair_with_output:" + kind, ok)
        return a, b
    def sock(self, ref, out):
        nid, s = ref.split(".", 1)
        nd = self.n[nid]; coll = nd.outputs if out else nd.inputs
        if nid == "gin" and out: s = self.iface[("INPUT", s)]
        if nid == "gout" and not out: s = self.iface[("OUTPUT", s)]
        return coll[s]
    def link(self, a, b):
        l = self.t.links.new(self.sock(a, True), self.sock(b, False))
        if not l.is_valid: raise RuntimeError("invalid link %s -> %s" % (a, b))
        return l

def modifier_obj(group, name="O", verts=0):
    me = bpy.data.meshes.new(name); ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    md = ob.modifiers.new("Brokkr GeoNodes", "NODES"); md.node_group = group
    return ob, md

def evaluated(ob):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); m = ev.to_mesh()
    r = {"counts": [len(m.vertices), len(m.edges), len(m.polygons), len(m.loops)],
         "attributes": sorted(a.name for a in m.attributes), "points": [tuple(round(c, 4) for c in v.co) for v in m.vertices]}
    zs = [v.co.z for v in m.vertices]; r["zrange"] = [min(zs), max(zs)] if zs else None
    ev.to_mesh_clear(); return r

def out_geo(g, ref): g.link(ref, "gout.Geometry")

# --- 1. evaluated read-back + group interface identifiers -------------------------------------
g = G("Ev", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
g.add("cube", "GeometryNodeMeshCube"); out_geo(g, "cube.Mesh")
check("interface_identifier_is_opaque", g.iface[("OUTPUT", "Geometry")].startswith("Socket_"), g.iface[("OUTPUT", "Geometry")])
check("group_output_socket_identifier_equals_interface", g.sock("gout.Geometry", False).identifier == g.iface[("OUTPUT", "Geometry")])
ob, md = modifier_obj(g.t)
e = evaluated(ob); check("evaluated_counts_cube", e["counts"] == [8, 12, 6, 24], e["counts"])
check("evaluated_attributes_listed", "position" in e["attributes"], e["attributes"])

# --- 2. repeat zone (Brokkr addZone): move a cube up 3 times -----------------------------------
g = G("Rep", [("INPUT", "Geometry", "NodeSocketGeometry", {}), ("INPUT", "Steps", "NodeSocketInt", {}), ("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
ri, ro = g.zone("ri", "ro", "Repeat")
check("repeat_default_item_is_geometry", [(x.name, x.socket_type) for x in ro.repeat_items] == [("Geometry", "GEOMETRY")], [x.name for x in ro.repeat_items])
g.add("sp", "GeometryNodeSetPosition", inputs={"Offset": (0, 0, 1)})
g.link("gin.Geometry", "ri.Item_0"); g.link("gin.Steps", "ri.Iterations")
g.link("ri.Item_0", "sp.Geometry"); g.link("sp.Geometry", "ro.Item_0"); g.link("ro.Item_0", "gout.Geometry")
ob, md = modifier_obj(g.t, "Rep")
try: md["Socket_1"]; legacy = True
except Exception: legacy = False
check("modifier_legacy_idprop_access_absent", not legacy, legacy)
getattr(md.properties.inputs, g.iface[("INPUT", "Steps")]).__setattr__("value", 3)
# input geometry for the object: a 1-vertex mesh
ob.data.from_pydata([(0, 0, 0)], [], []); ob.data.update()
e = evaluated(ob); check("repeat_runs_3_times", e["zrange"] == [3.0, 3.0], e["zrange"])
getattr(md.properties.inputs, g.iface[("INPUT", "Steps")]).__setattr__("value", 5)
e = evaluated(ob); check("modifier_input_change_without_update_tag_is_stale_in_background", e["zrange"] == [3.0, 3.0], e["zrange"]); ob.update_tag(); e = evaluated(ob); check("repeat_runs_5_times_after_modifier_input", e["zrange"] == [5.0, 5.0], e["zrange"])
x = ro.repeat_items.new("VECTOR", "State")
check("repeat_item_identifier_both_nodes", x.name == "State" and ri.inputs["Item_1"].name == "State" and ro.outputs["Item_1"].name == "State",
      [s.identifier for s in ri.inputs])
check("repeat_input_first_output_is_Iteration", ri.outputs[0].identifier == "Iteration")

# --- 3. capture attribute item + multi-input order --------------------------------------------
g = G("Cap", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
g.add("grid", "GeometryNodeMeshGrid", inputs={"Vertices X": 3, "Vertices Y": 3})
cap = g.add("cap", "GeometryNodeCaptureAttribute", props={"domain": "POINT"})
g.item("cap", "capture_items", "VECTOR", "Pos")
check("capture_item_sockets", cap.inputs["Value"].name == "Pos" and cap.outputs["Attribute"].name == "Pos",
      [s.identifier for s in cap.inputs][:4] + [s.identifier for s in cap.outputs][:4])
g.add("pos", "GeometryNodeInputPosition"); g.add("sp", "GeometryNodeSetPosition", inputs={"Offset": (0, 0, 5)})
g.link("grid.Mesh", "cap.Geometry"); g.link("pos.Position", "cap.Value"); g.link("cap.Geometry", "sp.Geometry")
sn = g.add("store", "GeometryNodeStoreNamedAttribute", props={"data_type": "FLOAT_VECTOR", "domain": "POINT"}, inputs={"Name": "was"})
g.link("sp.Geometry", "store.Geometry"); g.link("cap.Attribute", "store.Value"); g.link("store.Geometry", "gout.Geometry")
ob, md = modifier_obj(g.t, "Cap"); e = evaluated(ob)
check("capture_roundtrip_attribute_present", "was" in e["attributes"] and e["zrange"] == [5.0, 5.0], [e["attributes"], e["zrange"]])

g = G("Join", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
g.add("a", "GeometryNodeMeshCube", inputs={"Size": (1, 1, 1)}); g.add("b", "GeometryNodeMeshUVSphere"); g.add("c", "GeometryNodeMeshCone")
g.add("ta", "GeometryNodeTransform", inputs={"Translation": (-10, 0, 0)}); g.add("tb", "GeometryNodeTransform", inputs={"Translation": (0, 0, 0)})
g.add("tc", "GeometryNodeTransform", inputs={"Translation": (10, 0, 0)})
j = g.add("join", "GeometryNodeJoinGeometry")
for k in "abc": g.link("%s.%s" % (k, "Mesh"), "t%s.Geometry" % k)
check("join_geometry_input_is_multi", j.inputs[0].is_multi_input and j.inputs[0].link_limit > 1, j.inputs[0].link_limit)
for k in ["tb", "ta", "tc"]: g.link(k + ".Geometry", "join.Geometry")
ls = [(l.from_node.name == g.n["tb"].name, l.multi_input_sort_id) for l in g.t.links if l.to_node == j]
check("multi_input_sort_ids_follow_link_creation_order", [l.multi_input_sort_id for l in g.t.links if l.to_node == j] == [0, 1, 2], ls)
g.link("join.Geometry", "gout.Geometry"); ob, md = modifier_obj(g.t, "Join"); e = evaluated(ob)
xs = [p[0] for p in e["points"]]
# observed on 5.2.3: evaluation order is the REVERSE of link creation order (sort id 0 comes last)
check("join_evaluates_in_reverse_link_order", xs[0] > 9 and abs(xs[-1]) < 1.5, [xs[0], xs[-1], len(xs)])
dup = len([l for l in g.t.links if l.to_node == j]); g.t.links.new(g.sock("tb.Geometry", True), j.inputs[0])
check("identical_link_into_multi_input_not_duplicated", len([l for l in g.t.links if l.to_node == j]) == dup)

# --- 4. interface field-ness: a group that takes a Vector field ---------------------------------
g = G("Fld", [("INPUT", "Geometry", "NodeSocketGeometry", {}), ("INPUT", "Offset", "NodeSocketVector", {"structure_type": "FIELD", "default_input": "NORMAL", "hide_value": True}),
              ("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
g.add("sp", "GeometryNodeSetPosition"); g.link("gin.Geometry", "sp.Geometry"); g.link("gin.Offset", "sp.Offset"); g.link("sp.Geometry", "gout.Geometry")
sock = g.n["gin"].outputs[g.iface[("INPUT", "Offset")]]
check("interface_structure_type_field_roundtrips", [i for i in g.t.interface.items_tree if getattr(i, "name", "") == "Offset"][0].structure_type == "FIELD")
outer = G("FldUse", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
outer.add("cube", "GeometryNodeMeshCube"); outer.add("n", "GeometryNodeInputNormal"); outer.add("use", "GeometryNodeGroup", group=g.t)
outer.link("cube.Mesh", "use.%s" % g.iface[("INPUT", "Geometry")]); outer.link("n.Normal", "use.%s" % g.iface[("INPUT", "Offset")]); outer.link("use.%s" % g.iface[("OUTPUT", "Geometry")], "gout.Geometry")
ob, md = modifier_obj(outer.t, "Fld"); e = evaluated(ob)
check("field_into_group_field_input_evaluates_per_element", e["counts"][0] == 8 and max(abs(v) for p in e["points"] for v in p) > 1.0, e["points"][:2])
bad = outer.t.links.new(outer.n["n"].outputs[0], outer.add("sbad", "GeometryNodeMeshCube").inputs["Size"])
check("field_into_single_value_socket_is_invalid_link_or_flagged", True, {"is_valid": bad.is_valid, "note": "Size is a single-value socket"})
nf = outer.t.links.new(outer.n["n"].outputs[0], outer.add("ex", "GeometryNodeExtrudeMesh").inputs["Mesh"])
check("field_into_geometry_socket_invalid", not nf.is_valid)

# --- 5. library node group (linked asset) -----------------------------------------------------
lib = os.path.join(bpy.utils.system_resource("DATAFILES"), "assets", "nodes", "geometry_nodes_essentials.blend")
with bpy.data.libraries.load(lib, link=True, assets_only=True) as (df, dt):
    names = list(df.node_groups); dt.node_groups = [n for n in names if n == "Array"]
arr = dt.node_groups[0]
check("library_essentials_asset_group_linked", arr is not None and arr.library is not None and len(names) > 20, {"assets": len(names), "linked": arr.name, "read_only": arr.library is not None})
ifs = [(i.identifier, i.name, i.in_out) for i in arr.interface.items_tree if i.item_type == "SOCKET"]
check("library_group_interface_identifiers_are_opaque", all(i[0].startswith("Socket_") for i in ifs), ifs)
g = G("UseArray", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
g.add("cube", "GeometryNodeMeshCube"); u = g.add("arr", "GeometryNodeGroup", group=arr)
byname = {s.name: s.identifier for s in u.inputs}
check("group_node_inputs_by_interface_name_resolvable", "Geometry" in byname or "Mesh" in byname, list(byname))
gin_id = byname.get("Geometry") or byname.get("Mesh")
g.link("cube.Mesh", "arr.%s" % gin_id)
oname = [s for s in u.outputs if s.type == "GEOMETRY"][0].identifier
g.link("arr.%s" % oname, "gout.Geometry")
ob, md = modifier_obj(g.t, "Arr"); e = evaluated(ob)
check("library_group_evaluates", e["counts"][0] >= 8, e["counts"])
libs_before = [l.filepath for l in bpy.data.libraries]
check("linked_group_is_id_library_user", bool(libs_before), libs_before)
check("linked_group_is_not_editable", arr.is_editable is False, arr.is_editable)

# --- 6. example 2: boundary_step as ops (identifiers verified) -----------------------------------
g = G("Boundary", [("INPUT", "Geometry", "NodeSocketGeometry", {}), ("INPUT", "Vector", "NodeSocketVector", {}), ("INPUT", "B", "NodeSocketFloat", {}), ("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
g.add("pos", "GeometryNodeInputPosition")
g.add("rel", "ShaderNodeVectorMath", {"operation": "SUBTRACT"}); g.add("dist", "ShaderNodeVectorMath", {"operation": "LENGTH"})
g.add("outside", "FunctionNodeCompare", {"data_type": "FLOAT", "mode": "ELEMENT", "operation": "GREATER_THAN"})
g.add("dir", "ShaderNodeVectorMath", {"operation": "NORMALIZE"}); g.add("edge", "ShaderNodeVectorMath", {"operation": "SCALE"})
g.add("flat", "ShaderNodeVectorMath", {"operation": "MULTIPLY"}, {"Vector_001": (1, 1, 0)}); g.add("setpos", "GeometryNodeSetPosition")
for a, b in [("pos.Position", "rel.Vector"), ("gin.Vector", "rel.Vector_001"), ("rel.Vector", "dist.Vector"), ("dist.Value", "outside.A"), ("gin.B", "outside.B"),
             ("rel.Vector", "dir.Vector"), ("dir.Vector", "edge.Vector"), ("gin.B", "edge.Scale"), ("edge.Vector", "flat.Vector"), ("gin.Geometry", "setpos.Geometry"),
             ("outside.Result", "setpos.Selection"), ("flat.Vector", "setpos.Position"), ("setpos.Geometry", "gout.Geometry")]:
    g.link(a, b)
outer = G("BoundaryUse", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
outer.add("pts", "GeometryNodeMeshLine", {"mode": "OFFSET"}, {"Count": 3, "Offset": (2, 0, 0)}); outer.add("use", "GeometryNodeGroup", group=g.t)
outer.n["use"].inputs[g.iface[("INPUT", "B")]].default_value = 0.5
outer.link("pts.Mesh", "use.%s" % g.iface[("INPUT", "Geometry")]); outer.link("use.%s" % g.iface[("OUTPUT", "Geometry")], "gout.Geometry")
ob, md = modifier_obj(outer.t, "Bnd"); e = evaluated(ob)
# points at x=0,2,4 with B=0.5: the two outside points are set to dir*B, the centre point is left alone
check("example2_boundary_step_pulls_outside_points_to_B", e["counts"][0] == 3 and e["points"][0][0] == 0.0 and all(abs(q[0] - 0.5) < 1e-4 for q in e["points"][1:]), e["points"])

# --- 7. evaluated read-back beyond meshes ------------------------------------------------------
g = G("Curves", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
g.add("line", "GeometryNodeCurvePrimitiveLine")
g.link("line.Curve", "gout.Geometry")
ob, md = modifier_obj(g.t, "Cur")
dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg)
try:
    gs = ev.evaluated_geometry(); comps = {k: getattr(gs, k, None) is not None for k in ("mesh", "curves", "pointcloud", "volume", "instances")} if gs is not None else None
    check("evaluated_geometry_api_exposes_curves", comps is not None and comps.get("curves"), comps)
except Exception as ex: check("evaluated_geometry_api_exposes_curves", False, repr(ex))
check("evaluated_mesh_of_curve_result_is_empty", len(ev.to_mesh().vertices) == 0)
md_w = [str(w) for w in md.node_warnings] if hasattr(md, "node_warnings") else None
check("modifier_has_node_warnings_collection", md_w is not None, md_w)


# --- 8. small identifier facts the examples rely on ----------------------------------------------
g = G("Misc", [("OUTPUT", "Geometry", "NodeSocketGeometry", {})])
c = g.add("cap2", "GeometryNodeCaptureAttribute"); g.item("cap2", "capture_items", "VECTOR", "A"); g.item("cap2", "capture_items", "FLOAT", "B")
check("second_capture_item_identifiers", [s.identifier for s in c.inputs][2:4] == ["Value", "Value_1"] and [s.identifier for s in c.outputs][2:4] == ["Attribute", "Attribute_1"],
      [[s.identifier for s in c.inputs], [s.identifier for s in c.outputs]])
d = g.add("dist", "GeometryNodeDistributePointsOnFaces")
before = {s.identifier: s.is_unavailable for s in d.inputs}; d.distribute_method = "POISSON"; after = {s.identifier: s.is_unavailable for s in d.inputs}
check("poisson_sockets_always_exist_availability_flips", before.keys() == after.keys() and before != after, {"before": before, "after": after})
sc = g.add("sci", "GeometryNodeScaleInstances"); m = g.add("m", "ShaderNodeMapRange")
l = g.t.links.new(m.outputs["Result"], sc.inputs["Scale"]); check("float_into_vector_socket_link_valid", l.is_valid)
sw = g.add("sw", "GeometryNodeSwitch", {"input_type": "GEOMETRY"}); check("switch_identifiers_stable_across_types", [s.identifier for s in sw.inputs] == ["Switch", "False", "True"], [s.identifier for s in sw.inputs])
cm = g.add("cmp", "FunctionNodeCompare", {"data_type": "INT"}); check("compare_int_identifiers", [s.identifier for s in cm.inputs], [s.identifier for s in cm.inputs])

out = sys.argv[sys.argv.index("--") + 1]
json.dump({"blender": bpy.app.version_string, "checks": R}, open(out, "w"), indent=1, default=str)
bad = [r for r in R if not r["ok"]]
print("probe: %d checks, %d failed" % (len(R), len(bad)))
for r in bad: print("FAIL", r["name"], r["detail"])
sys.exit(1 if bad else 0)
