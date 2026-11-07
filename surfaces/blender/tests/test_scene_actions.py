"""Scene command action tests. No Blender: a fake bpy records what the target does to it.

Run: python3 -m unittest discover -s surfaces/blender/tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ADDON = Path(__file__).resolve().parents[1] / "brokkr_bridge"
package = types.ModuleType("brokkr_bridge")
package.__path__ = [str(ADDON)]
sys.modules.setdefault("brokkr_bridge", package)

from brokkr_bridge import blender_target as bt  # noqa: E402
from brokkr_bridge import scene_actions as sa  # noqa: E402

NS = types.SimpleNamespace


class Enum:
    def __init__(self, *names):
        self.enum_items = [NS(identifier=n) for n in names]


def fake_render():
    render = NS(engine="BLENDER_EEVEE", resolution_x=1920, resolution_y=1080, filepath="//old",
                image_settings=NS(file_format="PNG"))
    render.bl_rna = NS(properties={"engine": Enum("BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH")})
    return render


class Objects(dict):
    """bpy.data.objects: a mapping with keys() and get()."""


class FakeBpy:
    def __init__(self):
        self.imported = []
        self.rendered = []
        self.scene = NS(name="Scene", camera=None, world=None, render=fake_render())
        self.camera_data = NS(lens=50.0, type="PERSP", ortho_scale=6.0, clip_start=0.1, clip_end=100.0,
                              panorama_type="FISHEYE_EQUISOLID",
                              bl_rna=NS(properties={"panorama_type": Enum("EQUIRECTANGULAR", "FISHEYE_EQUISOLID")}))
        self.light_data = NS(energy=1000.0, color=(1.0, 1.0, 1.0), type="POINT")
        self.cam = NS(name="Cam", type="CAMERA", data=self.camera_data)
        self.lamp = NS(name="Lamp", type="LIGHT", data=self.light_data)
        self.mesh = NS(name="Cube", type="MESH", data=None)
        self.data = NS(
            objects=Objects({o.name: o for o in (self.cam, self.lamp, self.mesh)}),
            worlds=NS(get=lambda name: None, new=self.new_world),
        )
        self.path = NS(abspath=lambda p: p)
        self.ops = NS(import_scene=NS(gltf=self.import_gltf), render=NS(render=self.render_still))

    def new_world(self, name):
        background = NS(inputs={"Color": NS(default_value=None), "Strength": NS(default_value=None)})
        world = NS(name=name, use_nodes=False,
                   node_tree=NS(nodes=NS(get=lambda n: background if n == "Background" else None)))
        world.background = background
        return world

    def import_gltf(self, filepath):
        self.imported.append(filepath)
        self.data.objects["Imported"] = NS(name="Imported", type="MESH", data=None)

    def render_still(self, write_still):
        r = self.scene.render
        self.rendered.append((r.engine, r.resolution_x, r.resolution_y, r.filepath,
                              r.image_settings.file_format, self.scene.camera))


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "in").mkdir()
        (self.root / "out").mkdir()
        (self.root / "in" / "model.glb").write_bytes(b"glTF")
        (self.root / "secret.glb").write_bytes(b"glTF")
        self.bpy = FakeBpy()
        self.target = bt.BrokkrBlenderTarget(self.bpy)
        self.target.configure_action_dirs(str(self.root / "in"), str(self.root / "out"))
        self.context = NS(scene=self.bpy.scene)

    def run_action(self, **command):
        command.setdefault("commandId", "c1")
        return self.target.execute_command(self.context, command)

    # importGltf
    def test_import_inside_the_import_dir_runs(self):
        receipt = self.run_action(action="importGltf", filepath="model.glb")
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(self.bpy.imported, [str(self.root / "in" / "model.glb")])
        self.assertEqual(receipt["objectName"], "Imported")

    def test_import_outside_the_import_dir_is_refused_before_bpy(self):
        for path in ("../secret.glb", str(self.root / "secret.glb"), "/etc/passwd.glb", "sub/../../secret.glb"):
            receipt = self.run_action(action="importGltf", filepath=path)
            self.assertEqual(receipt["status"], "failed", path)
        self.assertEqual(self.bpy.imported, [])

    def test_import_through_a_symlink_that_escapes_is_refused(self):
        link = self.root / "in" / "link.glb"
        try:
            os.symlink(self.root / "secret.glb", link)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.run_action(action="importGltf", filepath="link.glb")["status"], "failed")
        self.assertEqual(self.bpy.imported, [])

    def test_import_needs_a_configured_dir_a_gltf_extension_and_an_existing_file(self):
        self.target.configure_action_dirs("", "")
        self.assertEqual(self.run_action(action="importGltf", filepath="model.glb")["status"], "failed")
        self.target.configure_action_dirs(str(self.root / "in"), "")
        (self.root / "in" / "x.obj").write_text("x")
        for path in ("x.obj", "missing.glb", ""):
            self.assertEqual(self.run_action(action="importGltf", filepath=path)["status"], "failed", path)
        self.assertEqual(self.bpy.imported, [])

    # setCamera
    def test_set_camera_sets_lens_type_panorama_and_active(self):
        receipt = self.run_action(action="setCamera", targetObjectName="Cam", lens=35, cameraType="pano",
                                  panoramaType="EQUIRECTANGULAR", active=True, clipEnd=500)
        self.assertEqual(receipt["status"], "accepted")
        d = self.bpy.camera_data
        self.assertEqual((d.lens, d.type, d.panorama_type, d.clip_end), (35.0, "PANO", "EQUIRECTANGULAR", 500.0))
        self.assertIs(self.bpy.scene.camera, self.bpy.cam)

    def test_set_camera_falls_back_to_the_cycles_panorama_property(self):
        cycles = NS(panorama_type="FISHEYE_EQUISOLID",
                    bl_rna=NS(properties={"panorama_type": Enum("EQUIRECTANGULAR")}))
        data = NS(lens=50.0, type="PERSP", cycles=cycles)
        self.bpy.data.objects["Cam"] = NS(name="Cam", type="CAMERA", data=data)
        receipt = self.run_action(action="setCamera", targetObjectName="Cam", panoramaType="EQUIRECTANGULAR")
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(cycles.panorama_type, "EQUIRECTANGULAR")

    def test_set_camera_refused_input_changes_nothing(self):
        for bad in ({"lens": -1}, {"lens": "wide"}, {"lens": float("nan")}, {"cameraType": "FISHEYE"},
                    {"panoramaType": "NOPE"}, {"lens": True}):
            receipt = self.run_action(action="setCamera", targetObjectName="Cam", clipEnd=9, **bad)
            self.assertEqual(receipt["status"], "failed", bad)
        self.assertEqual(self.bpy.camera_data.clip_end, 100.0)
        self.assertEqual(self.run_action(action="setCamera", targetObjectName="Lamp", lens=35)["status"], "failed")
        self.assertEqual(self.run_action(action="setCamera", targetObjectName="Nope", lens=35)["status"], "failed")

    # setLight
    def test_set_light_energy_and_colour(self):
        receipt = self.run_action(action="setLight", targetObjectName="Lamp", energy=250, color=[1, 0.5, 0])
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual((self.bpy.light_data.energy, self.bpy.light_data.color), (250.0, (1.0, 0.5, 0.0)))

    def test_set_light_rejects_bad_values_whole(self):
        for bad in ({"energy": -5}, {"color": [2, 0, 0]}, {"color": [1, 0]}, {"color": "red"}, {"lightType": "LASER"}):
            self.assertEqual(self.run_action(action="setLight", targetObjectName="Lamp", **bad)["status"], "failed", bad)
        self.assertEqual(self.bpy.light_data.energy, 1000.0)
        self.assertEqual(self.run_action(action="setLight", targetObjectName="Cam", energy=1)["status"], "failed")

    # setWorld
    def test_set_world_creates_and_assigns_a_world_with_colour_and_strength(self):
        receipt = self.run_action(action="setWorld", color=[0.1, 0.2, 0.3], strength=2)
        self.assertEqual(receipt["status"], "accepted")
        world = self.bpy.scene.world
        self.assertTrue(world.use_nodes)
        self.assertEqual(world.background.inputs["Color"].default_value, (0.1, 0.2, 0.3, 1.0))
        self.assertEqual(world.background.inputs["Strength"].default_value, 2.0)

    def test_set_world_refuses_bad_colour_before_creating_a_world(self):
        self.assertEqual(self.run_action(action="setWorld", color=[9, 0, 0])["status"], "failed")
        self.assertIsNone(self.bpy.scene.world)

    # renderStill
    def test_render_still_writes_inside_output_dir_and_restores_settings(self):
        receipt = self.run_action(action="renderStill", outputPath="shots/a.png", engine="cycles",
                                  resolutionX=640, resolutionY=360, cameraName="Cam")
        self.assertEqual(receipt["status"], "accepted")
        engine, x, y, filepath, fmt, camera = self.bpy.rendered[0]
        self.assertEqual((engine, x, y, fmt), ("CYCLES", 640, 360, "PNG"))
        self.assertEqual(filepath, str(self.root / "out" / "shots" / "a.png"))
        self.assertIs(camera, self.bpy.cam)
        render = self.bpy.scene.render
        self.assertEqual((render.engine, render.resolution_x, render.resolution_y, render.filepath),
                         ("BLENDER_EEVEE", 1920, 1080, "//old"))
        self.assertIsNone(self.bpy.scene.camera)

    def test_render_still_restores_settings_when_the_render_fails(self):
        def boom(write_still):
            raise RuntimeError("render failed")
        self.bpy.ops.render.render = boom
        self.assertEqual(self.run_action(action="renderStill", outputPath="a.png", engine="CYCLES")["status"], "failed")
        self.assertEqual(self.bpy.scene.render.engine, "BLENDER_EEVEE")

    def test_render_still_outside_the_output_dir_or_with_bad_input_never_renders(self):
        cases = [{"outputPath": "../a.png"}, {"outputPath": str(self.root / "a.png")}, {"outputPath": "a.txt"},
                 {"outputPath": ""}, {"outputPath": "a.png", "engine": "NOPE"},
                 {"outputPath": "a.png", "resolutionX": 0}, {"outputPath": "a.png", "resolutionX": 99999},
                 {"outputPath": "a.png", "resolutionX": 10.5}, {"outputPath": "a.png", "cameraName": "Lamp"}]
        for case in cases:
            self.assertEqual(self.run_action(action="renderStill", **case)["status"], "failed", case)
        self.assertEqual(self.bpy.rendered, [])
        self.target.configure_action_dirs(str(self.root / "in"), "")
        self.assertEqual(self.run_action(action="renderStill", outputPath="a.png")["status"], "failed")

    def test_capabilities_advertise_the_new_actions(self):
        for capability in ("asset.import.gltf", "camera.write", "light.write", "world.write", "render.still"):
            self.assertIn(capability, bt.CAPABILITIES)


class PathTests(unittest.TestCase):
    def test_resolve_inside_collapses_dotdot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.assertEqual(sa.resolve_inside(tmp, "a/../b.png", "output"), root / "b.png")
            with self.assertRaises(sa.ActionRefused):
                sa.resolve_inside(tmp, "a/../../b.png", "output")


if __name__ == "__main__":
    unittest.main()
