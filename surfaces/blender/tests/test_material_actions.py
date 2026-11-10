"""assignMaterial tests. No Blender: a fake bpy with materials, slots and a Principled node.

Run: python3 -m unittest discover -s surfaces/blender/tests -v
The real API is exercised by tests/live/material_colour.py.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

ADDON = Path(__file__).resolve().parents[1] / "brokkr_bridge"
package = types.ModuleType("brokkr_bridge")
package.__path__ = [str(ADDON)]
sys.modules.setdefault("brokkr_bridge", package)

from brokkr_bridge import blender_target as bt  # noqa: E402

NS = types.SimpleNamespace


class Nodes(dict):
    def new(self, idname):
        node = NS(bl_idname=idname, inputs={"Base Color": NS(default_value=(0.8, 0.8, 0.8, 1.0))})
        self["Principled BSDF"] = node
        return node


class Material:
    def __init__(self, name):
        self.name, self.diffuse_color, self.node_tree = name, (0.8, 0.8, 0.8, 1.0), None
        self._use_nodes = False

    @property
    def use_nodes(self):
        return self._use_nodes

    @use_nodes.setter
    def use_nodes(self, value):  # Blender creates the default tree, with a Principled BSDF, on first use
        self._use_nodes = value
        if value and self.node_tree is None:
            self.node_tree = NS(nodes=Nodes())
            self.node_tree.nodes.new("ShaderNodeBsdfPrincipled")


class Materials(dict):
    def new(self, name):
        self[name] = Material(name)
        return self[name]


class FakeBpy:
    def __init__(self):
        self.mesh = NS(name="Cube", type="MESH", data=NS(materials=[]))
        self.empty = NS(name="Empty", type="EMPTY", data=None)
        self.data = NS(objects={"Cube": self.mesh, "Empty": self.empty}, materials=Materials())


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.bpy = FakeBpy()
        self.target = bt.BrokkrBlenderTarget(self.bpy)

    def assign(self, **fields):
        return self.target.execute_command(NS(), {"commandId": "c1", "action": "assignMaterial",
                                                  "targetObjectName": "Cube", **fields})

    def base_color(self, name="oxide red"):
        return tuple(self.bpy.data.materials[name].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value)

    def test_rgb_colour_sets_base_color_and_diffuse_with_alpha_one(self):
        receipt = self.assign(materialName="oxide red", color=[0.56, 0.2, 0.12])
        self.assertEqual(receipt["status"], "accepted", receipt["message"])
        material = self.bpy.data.materials["oxide red"]
        self.assertEqual(self.base_color(), (0.56, 0.2, 0.12, 1.0))
        self.assertEqual(tuple(material.diffuse_color), (0.56, 0.2, 0.12, 1.0))
        self.assertTrue(material.use_nodes)
        self.assertEqual(self.bpy.mesh.data.materials, [material])

    def test_rgba_colour_keeps_its_alpha(self):
        self.assign(materialName="glass", color=[0.1, 0.2, 0.3, 0.5])
        self.assertEqual(self.base_color("glass"), (0.1, 0.2, 0.3, 0.5))
        self.assertEqual(tuple(self.bpy.data.materials["glass"].diffuse_color), (0.1, 0.2, 0.3, 0.5))

    def test_no_colour_leaves_a_new_material_at_blender_defaults(self):
        self.assertEqual(self.assign(materialName="plain")["status"], "accepted")
        self.assertEqual(tuple(self.bpy.data.materials["plain"].diffuse_color), (0.8, 0.8, 0.8, 1.0))

    def test_malformed_colour_is_refused_naming_color_and_changes_nothing(self):
        for bad in ([1], [1, 0], [0, 0, 0, 1, 1], "red", 0.5, {"r": 1}, ["a", 0, 0], [True, 0, 0], [None, 0, 0],
                    [float("nan"), 0, 0], [float("inf"), 0, 0], [-0.1, 0, 0], [1.1, 0, 0], [0, 0, 0, 2]):
            receipt = self.assign(materialName="oxide red", color=bad)
            self.assertEqual(receipt["status"], "failed", bad)
            self.assertIn("color", receipt["message"], bad)
        self.assertEqual(dict(self.bpy.data.materials), {})
        self.assertEqual(self.bpy.mesh.data.materials, [])

    def test_assigning_twice_keeps_one_slot(self):
        self.assign(materialName="oxide red", color=[0.5, 0.1, 0.1])
        self.assign(materialName="oxide red", color=[0.5, 0.1, 0.1])
        self.assertEqual(len(self.bpy.mesh.data.materials), 1)
        self.assign(materialName="charcoal")
        self.assertEqual([m.name for m in self.bpy.mesh.data.materials], ["oxide red", "charcoal"])

    def test_reusing_a_material_recolours_only_when_colour_is_given(self):
        self.assign(materialName="oxide red", color=[0.5, 0.1, 0.1])
        self.assign(materialName="oxide red")
        self.assertEqual(self.base_color(), (0.5, 0.1, 0.1, 1.0))
        self.assign(materialName="oxide red", color=[0.9, 0.9, 0.9])
        self.assertEqual(self.base_color(), (0.9, 0.9, 0.9, 1.0))
        self.assertEqual(len(self.bpy.mesh.data.materials), 1)

    def test_refused_colour_on_an_existing_material_leaves_it_alone(self):
        self.assign(materialName="oxide red", color=[0.5, 0.1, 0.1])
        self.assertEqual(self.assign(materialName="oxide red", color=[2, 0, 0])["status"], "failed")
        self.assertEqual(self.base_color(), (0.5, 0.1, 0.1, 1.0))

    def test_existing_tree_without_a_principled_node_gets_one(self):
        material = self.bpy.data.materials.new("bare")
        material.use_nodes = True
        material.node_tree.nodes.clear()
        self.assertEqual(self.assign(materialName="bare", color=[0.2, 0.3, 0.4])["status"], "accepted")
        self.assertEqual(self.base_color("bare"), (0.2, 0.3, 0.4, 1.0))

    def test_object_without_material_slots_is_refused(self):
        receipt = self.target.execute_command(NS(), {"commandId": "c", "action": "assignMaterial",
                                                     "targetObjectName": "Empty", "color": [1, 0, 0]})
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(dict(self.bpy.data.materials), {})


if __name__ == "__main__":
    unittest.main()
