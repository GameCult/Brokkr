"""Geometry node graph command actions: createNodeGroup, addNode, linkSockets, addModifier, setModifierInput.

Owner of how an intent becomes a node group, a node, a link or a modifier input on Blender 5.2.
Validation is plain Python and runs before bpy is touched; apply steps that can still fail after
Blender has been asked (an unknown node type, an enum that is not offered) undo what they made, so a
refused intent leaves the tree as it was. Docs: docs/blender-node-graphs.md.
"""
from __future__ import annotations

import math
import re
from typing import Any

from .scene_actions import ActionRefused

ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,63}")
KEY_PATTERN = re.compile(r"[A-Za-z0-9 ._-]{1,63}")
# A geometry tree may hold geometry, function and shader math nodes. Nodes that read or write files,
# run code, write caches or nest groups are not part of this cut.
NODE_IDNAME = re.compile(r"(GeometryNode|FunctionNode|ShaderNode)[A-Za-z0-9]+")
NODE_DENIED = ("Import", "Export", "Script", "Bake", "Group", "Simulation", "Repeat", "Foreach", "Viewer", "TexImage", "TexEnvironment")
MAX_NODES = 500
MAX_INTERFACE = 64
MAX_MODIFIERS = 8
MAX_VALUE = 1.0e9
MAX_INT = 4096  # counts, levels and sizes multiply: a 4096 x 4096 grid is the ceiling
SOCKET_TYPES = {"Geometry": "NodeSocketGeometry", "Float": "NodeSocketFloat", "Int": "NodeSocketInt",
                "Bool": "NodeSocketBool", "Vector": "NodeSocketVector"}
IN_OUT = {"INPUT", "OUTPUT"}
# Node properties that are not node settings, or that make a node reach outside the tree.
NODE_PROPERTY_DENIED = frozenset({"name", "label", "location", "width", "height", "parent", "node_tree", "select",
                                  "mute", "hide", "show_options", "show_preview", "show_texture", "use_custom_color",
                                  "color", "bl_idname", "bl_label", "bl_description", "bl_icon", "bl_static_type",
                                  "bl_width_default", "bl_width_min", "bl_width_max", "bl_height_default",
                                  "bl_height_min", "bl_height_max", "rna_type", "type", "internal_links"})
SETTABLE_PROPERTY_TYPES = ("ENUM", "BOOLEAN", "INT", "FLOAT")


def text(command: dict[str, Any], key: str, pattern: re.Pattern, label: str, *, required: bool = True) -> str:
    value = command.get(key)
    if value is None or value == "":
        if required:
            raise ActionRefused(f"{label} is required.")
        return ""
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ActionRefused(f"{label} must be 1..63 characters of letters, digits, '.', '_' or '-'.")
    return value


def tree_key(command: dict[str, Any]) -> str:
    kind = command.get("treeKind", "geometry")
    if kind != "geometry":
        raise ActionRefused(f"treeKind {kind!r} is not supported; only 'geometry'.")
    return text(command, "treeKey", KEY_PATTERN, "treeKey")


def finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > MAX_VALUE:
        raise ActionRefused(f"{label} must be a finite number within +-{MAX_VALUE:g}.")
    return float(value)


def typed_value(value: Any, kind: str, label: str) -> Any:
    """A value for a socket of `kind` (Blender's socket.type, or the interface type's tail), or ActionRefused."""
    if kind in ("VALUE", "FLOAT", "Float"):
        return finite(value, label)
    if kind in ("INT", "Int"):
        number = finite(value, label)
        if number != int(number) or abs(number) > MAX_INT:
            raise ActionRefused(f"{label} must be a whole number within +-{MAX_INT}.")
        return int(number)
    if kind in ("BOOLEAN", "Bool"):
        if not isinstance(value, bool):
            raise ActionRefused(f"{label} must be true or false.")
        return value
    if kind in ("VECTOR", "Vector", "RGBA"):
        size = 4 if kind == "RGBA" else 3
        if not isinstance(value, (list, tuple)) or len(value) != size:
            raise ActionRefused(f"{label} must be exactly {size} numbers.")
        return tuple(finite(part, f"{label}[{i}]") for i, part in enumerate(value))
    raise ActionRefused(f"{label}: socket type {kind} cannot be set by an intent.")


