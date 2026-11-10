"""Live proof of assignMaterial colour and idempotence on real bpy.

  BROKKR_ADDON=<path to surfaces/blender/brokkr_bridge> \
    blender -b --factory-startup --python material_colour.py -- result.json

Exit status is non-zero if any check fails.
"""
import bpy, sys, os, json, types
from pathlib import Path

ADDON = Path(os.environ["BROKKR_ADDON"]).resolve()
pkg = types.ModuleType("brokkr_bridge"); pkg.__path__ = [str(ADDON)]
sys.modules["brokkr_bridge"] = pkg
from brokkr_bridge import blender_target as bt

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "material_colour_result.json"
R = {"blender": bpy.app.version_string, "checks": []}

def check(name, ok, detail=None):
    R["checks"].append({"name": name, "ok": bool(ok), "detail": detail}); print("CHECK", "ok  " if ok else "FAIL", name, detail if not ok else "", flush=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
t = bt.BrokkrBlenderTarget(bpy)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.active_object
N = [0]
def act(**cmd):
    N[0] += 1; cmd.setdefault("commandId", "c%d" % N[0]); cmd["action"] = "assignMaterial"; cmd["targetObjectName"] = cube.name
    return t.execute_command(bpy.context, cmd)

def base():
    return tuple(round(c, 6) for c in bpy.data.materials["oxide red"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value)

r = act(materialName="oxide red", color=[0.56, 0.2, 0.12])
check("oxide red accepted", r["status"] == "accepted", r["message"])
check("principled base color", base() == (0.56, 0.2, 0.12, 1.0), base())
m = bpy.data.materials["oxide red"]
check("diffuse_color", tuple(round(c, 6) for c in m.diffuse_color) == (0.56, 0.2, 0.12, 1.0), tuple(m.diffuse_color))
check("one slot", len(cube.material_slots) == 1, len(cube.material_slots))
r = act(materialName="oxide red", color=[0.56, 0.2, 0.12])
check("repeat accepted", r["status"] == "accepted", r["message"])
check("repeat keeps one slot", len(cube.material_slots) == 1, len(cube.material_slots))
r = act(materialName="oxide red")
check("no color leaves colour", r["status"] == "accepted" and base() == (0.56, 0.2, 0.12, 1.0), base())
r = act(materialName="oxide red", color=[0.1, 0.2, 0.3, 0.5])
check("rgba recolours", base() == (0.1, 0.2, 0.3, 0.5) and len(cube.material_slots) == 1, base())
for bad in ([1, 2], [2, 0, 0], [float("nan"), 0, 0], "red"):
    r = act(materialName="oxide red", color=bad)
    check("bad colour refused %r" % (bad,), r["status"] == "failed" and "color" in r["message"], r["message"])
check("refusals left colour", base() == (0.1, 0.2, 0.3, 0.5), base())
r = act(materialName="never made", color=[7, 0, 0])
check("refusal creates no material", "never made" not in bpy.data.materials)

json.dump(R, open(out, "w"), indent=1)
sys.exit(0 if all(c["ok"] for c in R["checks"]) else 1)
