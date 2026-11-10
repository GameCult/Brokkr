"""Scene command action tests. No Blender: a fake bpy records what the target does to it.

Run: python3 -m unittest discover -s surfaces/blender/tests -v
"""
from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ADDON = Path(__file__).resolve().parents[1] / "brokkr_bridge"
package = types.ModuleType("brokkr_bridge")
package.__path__ = [str(ADDON)]
sys.modules.setdefault("brokkr_bridge", package)

from brokkr_bridge import blender_target as bt  # noqa: E402
from brokkr_bridge import scene_actions as sa  # noqa: E402

NS = types.SimpleNamespace


def glb_bytes(document=None):
    document = document or {"asset": {"version": "2.0"}}
    raw = json.dumps(document).encode()
    raw += b" " * (-len(raw) % 4)
    return struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(raw)) + struct.pack("<I4s", len(raw), b"JSON") + raw


class Enum:
    def __init__(self, *names):
        self.enum_items = [NS(identifier=n) for n in names]


class FakeRender:
    """Assigning an engine Blender does not have raises TypeError, as RNA enums do. The enum's
    bl_rna lists only the static default, as a real dynamic enum does (Blender 5.2.3 reports
    only BLENDER_EEVEE there while Cycles is installed)."""

    ENGINES = ("BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH")

    def __init__(self):
        self._engine = "BLENDER_EEVEE"
        self.resolution_x, self.resolution_y, self.filepath = 1920, 1080, "//old"
        self.image_settings = NS(file_format="PNG")
        self.bl_rna = NS(properties={"engine": Enum("BLENDER_EEVEE")})

    @property
    def engine(self):
        return self._engine

    @engine.setter
    def engine(self, value):
        if value not in self.ENGINES:
            raise TypeError(f"enum {value!r} not found")
        self._engine = value