def check_idname(idname: Any) -> str:
    if not isinstance(idname, str) or not NODE_IDNAME.fullmatch(idname):
        raise ActionRefused("blIdname must be a GeometryNode*, FunctionNode* or ShaderNode* type.")
    for denied in NODE_DENIED:
        if denied in idname:
            raise ActionRefused(f"node type {idname} is not allowed in this cut ({denied}).")
    return idname


def check_interface(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list) or not items or len(items) > MAX_INTERFACE:
        raise ActionRefused(f"interface must be a list of 1..{MAX_INTERFACE} sockets.")
    seen: set[tuple[str, str]] = set()
    result = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ActionRefused(f"interface[{i}] must be an object.")
        in_out = str(item.get("inOut", "")).upper()
        name = item.get("name")
        socket_type = item.get("type")
        if in_out not in IN_OUT or not isinstance(name, str) or not name or len(name) > 63 or socket_type not in SOCKET_TYPES:
            raise ActionRefused(f"interface[{i}] needs inOut INPUT|OUTPUT, a name and a type of {sorted(SOCKET_TYPES)}.")
        if (in_out, name) in seen:
            raise ActionRefused(f"interface[{i}] repeats {in_out} socket {name!r}.")
        seen.add((in_out, name))
        entry = {"inOut": in_out, "name": name, "type": socket_type}
        if "default" in item:
            entry["default"] = typed_value(item["default"], socket_type, f"interface[{i}].default")
        result.append(entry)
    return result


