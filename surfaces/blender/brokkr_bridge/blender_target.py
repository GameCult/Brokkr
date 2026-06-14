from __future__ import annotations

import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROVIDER_ID = "brokkr.blender_editor"
TOOL_KIND = "blender-editor"
DEFAULT_BROKER_URI = "cultmesh://brokkr"
DEFAULT_CULTMESH_CACHE_PATH = "//.brokkr/blender-editor.ccmp"
DEFAULT_CULTLIB_PY_SRC = "E:/Projects/CultLib-main-work/packages/cultcache-py/src"
DEFAULT_DEBUG_MIRROR_ROOT = "//.brokkr/blender-editor-debug"

HOST_SNAPSHOT_SCHEMA = "brokkr.blender.host_snapshot.v0"
COMMAND_INTENT_SCHEMA = "brokkr.blender.command_intent.v0"
COMMAND_RECEIPT_SCHEMA = "brokkr.blender.command_receipt.v0"

CAPABILITIES = (
    "cultcache.mirror.publish",
    "cultcache.intent.watch",
    "host.status.read",
    "scene.tree.read",
    "object.graph.read",
    "object.transform.write",
    "object.create",
    "object.delete",
    "material.catalog.read",
    "material.assign",
    "selection.read",
    "selection.write",
    "command.receipt.publish",
    "eve.gui.publish",
    "eve.tui.publish",
)