def fake_render():
    return FakeRender()


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
        self.created = []
        self.app = NS(background=False)
        add = lambda kind: (lambda **kw: self.add_object(kind, kw))
        self.ops = NS(import_scene=NS(gltf=self.import_gltf), render=NS(render=self.render_still),
                      mesh=NS(primitive_cube_add=add("MESH")), object=NS(light_add=add("LIGHT"),
                      camera_add=add("CAMERA"), empty_add=add("EMPTY")))
        self.on_add = lambda obj: None

    def add_object(self, kind, kwargs):
        self.created.append((kind, kwargs))
        obj = NS(name=kind.title(), type=kind)
        self.data.objects[obj.name] = obj
        self.on_add(obj)

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
        (self.root / "in" / "model.glb").write_bytes(glb_bytes())
        (self.root / "secret.glb").write_bytes(glb_bytes())
        self.bpy = FakeBpy()
        self.target = bt.BrokkrBlenderTarget(self.bpy)
        self.target.configure_action_dirs(str(self.root / "in"), str(self.root / "out"))
        self.context = NS(scene=self.bpy.scene, object=None)
        self.bpy.on_add = lambda obj: setattr(self.context, "object", obj)

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

    # createObject
    def test_create_object_makes_the_four_admitted_types(self):
        for kind in ("MESH", "LIGHT", "CAMERA", "EMPTY"):
            receipt = self.run_action(action="createObject", objectType=kind, name="N")
            self.assertEqual(receipt["status"], "accepted", kind)
            self.assertEqual(self.bpy.created[-1][0], kind)
        self.assertEqual(self.run_action(action="createObject", objectType="MESH", meshType="cube")["status"], "accepted")

    def test_create_object_refuses_other_types_naming_the_type_and_the_allowed_set(self):
        for kind in ("TEXT", "CURVE", "mesh", "", None, 3):
            receipt = self.run_action(action="createObject", objectType=kind)
            self.assertEqual(receipt["status"], "failed", kind)
            for allowed in ("MESH", "LIGHT", "CAMERA", "EMPTY"):
                self.assertIn(allowed, receipt["message"])
            self.assertIn(repr(kind) if not isinstance(kind, str) else kind, receipt["message"])
        self.assertEqual(self.bpy.created, [])

    def test_create_object_refuses_a_mesh_type_other_than_cube(self):
        for mesh_type in ("CYLINDER", "", 1):
            receipt = self.run_action(action="createObject", objectType="MESH", meshType=mesh_type)
            self.assertEqual(receipt["status"], "failed", mesh_type)
            self.assertIn("CUBE", receipt["message"])
        self.assertEqual(self.bpy.created, [])

    # renderStill: GPU engines without a GL runtime
    def test_render_still_refuses_gpu_engines_headless_when_the_gl_library_is_missing(self):
        self.bpy.app.background = True
        for engine in ("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "blender_workbench"):
            self.bpy.scene.render.ENGINES = FakeRender.ENGINES + ("BLENDER_EEVEE_NEXT",)
            with mock.patch.object(bt, "missing_gl_library", return_value="libEGL.so.1"):
                receipt = self.run_action(action="renderStill", outputPath="a.png", engine=engine)
            self.assertEqual(receipt["status"], "failed", engine)
            self.assertIn("libEGL.so.1", receipt["message"])
            self.assertIn("CYCLES", receipt["message"])
        self.assertEqual(self.bpy.rendered, [])
        self.assertEqual(self.bpy.scene.render.engine, "BLENDER_EEVEE")

    def test_render_still_refuses_the_scene_engine_too_and_leaves_no_folder(self):
        self.bpy.app.background = True  # scene engine is BLENDER_EEVEE
        with mock.patch.object(bt, "missing_gl_library", return_value="libEGL.so.1"):
            receipt = self.run_action(action="renderStill", outputPath="shots/a.png")
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse((self.root / "out" / "shots").exists())

    def test_render_still_gl_check_spares_cycles_foreground_and_a_present_library(self):
        probe = mock.Mock(return_value="libEGL.so.1")
        with mock.patch.object(bt, "missing_gl_library", probe):
            self.bpy.app.background = True
            self.assertEqual(self.run_action(action="renderStill", outputPath="a.png", engine="CYCLES")["status"], "accepted")
            probe.assert_not_called()
            self.bpy.app.background = False
            self.assertEqual(self.run_action(action="renderStill", outputPath="b.png", engine="BLENDER_WORKBENCH")["status"], "accepted")
            probe.assert_not_called()
            self.bpy.app.background = True
            probe.return_value = None
            self.assertEqual(self.run_action(action="renderStill", outputPath="c.png", engine="BLENDER_WORKBENCH")["status"], "accepted")

    def test_missing_gl_library_probes_only_on_linux_and_only_once(self):
        bt.missing_gl_library.cache_clear()
        with mock.patch.object(bt.sys, "platform", "win32"), mock.patch.object(bt.ctypes, "CDLL", side_effect=OSError) as cdll:
            self.assertIsNone(bt.missing_gl_library())
            cdll.assert_not_called()
        bt.missing_gl_library.cache_clear()
        with mock.patch.object(bt.sys, "platform", "linux"), mock.patch.object(bt.ctypes, "CDLL", side_effect=OSError) as cdll:
            self.assertEqual(bt.missing_gl_library(), "libEGL.so.1")
            self.assertEqual(bt.missing_gl_library(), "libEGL.so.1")
            cdll.assert_called_once_with("libEGL.so.1")
        bt.missing_gl_library.cache_clear()
        with mock.patch.object(bt.sys, "platform", "linux"), mock.patch.object(bt.ctypes, "CDLL"):
            self.assertIsNone(bt.missing_gl_library())
        bt.missing_gl_library.cache_clear()

    # importGltf: names
    def test_import_refuses_drive_unc_extended_stream_and_device_names(self):
        for name in ("C:foo.glb", "C:\\x\\model.glb", "\\\\host\\share\\model.glb", "\\\\?\\C:\\model.glb",
                     "model.glb:stream", "/model.glb", "\\model.glb", "CON.glb", "sub/nul.glb", "model.glb.",
                     "model.glb ", "a\x00.glb", "..\\secret.glb"):
            self.assertEqual(self.run_action(action="importGltf", filepath=name)["status"], "failed", name)
        self.assertEqual(self.bpy.imported, [])

    def test_import_refuses_a_symlinked_folder_even_when_it_points_elsewhere_inside_the_root(self):
        (self.root / "in" / "real").mkdir()
        (self.root / "in" / "real" / "m.glb").write_bytes(glb_bytes())
        try:
            os.symlink(self.root / "in" / "real", self.root / "in" / "alias", target_is_directory=True)
            os.symlink(self.root, self.root / "in" / "up", target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        for name in ("alias/m.glb", "up/secret.glb"):
            self.assertEqual(self.run_action(action="importGltf", filepath=name)["status"], "failed", name)
        self.assertEqual(self.run_action(action="importGltf", filepath="real/m.glb")["status"], "accepted")

    # importGltf: references inside the glTF
    def write_gltf(self, name, document, glb=False):
        path = self.root / "in" / name
        if glb:
            path.write_bytes(glb_bytes(document))
        else:
            path.write_text(json.dumps(document))
        return path

    def test_gltf_with_references_inside_the_root_and_data_uris_is_imported(self):
        (self.root / "in" / "tex").mkdir()
        (self.root / "in" / "tex" / "a.png").write_bytes(b"png")
        (self.root / "in" / "m.bin").write_bytes(b"bin")
        for glb, name in ((False, "ok.gltf"), (True, "ok.glb")):
            self.write_gltf(name, {"asset": {"version": "2.0"},
                                   "buffers": [{"uri": "m.bin", "byteLength": 3},
                                               {"uri": "data:application/octet-stream;base64,AAAA", "byteLength": 3}],
                                   "images": [{"uri": "tex/a%2Epng"}]}, glb=glb)
            self.assertEqual(self.run_action(action="importGltf", filepath=name)["status"], "accepted", name)
        self.assertEqual(len(self.bpy.imported), 2)

    def test_gltf_references_that_leave_the_root_or_name_a_scheme_are_refused(self):
        bad = ["../secret.glb", "..\\secret.glb", "%2e%2e/secret.glb", "/etc/passwd", "\\\\host\\share\\x.bin",
               "C:\\Windows\\x.bin", "C:x.bin", "file:///etc/passwd", "http://example.com/x.bin",
               "x.bin:stream", "sub/../../secret.glb", "CON", "x.bin."]
        for kind in ("buffers", "images"):
            for uri in bad:
                for glb in (False, True):
                    name = f"bad{glb}.{'glb' if glb else 'gltf'}"
                    self.write_gltf(name, {"asset": {"version": "2.0"}, kind: [{"uri": uri}]}, glb=glb)
                    receipt = self.run_action(action="importGltf", filepath=name)
                    self.assertEqual(receipt["status"], "failed", (kind, uri, glb))
        self.assertEqual(self.bpy.imported, [])

    def test_gltf_reference_through_a_symlink_that_escapes_is_refused(self):
        try:
            os.symlink(self.root / "secret.glb", self.root / "in" / "buf.bin")
        except OSError:
            self.skipTest("symlinks unavailable")
        self.write_gltf("link.gltf", {"asset": {"version": "2.0"}, "buffers": [{"uri": "buf.bin"}]})
        receipt = self.run_action(action="importGltf", filepath="link.gltf")
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("link", receipt["message"])  # the rule that fired, not a generic "outside"
        self.assertEqual(self.bpy.imported, [])

    def test_gltf_reference_to_a_missing_file_is_refused(self):
        try:
            os.symlink(self.root / "nowhere.bin", self.root / "in" / "dangling.bin")
            dangling = True
        except OSError:
            dangling = False
        for kind in ("buffers", "images"):
            for uri in ["absent.bin", "sub/absent.png"] + (["dangling.bin"] if dangling else []):
                self.write_gltf("miss.gltf", {"asset": {"version": "2.0"}, kind: [{"uri": uri}]})
                receipt = self.run_action(action="importGltf", filepath="miss.gltf")
                self.assertEqual(receipt["status"], "failed", (kind, uri))
                self.assertRegex(receipt["message"], "does not exist|link", (kind, uri))
        self.assertEqual(self.bpy.imported, [])

    def test_malformed_gltf_is_refused(self):
        (self.root / "in" / "junk.gltf").write_text("{not json")
        (self.root / "in" / "list.gltf").write_text("[]")
        (self.root / "in" / "trunc.glb").write_bytes(glb_bytes()[:21])
        (self.root / "in" / "notglb.glb").write_bytes(b"GLTF" + bytes(30))
        (self.root / "in" / "uri.gltf").write_text(json.dumps({"buffers": [{"uri": 5}]}))
        for name in ("junk.gltf", "list.gltf", "trunc.glb", "notglb.glb", "uri.gltf"):
            self.assertEqual(self.run_action(action="importGltf", filepath=name)["status"], "failed", name)
        self.assertEqual(self.bpy.imported, [])

    def test_import_is_refused_when_the_file_changes_between_check_and_use(self):
        target_file = self.root / "in" / "model.glb"
        original = sa.gltf_references

        def swap_after_check(path):
            result = original(path)
            target_file.write_bytes(glb_bytes({"asset": {"version": "2.0"}, "extras": "x" * 50}))
            return result
        with mock.patch.object(sa, "gltf_references", swap_after_check):
            receipt = self.run_action(action="importGltf", filepath="model.glb")
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("changed", receipt["message"])
        self.assertEqual(self.bpy.imported, [])

    # renderStill: existing names and links
    def test_render_refuses_an_existing_file_symlink_dangling_symlink_or_hardlink(self):
        out = self.root / "out"
        (out / "taken.png").write_bytes(b"old")
        cases = ["taken.png"]
        try:
            os.symlink(self.root / "secret.glb", out / "sym.png")
            os.symlink(self.root / "nowhere.png", out / "dangling.png")
            os.link(self.root / "secret.glb", out / "hard.png")
            cases += ["sym.png", "dangling.png", "hard.png"]
        except OSError:
            pass
        for name in cases:
            self.assertEqual(self.run_action(action="renderStill", outputPath=name)["status"], "failed", name)
        self.assertEqual(self.bpy.rendered, [])
        self.assertEqual((out / "taken.png").read_bytes(), b"old")

    def test_render_refuses_a_symlinked_output_folder(self):
        outside = self.root / "outside"
        outside.mkdir()
        try:
            os.symlink(outside, self.root / "out" / "dir", target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.run_action(action="renderStill", outputPath="dir/a.png")["status"], "failed")
        self.assertEqual(self.bpy.rendered, [])
        self.assertEqual(list(outside.iterdir()), [])

    def test_a_refused_render_leaves_no_folders_behind(self):
        (self.root / "out" / "taken").mkdir()
        (self.root / "out" / "taken" / "a.png").write_bytes(b"x")
        for case in ({"outputPath": "new/deep/a.png", "resolutionX": 0}, {"outputPath": "new/deep/a.png", "engine": ""}, {"outputPath": "new/deep/a.png", "engine": "NOPE"},
                     {"outputPath": "new/deep/a.png", "cameraName": "Nope"}, {"outputPath": "new/deep/a.txt"},
                     {"outputPath": "taken/a.png"}):
            self.assertEqual(self.run_action(action="renderStill", **case)["status"], "failed", case)
        self.assertIn("already exists", self.run_action(action="renderStill", outputPath="taken/a.png")["message"])
        self.assertEqual(sorted(p.name for p in (self.root / "out").iterdir()), ["taken"])
        self.assertEqual(self.bpy.rendered, [])

    def test_render_refuses_drive_unc_extended_stream_and_device_names(self):
        for name in ("C:a.png", "C:\\a.png", "\\\\host\\share\\a.png", "\\\\?\\C:\\a.png", "a.png:stream",
                     "/a.png", "NUL.png", "a.png.", "x/../a.png"):
            self.assertEqual(self.run_action(action="renderStill", outputPath=name)["status"], "failed", name)
        self.assertEqual(self.bpy.rendered, [])

    def test_render_is_refused_when_a_link_appears_after_the_check(self):
        outside = self.root / "outside"
        outside.mkdir()
        real_mkdir = Path.mkdir

        def swap(self_path, *args, **kwargs):
            real_mkdir(self_path, *args, **kwargs)
            if self_path.name == "late":
                self_path.rmdir()
                os.symlink(outside, self_path, target_is_directory=True)
        try:
            with mock.patch.object(Path, "mkdir", swap):
                receipt = self.run_action(action="renderStill", outputPath="late/a.png")
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(self.bpy.rendered, [])

    def test_capabilities_advertise_the_new_actions(self):
        for capability in ("asset.import.gltf", "camera.write", "light.write", "world.write", "render.still"):
            self.assertIn(capability, bt.CAPABILITIES)


class PathTests(unittest.TestCase):
    def test_resolve_inside_takes_plain_relative_paths_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.assertEqual(sa.resolve_inside(tmp, "a/./b.png", "output"), root / "a" / "b.png")
            for name in ("a/../b.png", "a/../../b.png", "..", "", "."):
                with self.assertRaises(sa.ActionRefused, msg=name):
                    sa.resolve_inside(tmp, name, "output")

    def test_check_relative_refuses_device_names_however_windows_spells_them(self):
        # Windows drops spaces before the first dot (CON .txt is CON) and reads superscript digits as COM/LPT digits.
        for name in ("CON", "con", "CON .txt", "NUL .png", "sub/NUL  .png", "COM1", "COM\u00b9", "LPT\u00b2.txt", "LPT\u00b3",
                     "CONIN$", "a/PRN.tar.gz"):
            with self.assertRaisesRegex(sa.ActionRefused, "device", msg=name):
                sa.check_relative(name, "output")
        for name in ("CONSOLE.png", "COM10.png", "com.png", "a.CON.png", "NULL"):
            sa.check_relative(name, "output")

    def test_check_relative_itself_refuses_dotdot_and_nul(self):
        # Each rule on its own: resolve_inside's link walk also trips on '..', so only a
        # direct call proves the text rule.
        for name in ("a/../b", "..", "a\\..\\b", "a\x00b"):
            with self.assertRaises(sa.ActionRefused, msg=repr(name)):
                sa.check_relative(name, "output")
        self.assertEqual(sa.check_relative("a\\b/./c", "output"), ["a", "b", "c"])

    def test_a_component_the_os_refuses_to_resolve_counts_as_a_link(self):
        # Windows raises WinError 448 resolving some junctions; that is a link refusal, not a crash.
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "j").mkdir()
            real = Path.resolve

            def resolve(self, *args, **kwargs):
                if self.name == "j":
                    raise OSError(448, "untrusted mount point")
                return real(self, *args, **kwargs)

            with mock.patch.object(Path, "resolve", resolve):
                with self.assertRaisesRegex(sa.ActionRefused, "link"):
                    sa.resolve_inside(tmp, "j/x.png", "output")


if __name__ == "__main__":
    unittest.main()