class NodeActions:
    """Applies the node-graph actions to a bpy module. Stateless: every lookup goes to bpy.data."""

    ACTIONS = ("createNodeGroup", "addNode", "linkSockets", "addModifier", "setModifierInput")

    def __init__(self, bpy_module: Any):
        self.bpy = bpy_module

    def execute(self, action: str, command: dict[str, Any]) -> tuple[str, str]:
        return getattr(self, "_" + action)(command)

    # tree and node lookup
    def _tree(self, key: str) -> Any:
        tree = self.bpy.data.node_groups.get(key)
        if tree is None:
            raise ActionRefused(f"Node group {key!r} does not exist; createNodeGroup first.")
        if tree.bl_idname != "GeometryNodeTree":
            raise ActionRefused(f"Node group {key!r} is not a geometry node group.")
        if getattr(tree, "library", None):
            raise ActionRefused(f"Node group {key!r} is linked from a library and read-only.")
        return tree

    @staticmethod
    def _node(tree: Any, node_id: str) -> Any:
        for node in tree.nodes:
            if node.get("brokkr_id") == node_id:
                return node
        raise ActionRefused(f"Node {node_id!r} does not exist in {tree.name!r}.")

    @staticmethod
    def _socket(sockets: Any, key: str, label: str) -> Any:
        """A socket of a node by identifier, else by display name when exactly one available socket has it."""
        usable = [s for s in sockets if s.identifier and getattr(s, "enabled", True)]
        for socket in usable:
            if socket.identifier == key:
                return socket
        named = [s for s in usable if s.name == key]
        if len(named) == 1:
            return named[0]
        raise ActionRefused(f"{label}: socket {key!r} " + ("is ambiguous by name; use its identifier." if named else "was not found."))

    # actions
    def _createNodeGroup(self, command: dict[str, Any]) -> tuple[str, str]:
        key = tree_key(command)
        interface = check_interface(command.get("interface"))
        existing = self.bpy.data.node_groups.get(key)
        if existing is not None:
            raise ActionRefused(f"Node group {key!r} already exists.")
        tree = self.bpy.data.node_groups.new(key, "GeometryNodeTree")
        try:
            made = []
            for entry in interface:
                socket = tree.interface.new_socket(entry["name"], in_out=entry["inOut"], socket_type=SOCKET_TYPES[entry["type"]])
                if "default" in entry:
                    socket.default_value = entry["default"]
                made.append(f"{entry['inOut'].lower()} {entry['name']}={socket.identifier}")
            for node_id, idname in (("gin", "NodeGroupInput"), ("gout", "NodeGroupOutput")):
                node = tree.nodes.new(idname)
                node["brokkr_id"] = node_id
        except Exception:
            self.bpy.data.node_groups.remove(tree)
            raise
        return "Created node group; interface identifiers: " + ", ".join(made), tree.name

    def _addNode(self, command: dict[str, Any]) -> tuple[str, str]:
        tree = self._tree(tree_key(command))
        node_id = text(command, "id", ID_PATTERN, "id")
        idname = check_idname(command.get("blIdname"))
        location = command.get("location", [0, 0])
        if not isinstance(location, (list, tuple)) or len(location) != 2:
            raise ActionRefused("location must be two numbers.")
        location = [finite(part, "location") for part in location]
        properties = command.get("properties") or {}
        inputs = command.get("inputs") or {}
        if not isinstance(properties, dict) or not isinstance(inputs, dict):
            raise ActionRefused("properties and inputs must be objects.")
        if any(n.get("brokkr_id") == node_id for n in tree.nodes):
            raise ActionRefused(f"Node id {node_id!r} already exists in {tree.name!r}.")
        if len(tree.nodes) >= MAX_NODES:
            raise ActionRefused(f"Node group {tree.name!r} already has {MAX_NODES} nodes.")
        try:
            node = tree.nodes.new(idname)
        except RuntimeError as error:
            raise ActionRefused(f"Blender does not offer node type {idname}: {error}") from None
        try:
            node["brokkr_id"] = node_id
            node.location = location
            if command.get("label"):
                node.label = str(command["label"])[:63]
            for name, value in properties.items():  # node settings first: they decide which sockets exist
                self._set_property(node, name, value)
            for name, value in inputs.items():
                socket = self._socket(node.inputs, name, f"input {name!r}")
                if socket.is_linked or not hasattr(socket, "default_value"):
                    raise ActionRefused(f"input {name!r} has no settable default.")
                socket.default_value = typed_value(value, socket.type, f"input {name!r}")
        except Exception:
            tree.nodes.remove(node)
            raise
        return "Node added.", node_id

    def _set_property(self, node: Any, name: str, value: Any) -> None:
        prop = node.bl_rna.properties.get(name) if isinstance(name, str) else None
        if prop is None or prop.is_readonly or name in NODE_PROPERTY_DENIED or prop.type not in SETTABLE_PROPERTY_TYPES:
            raise ActionRefused(f"{node.bl_idname} has no settable property {name!r}.")
        if prop.type == "ENUM":
            if not isinstance(value, str):
                raise ActionRefused(f"property {name!r} needs an enum identifier.")
        else:
            value = typed_value(value, {"BOOLEAN": "BOOLEAN", "INT": "INT", "FLOAT": "FLOAT"}[prop.type], f"property {name!r}")
        try:
            setattr(node, name, value)
        except (TypeError, ValueError) as error:
            raise ActionRefused(f"property {name!r} cannot be {value!r}: {error}") from None

    def _linkSockets(self, command: dict[str, Any]) -> tuple[str, str]:
        tree = self._tree(tree_key(command))
        source = self._node(tree, text(command, "fromNode", ID_PATTERN, "fromNode"))
        target = self._node(tree, text(command, "toNode", ID_PATTERN, "toNode"))
        out = self._socket(source.outputs, str(command.get("fromSocket", "")), "fromSocket")
        into = self._socket(target.inputs, str(command.get("toSocket", "")), "toSocket")
        displaced = [l.from_socket for l in tree.links if l.to_socket == into] if not getattr(into, "is_multi_input", False) else []
        link = tree.links.new(out, into)  # replaces whatever single link the input had
        if not link.is_valid:
            tree.links.remove(link)
            for old in displaced:
                tree.links.new(old, into)
            raise ActionRefused(f"Link {out.name} -> {into.name} is not valid (type or field/single-value mismatch).")
        return f"Linked {source.get('brokkr_id')}.{out.identifier} -> {target.get('brokkr_id')}.{into.identifier}.", tree.name

    def _object(self, command: dict[str, Any]) -> Any:
        name = command.get("objectName") or command.get("targetObjectName")
        obj = self.bpy.data.objects.get(name) if name else None
        if obj is None:
            raise ActionRefused(f"Object {name!r} was not found.")
        return obj

    def _addModifier(self, command: dict[str, Any]) -> tuple[str, str]:
        obj = self._object(command)
        kind = command.get("modifierType", "NODES")
        if kind != "NODES":
            raise ActionRefused("modifierType must be NODES; other modifiers are not part of this cut.")
        tree = self._tree(tree_key(command))
        name = text(command, "modifierName", KEY_PATTERN, "modifierName", required=False) or "Brokkr GeoNodes"
        modifier = obj.modifiers.get(name)
        if modifier is not None and modifier.type != "NODES":
            raise ActionRefused(f"{obj.name!r} already has a non-Geometry-Nodes modifier named {name!r}.")
        if modifier is None:
            if len(obj.modifiers) >= MAX_MODIFIERS:
                raise ActionRefused(f"{obj.name!r} already has {MAX_MODIFIERS} modifiers.")
            modifier = obj.modifiers.new(name, "NODES")
            if modifier is None:
                raise ActionRefused(f"{obj.name!r} is a {obj.type} object; it cannot take a Geometry Nodes modifier.")
        modifier.node_group = tree
        obj.update_tag()
        return "Geometry Nodes modifier set.", obj.name

    def _setModifierInput(self, command: dict[str, Any]) -> tuple[str, str]:
        obj = self._object(command)
        modifier = obj.modifiers.get(str(command.get("modifierName") or "Brokkr GeoNodes"))
        if modifier is None or modifier.type != "NODES" or modifier.node_group is None:
            raise ActionRefused(f"{obj.name!r} has no Geometry Nodes modifier with a node group of that name.")
        item = modifier_input(modifier.node_group, str(command.get("socket", "")))
        value = typed_value(command.get("value"), item.socket_type.replace("NodeSocket", ""), f"input {item.name!r}")
        # modifier.properties.inputs[id] is a raw IDPropertyGroup on 5.2.3; attribute access reaches the struct.
        getattr(modifier.properties.inputs, item.identifier).value = value
        obj.update_tag()  # without it a headless re-evaluation returned the previous result
        return f"Modifier input {item.name} set.", obj.name


def modifier_input(tree: Any, key: str) -> Any:
    """An INPUT socket of a group's interface, by identifier or by its unique name."""
    items = [i for i in tree.interface.items_tree if i.item_type == "SOCKET" and i.in_out == "INPUT"]
    for item in items:
        if item.identifier == key:
            return item
    named = [i for i in items if i.name == key]
    if len(named) == 1:
        return named[0]
    raise ActionRefused(f"Interface input {key!r} " + ("is ambiguous by name; use its identifier." if named else "was not found."))


def drives_modifier_input(obj: Any, property_name: str) -> str:
    """The modifier whose group has an interface input with identifier property_name (Socket_N), else ''.
    An object custom property never drives a modifier input, so only the modifier's own identifiers are
    refused; a property that merely shares an input's display name is an ordinary custom property."""
    for modifier in obj.modifiers:
        if modifier.type == "NODES" and modifier.node_group is not None:
            for item in modifier.node_group.interface.items_tree:
                if item.item_type == "SOCKET" and item.in_out == "INPUT" and property_name == item.identifier:
                    return modifier.name
    return ""
