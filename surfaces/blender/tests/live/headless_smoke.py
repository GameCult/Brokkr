"""Live Blender smoke for the scene actions. Not part of the unittest run: it needs Blender.

  BROKKR_RUN=<scratch dir> BROKKR_ADDON=<path to surfaces/blender/brokkr_bridge> \
    blender --background --factory-startup --python surfaces/blender/tests/live/headless_smoke.py

Writes a tiny .glb into <scratch>/in, runs every scene action against real bpy, and prints
RESULT lines (accepted/failed) plus the state each action should have produced.
Last run: Blender 5.2.3 LTS on Windows, all actions accepted, both escapes refused.
"""
import json, struct, sys, types, os, traceback
from pathlib import Path
import bpy

ROOT = Path(os.environ["BROKKR_RUN"]).resolve()
ADDON = Path(os.environ["BROKKR_ADDON"]).resolve()
(ROOT / "in").mkdir(parents=True, exist_ok=True)
(ROOT / "out").mkdir(parents=True, exist_ok=True)

# tiny triangle glb
pos = struct.pack("<9f", 0,0,0, 1,0,0, 0,1,0)
gltf = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "Tri"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "buffers": [{"byteLength": len(pos)}],
        "bufferViews": [{"buffer": 0, "byteLength": len(pos), "target": 34962}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0,0,0], "max": [1,1,0]}]}
j = json.dumps(gltf).encode(); j += b" " * (-len(j) % 4)
b = pos + b"\0" * (-len(pos) % 4)
glb = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(j) + 8 + len(b)) + struct.pack("<I4s", len(j), b"JSON") + j + struct.pack("<I4s", len(b), b"BIN\0") + b
(ROOT / "in" / "tiny.glb").write_bytes(glb)

pkg = types.ModuleType("brokkr_bridge"); pkg.__path__ = [str(ADDON)]
sys.modules["brokkr_bridge"] = pkg
from brokkr_bridge import blender_target as bt

bpy.ops.wm.read_factory_settings(use_empty=True)
target = bt.BrokkrBlenderTarget(bpy)
target.configure_action_dirs(str(ROOT / "in"), str(ROOT / "out"))
ctx = bpy.context
results = []

def run(label, **cmd):
    cmd.setdefault("commandId", label)
    try:
        r = target.execute_command(bpy.context, cmd)
    except Exception:
        r = {"status": "EXCEPTION", "message": traceback.format_exc()}
    print("RESULT", label, r["status"], r.get("message", "").replace("\n", " | ")[:400], flush=True)
    results.append((label, r["status"]))
    return r

print("BLENDER", bpy.app.version_string)
run("createCam", action="createObject", objectType="CAMERA", name="Cam", location=[0, -3, 1])
run("createLight", action="createObject", objectType="LIGHT", name="Lamp", location=[2, -2, 3])
run("importGltf", action="importGltf", filepath="tiny.glb")
print("OBJECTS", sorted(bpy.data.objects.keys()))
run("importGltf_escape", action="importGltf", filepath="../x.glb")
run("setCamera", action="setCamera", targetObjectName="Cam", lens=24, cameraType="PANO", panoramaType="EQUIRECTANGULAR", active=True, clipEnd=200)
cam = bpy.data.objects["Cam"].data
print("CAM", cam.lens, cam.type, getattr(cam, "panorama_type", None), bpy.context.scene.camera and bpy.context.scene.camera.name)
run("setLight", action="setLight", targetObjectName="Lamp", energy=500, color=[1, 0.5, 0.2], lightType="AREA")
l = bpy.data.objects["Lamp"].data
print("LIGHT", l.energy, tuple(l.color), l.type)
run("setWorld", action="setWorld", color=[0.1, 0.2, 0.4], strength=1.5)
w = bpy.context.scene.world
print("WORLD", w and w.name, w and tuple(w.node_tree.nodes["Background"].inputs["Color"].default_value), w and w.node_tree.nodes["Background"].inputs["Strength"].default_value)
sc = bpy.context.scene
print("ENGINES", [i.identifier for i in sc.render.bl_rna.properties["engine"].enum_items])
sc.cycles.samples = 1
run("renderStill_cycles_pano", action="renderStill", outputPath="pano.png", engine="CYCLES", resolutionX=64, resolutionY=32, cameraName="Cam")
print("FILE pano", (ROOT / "out" / "pano.png").exists(), (ROOT / "out" / "pano.png").stat().st_size if (ROOT / "out" / "pano.png").exists() else 0)
run("renderStill_workbench", action="renderStill", outputPath="wb/shot.jpg", engine="BLENDER_WORKBENCH", resolutionX=64, resolutionY=64)
print("FILE wb", (ROOT / "out" / "wb" / "shot.jpg").exists())
run("renderStill_escape", action="renderStill", outputPath="../evil.png")
print("RESTORED", sc.render.engine, sc.render.resolution_x, sc.render.resolution_y, sc.camera and sc.camera.name)
print("SUMMARY", results)
