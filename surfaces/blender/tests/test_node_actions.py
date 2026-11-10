"""Node-graph action tests. No Blender: a fake bpy with just enough node-tree surface.

Run: python3 -m unittest discover -s surfaces/blender/tests -v
The real API is exercised by tests/live/gn_actions.py.
"""
from __future__ import annotations

import sys
import types
import unittest
import unittest.mock
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

    counter = 1000

    def as_pointer(self):
        return self.pointer

    PROPS = {"operation": NS(type="ENUM", is_readonly=False), "flag": NS(type="BOOLEAN", is_readonly=False),
             "filepath": NS(type="STRING", is_readonly=False), "location": NS(type="FLOAT", is_readonly=False)}

    def __init__(self, idname):
        super().__init__()
        self.bl_idname, self.location, self.label, self.operation, self.flag = idname, [0, 0], "", "ADD", False
        Node.counter += 1
        self.pointer = Node.counter
        self.bl_rna = NS(properties=self.PROPS)
        self.inputs = [Sock("A", "A"), Sock("Size", "Size", "VECTOR", (1.0, 1.0, 1.0)), Sock("B", "Dup"), Sock("B_VEC", "Dup")]
        self.outputs = [Sock("Out", "Out")]
        for socket in self.inputs + self.outputs:
            socket.node = self

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


class Proxy:
    """A fresh wrapper per access, as bpy hands out: equal by pointer, with a different id() each time."""

    def __init__(self, node):
        self._node = node

    def as_pointer(self):
        return self._node.pointer

    def __getattr__(self, name):
        return getattr(self._node, name)

    def __eq__(self, other):
        return getattr(other, "pointer", None) == self._node.pointer or (isinstance(other, Proxy) and other._node is self._node)

    __hash__ = None