class BrokkrBlenderTarget:
    """Blender-owned adapter target for Brokkr mirror documents."""

    def __init__(self, bpy_module: Any):
        self.bpy = bpy_module
        self.last_snapshot: dict[str, Any] | None = None
        self.last_receipt: dict[str, Any] | None = None
        self._node_key: tuple[str, str, str] | None = None
        self._node: Any | None = None
        self._documents: dict[str, Any] | None = None

    def resolve_cache_path(self, cache_path: str) -> str:
        return self.bpy.path.abspath(cache_path or DEFAULT_CULTMESH_CACHE_PATH)

    def resolve_debug_mirror_root(self, debug_mirror_root: str) -> str:
        return self.bpy.path.abspath(debug_mirror_root or DEFAULT_DEBUG_MIRROR_ROOT)

    def publish_snapshot(
        self,
        context: Any,
        cache_path: str,
        cultlib_py_src: str,
        debug_mirror_root: str = "",
    ) -> dict[str, Any]:
        snapshot = self.capture_snapshot(context)
        node, documents = self._open_node(cache_path, cultlib_py_src)
        node.database.put(documents["host_snapshot"], "blender/host/current", snapshot)
        if debug_mirror_root:
            self._write_debug_document(debug_mirror_root, "blender/host/current.json", snapshot)
        self.last_snapshot = snapshot
        return snapshot

    def drain_commands(
        self,
        context: Any,
        cache_path: str,
        cultlib_py_src: str,
        debug_mirror_root: str = "",
    ) -> list[dict[str, Any]]:
        node, documents = self._open_node(cache_path, cultlib_py_src)
        if debug_mirror_root:
            self._import_debug_command_files(node, documents["command_intent"], debug_mirror_root)

        snapshot = node.database.snapshot()
        commands = snapshot.get(COMMAND_INTENT_SCHEMA, {})
        receipts: list[dict[str, Any]] = []

        for command_key, command in sorted(commands.items()):
            receipt = self.execute_command(context, command)
            self.publish_receipt(cache_path, cultlib_py_src, receipt, debug_mirror_root)
            node.database.delete(documents["command_intent"], command_key)
            receipts.append(receipt)

        return receipts

    def publish_receipt(
        self,
        cache_path: str,
        cultlib_py_src: str,
        receipt: dict[str, Any],
        debug_mirror_root: str = "",
    ) -> None:
        command_id = receipt.get("commandId") or uuid.uuid4().hex
        node, documents = self._open_node(cache_path, cultlib_py_src)
        node.database.put(documents["command_receipt"], f"blender/receipts/{command_id}", receipt)
        if debug_mirror_root:
            self._write_debug_document(debug_mirror_root, f"blender/receipts/{command_id}.json", receipt)
        self.last_receipt = receipt

    def capture_snapshot(self, context: Any) -> dict[str, Any]:
        bpy = self.bpy
        selected = [item.name for item in context.selected_objects if item is not None]
        active_object = context.active_object.name if context.active_object else ""
        active_scene = context.scene.name if context.scene else ""

        return {
            "schema": HOST_SNAPSHOT_SCHEMA,
            "providerId": PROVIDER_ID,
            "toolKind": TOOL_KIND,
            "projectPath": bpy.data.filepath,
            "observedAt": _now(),
            "blenderVersion": ".".join(str(part) for part in bpy.app.version),
            "activeScene": active_scene,
            "activeObjectName": active_object,
            "mode": context.mode,
            "selectedObjectNames": selected,
            "sceneCount": len(bpy.data.scenes),
            "objectCount": len(bpy.data.objects),
            "collectionCount": len(bpy.data.collections),
            "materialCount": len(bpy.data.materials),
            "imageCount": len(bpy.data.images),
            "capabilities": list(CAPABILITIES),
            "scenes": [self._scene_snapshot(scene) for scene in bpy.data.scenes],
            "objects": [self._object_snapshot(obj) for obj in bpy.data.objects],
            "materials": [self._material_snapshot(material) for material in bpy.data.materials],
            "collections": [self._collection_snapshot(collection) for collection in bpy.data.collections],
        }

    def execute_command(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        action = command.get("action", "")
        try:
            if action == "createObject":
                return self._create_object(context, command)
            if action == "deleteObject":
                return self._delete_object(context, command)
            if action == "setObjectTransform":
                return self._set_object_transform(context, command)
            if action == "selectObject":
                return self._select_object(context, command)
            if action == "assignMaterial":
                return self._assign_material(context, command)
            return self._receipt(command, "failed", f"Unsupported Blender command action: {action}", "")
        except Exception as error:
            return self._receipt(command, "failed", str(error), "")

    def _create_object(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        object_type = command.get("objectType", "EMPTY")
        name = command.get("name") or f"Brokkr {object_type.title()}"
        location = _vector(command.get("location"), 3, (0.0, 0.0, 0.0))

        if object_type == "MESH":
            self.bpy.ops.mesh.primitive_cube_add(size=float(command.get("size", 1.0)), location=location)
        elif object_type == "LIGHT":
            self.bpy.ops.object.light_add(type=command.get("lightType", "POINT"), location=location)
        elif object_type == "CAMERA":
            self.bpy.ops.object.camera_add(location=location)
        else:
            self.bpy.ops.object.empty_add(type=command.get("emptyDisplayType", "PLAIN_AXES"), location=location)

        obj = context.object
        obj.name = name
        return self._receipt(command, "accepted", "Blender object created.", obj.name)

    def _delete_object(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_object(command)
        if obj is None:
            return self._receipt(command, "failed", "Target Blender object was not found.", "")
        self.bpy.data.objects.remove(obj, do_unlink=True)
        return self._receipt(command, "accepted", "Blender object deleted.", command.get("targetObjectName", ""))

    def _set_object_transform(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_object(command)
        if obj is None:
            return self._receipt(command, "failed", "Target Blender object was not found.", "")

        if "location" in command:
            obj.location = _vector(command["location"], 3, obj.location)
        if "rotationEuler" in command:
            obj.rotation_euler = _vector(command["rotationEuler"], 3, obj.rotation_euler)
        if "scale" in command:
            obj.scale = _vector(command["scale"], 3, obj.scale)

        return self._receipt(command, "accepted", "Blender object transform updated.", obj.name)

    def _select_object(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_object(command)
        if obj is None:
            return self._receipt(command, "failed", "Target Blender object was not found.", "")

        if command.get("clearSelection", True):
            for existing in context.selected_objects:
                existing.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return self._receipt(command, "accepted", "Blender object selected.", obj.name)

    def _assign_material(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_object(command)
        if obj is None:
            return self._receipt(command, "failed", "Target Blender object was not found.", "")

        material_name = command.get("materialName") or "Brokkr Material"
        material = self.bpy.data.materials.get(material_name) or self.bpy.data.materials.new(material_name)
        if obj.data and hasattr(obj.data, "materials"):
            obj.data.materials.append(material)
            return self._receipt(command, "accepted", "Blender material assigned.", obj.name)
        return self._receipt(command, "failed", "Target object cannot receive materials.", obj.name)

    def _resolve_object(self, command: dict[str, Any]) -> Any:
        name = command.get("targetObjectName") or command.get("objectName")
        return self.bpy.data.objects.get(name) if name else None

    def _scene_snapshot(self, scene: Any) -> dict[str, Any]:
        return {
            "name": scene.name,
            "frameCurrent": scene.frame_current,
            "frameStart": scene.frame_start,
            "frameEnd": scene.frame_end,
            "cameraName": scene.camera.name if scene.camera else "",
            "renderEngine": scene.render.engine,
            "collectionName": scene.collection.name if scene.collection else "",
        }

    def _object_snapshot(self, obj: Any) -> dict[str, Any]:
        data = obj.data if hasattr(obj, "data") else None
        return {
            "name": obj.name,
            "type": obj.type,
            "dataName": data.name if data else "",
            "libraryPath": obj.library.filepath if obj.library else "",
            "location": _to_list(obj.location),
            "rotationEuler": _to_list(obj.rotation_euler),
            "scale": _to_list(obj.scale),
            "visible": bool(obj.visible_get()),
            "selected": bool(obj.select_get()),
            "collections": [collection.name for collection in obj.users_collection],
            "materials": [slot.material.name for slot in obj.material_slots if slot.material],
            "modifiers": [self._modifier_snapshot(modifier) for modifier in obj.modifiers],
            "constraints": [constraint.name for constraint in obj.constraints],
            "mesh": self._mesh_snapshot(data) if obj.type == "MESH" and data else None,
            "customProperties": self._custom_properties(obj.items()),
        }

    def _mesh_snapshot(self, mesh: Any) -> dict[str, Any]:
        return {
            "vertexCount": len(mesh.vertices),
            "edgeCount": len(mesh.edges),
            "polygonCount": len(mesh.polygons),
            "uvLayerCount": len(mesh.uv_layers),
            "shapeKeyCount": len(mesh.shape_keys.key_blocks) if mesh.shape_keys else 0,
        }

    def _modifier_snapshot(self, modifier: Any) -> dict[str, Any]:
        return {
            "name": modifier.name,
            "type": modifier.type,
            "showViewport": modifier.show_viewport,
            "showRender": modifier.show_render,
        }

    def _material_snapshot(self, material: Any) -> dict[str, Any]:
        return {
            "name": material.name,
            "useNodes": material.use_nodes,
            "diffuseColor": _to_list(material.diffuse_color),
            "libraryPath": material.library.filepath if material.library else "",
        }

    def _collection_snapshot(self, collection: Any) -> dict[str, Any]:
        return {
            "name": collection.name,
            "objectNames": [obj.name for obj in collection.objects],
            "childCollectionNames": [child.name for child in collection.children],
        }

    def _custom_properties(self, items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key.startswith("_"):
                continue
            result[key] = _jsonable(value)
        return result

    def _receipt(self, command: dict[str, Any], status: str, message: str, object_name: str) -> dict[str, Any]:
        return {
            "schema": COMMAND_RECEIPT_SCHEMA,
            "commandId": command.get("commandId") or uuid.uuid4().hex,
            "action": command.get("action", ""),
            "status": status,
            "message": message,
            "objectName": object_name,
            "observedAt": _now(),
        }

    def _open_node(self, cache_path: str, cultlib_py_src: str) -> tuple[Any, dict[str, Any]]:
        path = self.resolve_cache_path(cache_path)
        source = str(Path(cultlib_py_src or DEFAULT_CULTLIB_PY_SRC))
        runtime_id = PROVIDER_ID
        node_key = (path, source, runtime_id)
        if self._node is not None and self._documents is not None and self._node_key == node_key:
            self._node.database.pull()
            return self._node, self._documents

        cultmesh, cultcache = _load_cultmesh(cultlib_py_src)
        documents = {
            "host_snapshot": cultcache.define_document_type(HOST_SNAPSHOT_SCHEMA),
            "command_intent": cultcache.define_document_type(COMMAND_INTENT_SCHEMA),
            "command_receipt": cultcache.define_document_type(COMMAND_RECEIPT_SCHEMA),
        }
        node = cultmesh.CultMesh.start_node(path, runtime_id=runtime_id)
        for document in documents.values():
            node.database.register_document(document)
        node.database.pull()

        self._node_key = node_key
        self._node = node
        self._documents = documents
        return node, documents

    def _import_debug_command_files(self, node: Any, command_document: Any, debug_mirror_root: str) -> None:
        commands_root = Path(self.resolve_debug_mirror_root(debug_mirror_root)) / "blender" / "commands"
        for command_path in sorted(commands_root.glob("*.json")):
            with command_path.open("r", encoding="utf-8") as handle:
                command = json.load(handle)
            command_id = command.get("commandId") or command_path.stem
            command["schema"] = command.get("schema") or COMMAND_INTENT_SCHEMA
            command["commandId"] = command_id
            node.database.put(command_document, f"blender/commands/{command_id}", command)
            command_path.unlink(missing_ok=True)

    def _write_debug_document(self, debug_mirror_root: str, relative_path: str, document: dict[str, Any]) -> None:
        path = Path(self.resolve_debug_mirror_root(debug_mirror_root)) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)


def _load_cultmesh(cultlib_py_src: str) -> tuple[Any, Any]:
    source = Path(cultlib_py_src or DEFAULT_CULTLIB_PY_SRC)
    if source.exists():
        source_text = str(source)
        if source_text not in sys.path:
            sys.path.insert(0, source_text)
    try:
        import cultmesh_py  # type: ignore
        import cultcache_py  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Brokkr Blender target requires CultLib's Python CultMesh package. Set CultLib Python Source "
            "to the CultLib packages/cultcache-py/src directory or install cultcache-py into Blender's Python."
        ) from exc
    return cultmesh_py, cultcache_py


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_list(value: Any) -> list[float]:
    return [float(item) for item in value]


def _vector(value: Any, size: int, fallback: Any) -> tuple[float, ...]:
    if value is None:
        return tuple(float(item) for item in fallback)
    result = [float(item) for item in value[:size]]
    while len(result) < size:
        result.append(0.0)
    return tuple(result)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)
