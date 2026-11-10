"""Node-graph action tests. No Blender: a fake bpy with just enough node-tree surface.

Run: python3 -m unittest discover -s surfaces/blender/tests -v
The real API is exercised by tests/live/gn_actions.py.
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
from brokkr_bridge import node_actions as na  # noqa: E402

NS = types.SimpleNamespace


class Sock:
    def __init__(self, identifier, name, kind="VALUE", default=0.0):
        self.identifier, self.name, self.type, self.enabled = identifier, name, kind, True
        self.default_value, self.is_linked = default, False


class Node(dict):
    """A node; ID properties are the dict part."""

    PROPS = {"operation": NS(type="ENUM", is_readonly=False), "flag": NS(type="BOOLEAN", is_readonly=False),
             "filepath": NS(type="STRING", is_readonly=False), "location": NS(type="FLOAT", is_readonly=False)}

    def __init__(self, idname):
        super().__init__()
        self.bl_idname, self.location, self.label, self.operation, self.flag = idname, [0, 0], "", "ADD", False
        self.bl_rna = NS(properties=self.PROPS)
        self.inputs = [Sock("A", "A"), Sock("Size", "Size", "VECTOR", (1.0, 1.0, 1.0)), Sock("B", "Dup"), Sock("B_VEC", "Dup")]
        self.outputs = [Sock("Out", "Out")]

    def __setattr__(self, key, value):
        if key == "operation" and value not in ("ADD", "MULTIPLY"):
            raise TypeError("enum not found")
        object.__setattr__(self, key, value)


class Nodes(list):
    def new(self, idname):
        if idname.endswith("Missing"):
            raise RuntimeError("Node type undefined")
        node = Node(idname)
        self.append(node)
        return node

    def remove(self, node):
        list.remove(self, node)


class Links(list):
    def __init__(self, valid=True):
        super().__init__()
        self.valid = valid

    def new(self, a, b):
        link = NS(from_socket=a, to_socket=b, is_valid=self.valid)
        self.append(link)
        return link

    def remove(self, link):
        list.remove(self, link)


class Interface:
    def __init__(self):
        self.items_tree = []

    def new_socket(self, name, in_out, socket_type):
        item = NS(item_type="SOCKET", name=name, in_out=in_out, socket_type=socket_type, identifier=f"Socket_{len(self.items_tree)}", default_value=None)
        self.items_tree.append(item)
        return item


class Tree:
    bl_idname = "GeometryNodeTree"
    library = None

    def __init__(self, name):
        self.name, self.nodes, self.links, self.interface = name, Nodes(), Links(), Interface()


class Groups(dict):
    def new(self, name, kind):
        self[name] = Tree(name)
        return self[name]

    def remove(self, tree):
        del self[tree.name]


class Inputs:
    def __init__(self):
        self.values = {}

    def __getattr__(self, identifier):
        return self.values.setdefault(identifier, NS(value=None))


class Modifiers(list):
    def get(self, name):
        return next((m for m in self if m.name == name), None)

    def new(self, name, kind):
        m = NS(name=name, type=kind, node_group=None, properties=NS(inputs=Inputs()))
        self.append(m)
        return m


class Obj:
    def __init__(self, name):
        self.name, self.type, self.data, self.modifiers, self.tagged = name, "MESH", None, Modifiers(), 0

    def update_tag(self):
        self.tagged += 1

    def get(self, key, default=None):
        return default

    def __setitem__(self, key, value):
        self.custom = (key, value)


class FakeBpy:
    def __init__(self):
        self.data = NS(node_groups=Groups(), objects={"Host": Obj("Host")})


class NodeActionTests(unittest.TestCase):
    def setUp(self):
        self.bpy = FakeBpy()
        self.target = bt.BrokkrBlenderTarget(self.bpy)
        self.n = 0

    def run_action(self, **command):
        self.n += 1
        command.setdefault("commandId", f"c{self.n}")
        return self.target.execute_command(None, command)

    def accepted(self, **command):
        receipt = self.run_action(**command)
        self.assertEqual(receipt["status"], "accepted", receipt["message"])
        return receipt

    def refused(self, **command):
        receipt = self.run_action(**command)
        self.assertEqual(receipt["status"], "failed", receipt["message"])
        return receipt

    def group(self, interface=None):
        self.accepted(action="createNodeGroup", treeKey="G", interface=interface or [{"inOut": "OUTPUT", "name": "Geometry", "type": "Geometry"}, {"inOut": "INPUT", "name": "Count", "type": "Int", "default": 8}])
        return self.bpy.data.node_groups["G"]

    # createNodeGroup
    def test_group_gets_interface_and_stamped_group_nodes(self):
        receipt = self.accepted(action="createNodeGroup", treeKey="G", interface=[{"inOut": "INPUT", "name": "Count", "type": "Int", "default": 8}])
        tree = self.bpy.data.node_groups["G"]
        self.assertEqual([n.get("brokkr_id") for n in tree.nodes], ["gin", "gout"])
        self.assertEqual(tree.interface.items_tree[0].default_value, 8)
        self.assertIn("Count=Socket_0", receipt["message"])

    def test_group_refusals_create_nothing(self):
        for interface in (None, [], "x", [{"inOut": "SIDEWAYS", "name": "a", "type": "Int"}], [{"inOut": "INPUT", "name": "a", "type": "Mesh"}],
                          [{"inOut": "INPUT", "name": "a", "type": "Int"}, {"inOut": "INPUT", "name": "a", "type": "Float"}],
                          [{"inOut": "INPUT", "name": "a", "type": "Int", "default": 1.5}], [{"inOut": "INPUT", "name": "a", "type": "Vector", "default": [1, 2]}]):
            self.refused(action="createNodeGroup", treeKey="G", interface=interface)
        self.refused(action="createNodeGroup", treeKey="../x", interface=[{"inOut": "INPUT", "name": "a", "type": "Int"}])
        self.refused(action="createNodeGroup", treeKind="material", treeKey="G", interface=[{"inOut": "INPUT", "name": "a", "type": "Int"}])
        self.assertEqual(len(self.bpy.data.node_groups), 0)

    def test_group_that_exists_is_not_overwritten(self):
        self.group()
        self.refused(action="createNodeGroup", treeKey="G", interface=[{"inOut": "INPUT", "name": "a", "type": "Int"}])
        self.assertEqual(len(self.bpy.data.node_groups["G"].interface.items_tree), 2)

    # addNode
    def test_add_node_applies_properties_then_inputs_and_stamps_id(self):
        tree = self.group()
        self.accepted(action="addNode", treeKey="G", id="m", blIdname="ShaderNodeMath", location=[10, 20], properties={"operation": "MULTIPLY"}, inputs={"A": 3, "Size": [1, 2, 3]})
        node = tree.nodes[-1]
        self.assertEqual((node.operation, node.location, node.inputs[0].default_value, node.inputs[1].default_value), ("MULTIPLY", [10.0, 20.0], 3.0, (1.0, 2.0, 3.0)))

    def test_add_node_refusals_leave_no_node(self):
        tree = self.group()
        before = len(tree.nodes)
        cases = [dict(blIdname="GeometryNodeImportOBJ"), dict(blIdname="GeometryNodeBake"), dict(blIdname="NodeGroupInput"), dict(blIdname="bpy.ops"),
                 dict(blIdname="ShaderNodeMissing"), dict(blIdname="ShaderNodeMath", properties={"operation": "NOPE"}),
                 dict(blIdname="ShaderNodeMath", properties={"filepath": "/etc/passwd"}), dict(blIdname="ShaderNodeMath", properties={"location": 1.0}),
                 dict(blIdname="ShaderNodeMath", properties={"missing": 1}), dict(blIdname="ShaderNodeMath", inputs={"Dup": 1}),
                 dict(blIdname="ShaderNodeMath", inputs={"Nope": 1}), dict(blIdname="ShaderNodeMath", inputs={"A": float("nan")}),
                 dict(blIdname="ShaderNodeMath", inputs={"A": True}), dict(blIdname="ShaderNodeMath", inputs={"A": 1e12}),
                 dict(blIdname="ShaderNodeMath", inputs={"Size": [1, 2]}), dict(blIdname="ShaderNodeMath", location=[1])]
        for case in cases:
            self.refused(action="addNode", treeKey="G", id="x", **case)
        self.assertEqual(len(tree.nodes), before)

    def test_string_and_reserved_properties_are_refused_by_rule(self):
        self.group()
        for name in ("filepath", "location"):
            receipt = self.refused(action="addNode", treeKey="G", id="x", blIdname="ShaderNodeMath", properties={name: "v"})
            self.assertIn("no settable property", receipt["message"])

    def test_add_node_refuses_bad_ids_duplicates_and_missing_tree(self):
        self.group()
        for bad in ("", "a b", "x" * 64, "../x", None):
            self.refused(action="addNode", treeKey="G", id=bad, blIdname="ShaderNodeMath")
        self.refused(action="addNode", treeKey="G", id="gin", blIdname="ShaderNodeMath")
        self.refused(action="addNode", treeKey="Nope", id="a", blIdname="ShaderNodeMath")

    def test_node_cap(self):
        tree = self.group()
        for i in range(na.MAX_NODES - 2):
            tree.nodes.new("ShaderNodeMath")
        self.refused(action="addNode", treeKey="G", id="over", blIdname="ShaderNodeMath")

    def test_linked_library_group_is_read_only(self):
        tree = self.group()
        tree.library = NS(filepath="lib.blend")
        self.refused(action="addNode", treeKey="G", id="a", blIdname="ShaderNodeMath")

    # linkSockets
    def test_link_by_identifier_and_by_unique_name(self):
        tree = self.group()
        self.accepted(action="addNode", treeKey="G", id="a", blIdname="ShaderNodeMath")
        self.accepted(action="addNode", treeKey="G", id="b", blIdname="ShaderNodeMath")
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="b", toSocket="A")
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="b", toSocket="Size")
        self.assertEqual(len(tree.links), 2)
        self.refused(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="b", toSocket="Dup")  # name shared by two sockets
        self.refused(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="zzz", toSocket="A")
        self.assertEqual(len(tree.links), 2)

    def test_unavailable_socket_is_not_addressable_by_name(self):
        tree = self.group()
        self.accepted(action="addNode", treeKey="G", id="a", blIdname="ShaderNodeMath")
        tree.nodes[-1].inputs[3].enabled = False
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="a", toSocket="Dup")

    def test_invalid_link_is_refused_and_removed(self):
        tree = self.group()
        tree.links.valid = False
        self.accepted(action="addNode", treeKey="G", id="a", blIdname="ShaderNodeMath")
        self.refused(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="a", toSocket="A")
        self.assertEqual(len(tree.links), 0)

    # addModifier / setModifierInput
    def test_modifier_assigns_group_and_reuses_by_name(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        self.assertEqual(len(host.modifiers), 1)
        self.assertIs(host.modifiers[0].node_group, self.bpy.data.node_groups["G"])
        self.refused(action="addModifier", objectName="Host", modifierType="SUBSURF", treeKey="G")
        self.refused(action="addModifier", objectName="Nope", treeKey="G")
        self.refused(action="addModifier", objectName="Host", treeKey="Nope")

    def test_modifier_cap(self):
        self.group()
        for i in range(na.MAX_MODIFIERS):
            self.accepted(action="addModifier", objectName="Host", modifierName=f"m{i}", treeKey="G")
        self.refused(action="addModifier", objectName="Host", modifierName="extra", treeKey="G")

    def test_set_modifier_input_writes_value_through_the_struct_and_tags(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        tags = host.tagged
        self.accepted(action="setModifierInput", objectName="Host", modifierName="GN", socket="Count", value=12)
        self.assertEqual(host.modifiers[0].properties.inputs.Socket_1.value, 12)
        self.assertEqual(host.tagged, tags + 1)
        self.accepted(action="setModifierInput", objectName="Host", modifierName="GN", socket="Socket_1", value=3)
        self.assertEqual(host.modifiers[0].properties.inputs.Socket_1.value, 3)

    def test_set_modifier_input_refusals_change_nothing(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        for socket, value in (("Count", 1.5), ("Count", "x"), ("Count", True), ("Count", None), ("Count", 1e12), ("Nope", 1), ("Geometry", 1), ("", 1)):
            self.refused(action="setModifierInput", objectName="Host", modifierName="GN", socket=socket, value=value)
        self.refused(action="setModifierInput", objectName="Host", modifierName="other", socket="Count", value=1)
        self.assertEqual(host.modifiers[0].properties.inputs.values, {})

    def test_set_modifier_input_by_name_needs_a_unique_name(self):
        tree = self.group([{"inOut": "INPUT", "name": "Dup", "type": "Int"}])
        tree.interface.new_socket("Dup", in_out="INPUT", socket_type="NodeSocketFloat")  # a hand-made group can repeat a name
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        self.refused(action="setModifierInput", objectName="Host", modifierName="GN", socket="Dup", value=1)
        self.accepted(action="setModifierInput", objectName="Host", modifierName="GN", socket="Socket_1", value=1.5)
        self.assertEqual(host.modifiers[0].properties.inputs.Socket_1.value, 1.5)

    # setObjectCustomProperty on a Geometry Nodes host
    def test_custom_property_naming_a_modifier_input_is_refused(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        for name in ("Count", "Socket_1", "customProperties.Count"):
            receipt = self.refused(action="setObjectCustomProperty", targetObjectName="Host", propertyName=name, value=3)
            self.assertIn("setModifierInput", receipt["message"])
        self.assertFalse(hasattr(host, "custom"))

    def test_other_custom_properties_on_the_same_object_still_work(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        self.accepted(action="setObjectCustomProperty", targetObjectName="Host", propertyName="tag", value=3)
        self.assertEqual(host.custom, ("tag", 3))

    # snapshot
    def test_evaluated_snapshot_reports_counts_bounds_and_cap(self):
        host = self.bpy.data.objects["Host"]
        host.modifiers.new("GN", "NODES")
        verts = [NS(co=(float(i), 0.0, 0.0)) for i in range(3)]
        mesh = NS(vertices=verts, edges=[1], polygons=[])
        evaluated = NS(to_mesh=lambda: mesh, to_mesh_clear=lambda: None)
        host.evaluated_get = lambda dg: evaluated
        instances = [NS(is_instance=True, parent=NS(original=host), matrix_world=NS(translation=(0.0, 5.0 + i, 0.0))) for i in range(bt.EVALUATED_POSITION_CAP + 2)]
        instances.append(NS(is_instance=True, parent=NS(original=Obj("other")), matrix_world=NS(translation=(9.0, 9.0, 9.0))))
        instances.append(NS(is_instance=False, parent=None, matrix_world=NS(translation=(8.0, 8.0, 8.0))))
        self.bpy.context = NS(evaluated_depsgraph_get=lambda: NS(update=lambda: None, object_instances=instances))
        data = self.target._evaluated_snapshot(host)
        self.assertEqual((data["vertexCount"], data["edgeCount"], data["instanceCount"]), (3, 1, bt.EVALUATED_POSITION_CAP + 2))
        self.assertEqual((data["boundsMin"], data["boundsMax"]), ([0.0, 0.0, 0.0], [2.0, 5.0 + bt.EVALUATED_POSITION_CAP + 1, 0.0]))
        self.assertEqual((len(data["instanceLocations"]), len(data["vertexLocations"]), data["truncated"]), (bt.EVALUATED_POSITION_CAP, 3, True))

    def test_object_without_modifiers_has_no_evaluated_block(self):
        self.assertIsNone(self.target._evaluated_snapshot(self.bpy.data.objects["Host"]))


if __name__ == "__main__":
    unittest.main()