class Links(list):
    def __init__(self, valid=True):
        super().__init__()
        self.valid = valid

    def new(self, a, b):
        for old in [l for l in self if l.to_socket is b]:  # a single-link input loses its old link, as in Blender
            list.remove(self, old)
        link = NS(from_socket=a, to_socket=b, from_node=Proxy(a.node), to_node=Proxy(b.node), is_muted=False, is_valid=self.valid(a, b) if callable(self.valid) else self.valid)
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
    refuses = False

    def get(self, name):
        return next((m for m in self if m.name == name), None)

    def remove(self, modifier):
        list.remove(self, modifier)

    def new(self, name, kind):
        if self.refuses:
            return None  # Blender returns None for object types without modifiers
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
        self.accepted(action="addNode", treeKey="G", id="b", blIdname="ShaderNodeMath")
        tree.nodes[-1].inputs[3].enabled = False
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="b", toSocket="Dup")

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

    # removal, unlinking, cycles
    def chain(self):
        tree = self.group()
        for node_id in ("a", "b", "c"):
            self.accepted(action="addNode", treeKey="G", id=node_id, blIdname="ShaderNodeMath")
        return tree

    def test_cycles_and_self_links_are_refused_and_change_nothing(self):
        tree = self.chain()
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="b", toSocket="A")
        self.accepted(action="linkSockets", treeKey="G", fromNode="b", fromSocket="Out", toNode="c", toSocket="A")
        before = list(tree.links)
        for src, dst in (("c", "a"), ("b", "a"), ("a", "a"), ("c", "b")):
            receipt = self.refused(action="linkSockets", treeKey="G", fromNode=src, fromSocket="Out", toNode=dst, toSocket="Size")
            self.assertIn("cycle", receipt["message"])
        self.assertEqual(list(tree.links), before)
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="c", toSocket="Size")  # a forward skip is no cycle

    def test_cycle_detection_survives_fresh_node_wrappers_on_long_chains(self):
        tree = self.group()
        ids = [f"n{i}" for i in range(12)]
        for node_id in ids:
            self.accepted(action="addNode", treeKey="G", id=node_id, blIdname="ShaderNodeMath")
        for a, b in zip(ids, ids[1:]):
            self.accepted(action="linkSockets", treeKey="G", fromNode=a, fromSocket="Out", toNode=b, toSocket="A")
        # a diamond ladder: every rung reachable two ways
        for a, b in zip(ids[:-2], ids[2:]):
            self.accepted(action="linkSockets", treeKey="G", fromNode=a, fromSocket="Out", toNode=b, toSocket="Size")
        count = len(tree.links)
        for head in ids[:-1]:
            self.refused(action="linkSockets", treeKey="G", fromNode=ids[-1], fromSocket="Out", toNode=head, toSocket="Size")
        self.assertEqual(len(tree.links), count)

    def test_cycle_through_a_later_branch_is_found(self):
        tree = self.group()
        for node_id in "abcd":
            self.accepted(action="addNode", treeKey="G", id=node_id, blIdname="ShaderNodeMath")
        for src, dst in (("a", "b"), ("a", "c"), ("c", "d")):
            self.accepted(action="linkSockets", treeKey="G", fromNode=src, fromSocket="Out", toNode=dst, toSocket="A")
        self.refused(action="linkSockets", treeKey="G", fromNode="d", fromSocket="Out", toNode="a", toSocket="A")

    def test_cycle_walk_visits_each_node_once_on_a_ladder(self):
        tree = self.group()
        ids = [f"n{i}" for i in range(40)]
        for node_id in ids:
            self.accepted(action="addNode", treeKey="G", id=node_id, blIdname="ShaderNodeMath")
        for a, b in zip(ids, ids[1:]):
            tree.links.new(tree.nodes[2 + ids.index(a)].outputs[0], tree.nodes[2 + ids.index(b)].inputs[0])
        for a, b in zip(ids, ids[2:]):
            tree.links.new(tree.nodes[2 + ids.index(a)].outputs[0], tree.nodes[2 + ids.index(b)].inputs[1])
        calls = []
        real = na.node_key
        with unittest.mock.patch.object(na, "node_key", lambda n: calls.append(1) or real(n)):
            self.assertFalse(na.reaches(tree, tree.nodes[2], NS(pointer=-1, as_pointer=lambda: -1)))
        self.assertLess(len(calls), 4 * len(tree.links))

    def test_remove_node(self):
        tree = self.chain()
        self.accepted(action="removeNode", treeKey="G", id="b")
        self.assertEqual([n.get("brokkr_id") for n in tree.nodes], ["gin", "gout", "a", "c"])
        again = self.accepted(action="removeNode", treeKey="G", id="b")
        self.assertIn("already absent", again["message"])
        for keep in ("gin", "gout"):
            self.refused(action="removeNode", treeKey="G", id=keep)
        self.refused(action="removeNode", treeKey="Nope", id="a")
        self.refused(action="removeNode", treeKey="G", id="a b")

    def test_unlink_removes_only_the_matching_links(self):
        tree = self.chain()
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="c", toSocket="A")
        self.accepted(action="linkSockets", treeKey="G", fromNode="b", fromSocket="Out", toNode="c", toSocket="Size")
        self.refused(action="unlinkSockets", treeKey="G", fromNode="zzz", fromSocket="Out", toNode="c", toSocket="A")
        self.assertIn("Removed 0", self.accepted(action="unlinkSockets", treeKey="G", fromNode="b", fromSocket="Out", toNode="c", toSocket="A")["message"])
        self.assertEqual(len(tree.links), 2)
        self.assertIn("Removed 1", self.accepted(action="unlinkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="c", toSocket="A")["message"])
        self.assertEqual(len(tree.links), 1)
        self.accepted(action="unlinkSockets", treeKey="G", toNode="c", toSocket="Size")
        self.assertEqual(len(tree.links), 0)
        self.refused(action="unlinkSockets", treeKey="G", fromNode="a", toNode="c", toSocket="A")  # a source node needs its socket

    def test_remove_modifier_takes_only_geometry_nodes_modifiers(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        host.modifiers.new("Sub", "SUBSURF")
        tags = host.tagged
        self.refused(action="removeModifier", objectName="Host", modifierName="Sub")
        self.assertEqual([m.name for m in host.modifiers], ["GN", "Sub"])
        self.accepted(action="removeModifier", objectName="Host", modifierName="GN")
        self.assertEqual([m.name for m in host.modifiers], ["Sub"])
        self.assertEqual(host.tagged, tags + 1)
        self.assertIn("already absent", self.accepted(action="removeModifier", objectName="Host", modifierName="GN")["message"])
        self.refused(action="removeModifier", objectName="Nope", modifierName="GN")
        for bad in (["x"], "x" * 256, "a\0b", 5):
            self.refused(action="removeModifier", objectName="Host", modifierName=bad)
        host.modifiers.new("Gé x/y", "NODES")  # made by hand: any name Blender allows can be removed
        self.accepted(action="removeModifier", objectName="Host", modifierName="Gé x/y")
        self.assertEqual([m.name for m in host.modifiers], ["Sub"])

    # setObjectCustomProperty on a Geometry Nodes host
    def test_custom_property_naming_a_modifier_input_identifier_is_refused(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        for name in ("Socket_1", "customProperties.Socket_1"):
            receipt = self.refused(action="setObjectCustomProperty", targetObjectName="Host", propertyName=name, value=3)
            self.assertIn("setModifierInput", receipt["message"])
        self.assertFalse(hasattr(host, "custom"))

    def test_custom_property_sharing_only_a_display_name_is_an_ordinary_property(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        self.accepted(action="setObjectCustomProperty", targetObjectName="Host", propertyName="Count", value=3)
        self.assertEqual(host.custom, ("Count", 3))

    def test_other_custom_properties_on_the_same_object_still_work(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        self.accepted(action="addModifier", objectName="Host", modifierName="GN", treeKey="G")
        self.accepted(action="setObjectCustomProperty", targetObjectName="Host", propertyName="tag", value=3)
        self.assertEqual(host.custom, ("tag", 3))

    # review fixes
    def test_refused_link_restores_the_link_it_displaced(self):
        tree = self.group()
        self.accepted(action="addNode", treeKey="G", id="a", blIdname="ShaderNodeMath")
        self.accepted(action="addNode", treeKey="G", id="b", blIdname="ShaderNodeMath")
        self.accepted(action="addNode", treeKey="G", id="c", blIdname="ShaderNodeMath")
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="c", toSocket="A")
        tree.links.valid = lambda a, b: a is not tree.nodes[3].outputs[0]  # b.Out -> anything is invalid
        self.refused(action="linkSockets", treeKey="G", fromNode="b", fromSocket="Out", toNode="c", toSocket="A")
        self.assertEqual([(l.from_socket, l.to_socket) for l in tree.links], [(tree.nodes[2].outputs[0], tree.nodes[4].inputs[0])])

    def test_refused_link_restores_the_displaced_link_muted_state(self):
        tree = self.group()
        for node_id in ("a", "b", "c"):
            self.accepted(action="addNode", treeKey="G", id=node_id, blIdname="ShaderNodeMath")
        self.accepted(action="linkSockets", treeKey="G", fromNode="a", fromSocket="Out", toNode="c", toSocket="A")
        tree.links[0].is_muted = True
        tree.links.valid = lambda a, b: False
        self.refused(action="linkSockets", treeKey="G", fromNode="b", fromSocket="Out", toNode="c", toSocket="A")
        self.assertEqual([l.is_muted for l in tree.links], [True])

    def test_ints_are_capped_and_patterns_reject_trailing_newlines(self):
        self.group()
        self.accepted(action="addNode", treeKey="G", id="ok", blIdname="ShaderNodeMath")
        self.refused(action="addNode", treeKey="G", id="a\n", blIdname="ShaderNodeMath")
        self.refused(action="createNodeGroup", treeKey="T\n", interface=[{"inOut": "INPUT", "name": "a", "type": "Int"}])
        self.refused(action="createNodeGroup", treeKey="H", interface=[{"inOut": "INPUT", "name": "a", "type": "Int", "default": na.MAX_INT + 1}])
        self.accepted(action="createNodeGroup", treeKey="H", interface=[{"inOut": "INPUT", "name": "a", "type": "Int", "default": na.MAX_INT}])

    def test_modifier_on_an_object_type_without_modifiers_is_a_clear_refusal(self):
        self.group()
        host = self.bpy.data.objects["Host"]
        host.modifiers.refuses = True
        host.type = "CAMERA"
        receipt = self.refused(action="addModifier", objectName="Host", treeKey="G")
        self.assertIn("CAMERA", receipt["message"])

    # snapshot
    def snapshot_fixture(self, coords, instances):
        host = self.bpy.data.objects["Host"]
        host.modifiers.new("GN", "NODES")

        class Verts(list):
            def foreach_get(self_inner, name, buffer):
                flat = [c for v in self_inner for c in v.co]
                buffer[:] = type(buffer)("f", flat)

        mesh = NS(vertices=Verts(NS(co=c) for c in coords), edges=[1], polygons=[])
        evaluated = NS(to_mesh=lambda: mesh, to_mesh_clear=lambda: None)
        host.evaluated_get = lambda dg: evaluated
        self.bpy.context = NS(evaluated_depsgraph_get=lambda: NS(update=lambda: None, object_instances=instances))
        return host

    @staticmethod
    def instance(parent, point, is_instance=True):
        return NS(is_instance=is_instance, parent=NS(original=parent) if parent else None, matrix_world=NS(translation=point))

    def evaluated(self, host):
        return self.target._evaluated_snapshot(host, self.target._instance_scan())

    def test_evaluated_snapshot_reports_counts_separate_bounds_and_cap(self):
        host = self.bpy.data.objects["Host"]
        n = bt.EVALUATED_POSITION_CAP + 2
        other = Obj("other")
        instances = [self.instance(host, (0.0, 5.0 + i, 0.0)) for i in range(n)] + [self.instance(other, (9.0, 9.0, 9.0)), self.instance(None, (8.0, 8.0, 8.0), False)]
        host = self.snapshot_fixture([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)], instances)
        data = self.evaluated(host)
        self.assertEqual((data["vertexCount"], data["edgeCount"], data["instanceCount"]), (3, 1, n))
        self.assertEqual((data["vertexBoundsMin"], data["vertexBoundsMax"]), ([0.0, 0.0, 0.0], [2.0, 0.0, 0.0]))
        self.assertEqual((data["instanceBoundsMin"], data["instanceBoundsMax"]), ([0.0, 5.0, 0.0], [0.0, 5.0 + n - 1, 0.0]))
        self.assertEqual((len(data["instanceLocations"]), len(data["vertexLocations"]), data["truncated"]), (bt.EVALUATED_POSITION_CAP, 3, True))
        self.assertFalse(data["nonFinite"])

    def test_non_finite_positions_are_flagged_not_published(self):
        host = self.snapshot_fixture([(0.0, 0.0, 0.0), (float("inf"), 0.0, 0.0)], [])
        data = self.evaluated(host)
        self.assertTrue(data["nonFinite"])
        self.assertEqual((data["vertexLocations"], data["vertexBoundsMin"], data["vertexBoundsMax"]), ([], [], []))
        host = self.snapshot_fixture([(0.0, 0.0, 0.0)], [self.instance(host, (float("nan"), 0.0, 0.0))])
        data = self.evaluated(host)
        self.assertTrue(data["nonFinite"] and data["instanceLocations"] == [] and data["instanceBoundsMin"] == [])

    def test_a_huge_evaluated_mesh_reports_counts_only(self):
        host = self.snapshot_fixture([(0.0, 0.0, 0.0)] * 3, [])
        with unittest.mock.patch.object(bt, "EVALUATED_VERTEX_LIMIT", 2):
            data = self.evaluated(host)
        self.assertEqual((data["vertexCount"], data["positionsSkipped"], data["vertexLocations"], data["vertexBoundsMin"]), (3, True, [], []))

    def test_per_object_snapshots_reuse_the_one_scan(self):
        host = self.snapshot_fixture([(0.0, 0.0, 0.0)], [])
        calls = []
        get = self.bpy.context.evaluated_depsgraph_get
        self.bpy.context.evaluated_depsgraph_get = lambda: calls.append(1) or get()
        scan = self.target._instance_scan()
        for _ in range(3):
            self.target._evaluated_snapshot(host, scan)
        self.assertEqual(len(calls), 1)

    def test_instance_scan_stops_at_the_limit_and_says_so(self):
        host = self.bpy.data.objects["Host"]
        visited = []

        def many():
            for i in range(50):
                visited.append(i)
                yield self.instance(host, (float(i), 0.0, 0.0))

        host = self.snapshot_fixture([(0.0, 0.0, 0.0)], many())
        with unittest.mock.patch.object(bt, "EVALUATED_INSTANCE_SCAN_LIMIT", 10):
            scan = self.target._instance_scan()
        data = self.target._evaluated_snapshot(host, scan)
        self.assertEqual((data["instanceCount"], data["instancesComplete"]), (10, False))
        other = Obj("Other")
        other.modifiers.new("GN", "NODES")
        other.evaluated_get = host.evaluated_get
        self.assertIsNone(self.target._evaluated_snapshot(other, scan)["instanceCount"])  # never reached: unknown, not 0
        self.assertLessEqual(len(visited), 11)  # the generator is abandoned, not drained
        host = self.snapshot_fixture([(0.0, 0.0, 0.0)], [self.instance(host, (1.0, 0.0, 0.0))])
        self.assertTrue(self.evaluated(host)["instancesComplete"])

    def test_object_without_modifiers_has_no_evaluated_block(self):
        self.assertIsNone(self.target._evaluated_snapshot(self.bpy.data.objects["Host"], None))
        self.assertIsNone(self.target._evaluated_snapshot(self.bpy.data.objects["Host"], (None, {}, True)))


if __name__ == "__main__":
    unittest.main()
