from __future__ import annotations

import json
import math
import os
import sys
import uuid
from array import array
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import node_actions as na
from . import scene_actions as sa
from .server_guard import BindRefused, SessionGuard, check_bind, guarded_server_class, is_loopback_host, purge_command_intents

PROVIDER_ID = "brokkr.blender_editor"
TOOL_KIND = "blender-editor"
DEFAULT_BROKER_URI = "cultmesh://brokkr"
DEFAULT_CULTMESH_CACHE_PATH = "//.brokkr/blender-editor.ccmp"
# The CultLib `packages` directory. The Python runtime is three layered
# packages there (cultcache-py, cultnet-py, cultmesh-py); each one's `src` is
# added to sys.path when they are not installed into Blender's interpreter.
DEFAULT_CULTLIB_PY_SRC = "F:/Projects/CultLib/packages"
CULTLIB_PY_PACKAGES = ("cultcache-py", "cultnet-py", "cultmesh-py")
DEFAULT_DEBUG_MIRROR_ROOT = "//.brokkr/blender-editor-debug"

HOST_SNAPSHOT_SCHEMA = "brokkr.blender.host_snapshot.v0"
COMMAND_INTENT_SCHEMA = "brokkr.blender.command_intent.v0"
COMMAND_RECEIPT_SCHEMA = "brokkr.blender.command_receipt.v0"
SYNC_SESSION_SCHEMA = "brokkr.sync.session.v0"
SYNC_OBJECT_BINDING_SCHEMA = "brokkr.sync.object_binding.v0"
SYNC_VAR_SCHEMA = "brokkr.sync.var.v0"
SYNC_TIMELINE_BINDING_SCHEMA = "brokkr.sync.timeline_binding.v0"
SYNC_RECEIPT_SCHEMA = "brokkr.sync.receipt.v0"

EVALUATED_POSITION_CAP = 256
EVALUATED_VERTEX_LIMIT = 1_000_000
EVALUATED_INSTANCE_SCAN_LIMIT = 100_000  # depsgraph items visited per capture; iterating one in Python costs ~5 us

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
    "asset.import.gltf",
    "asset.export.gltf",
    "camera.write",
    "light.write",
    "world.write",
    "render.still",
    "nodegraph.geometry.write",
    "geometry.evaluated.read",
    "command.receipt.publish",
)


class BrokkrBlenderTarget:
    """Blender-owned adapter target for Brokkr mirror documents."""

    def __init__(self, bpy_module: Any):
        self.bpy = bpy_module
        self.last_snapshot: dict[str, Any] | None = None
        self.last_receipt: dict[str, Any] | None = None
        self.last_sync_receipt: dict[str, Any] | None = None
        self.last_auto_drain_error: str = ""
        self._node_key: tuple[str, str, str] | None = None
        self._node: Any | None = None
        self._documents: dict[str, Any] | None = None
        self._server_key: tuple[str, str, str, str, int, int, int] | None = None
        self._server: Any | None = None
        self._guard: SessionGuard | None = None
        self._cultmesh_module: str = ""
        self._debug_mirror_root: str = ""
        self.import_dir: str = ""
        self.output_dir: str = ""
        self.nodes = na.NodeActions(bpy_module)

    def configure_action_dirs(self, import_dir: str, output_dir: str) -> None:
        """The directories importGltf and renderStill may touch; empty leaves that action disabled."""
        self.import_dir = self.bpy.path.abspath(import_dir) if import_dir else ""
        self.output_dir = self.bpy.path.abspath(output_dir) if output_dir else ""

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

    def refresh_sync_receipt(
        self,
        cache_path: str,
        cultlib_py_src: str,
    ) -> dict[str, Any] | None:
        node, _documents = self._open_node(cache_path, cultlib_py_src)
        receipts = node.database.snapshot().get(SYNC_RECEIPT_SCHEMA, {})
        if not receipts:
            self.last_sync_receipt = None
            return None

        self.last_sync_receipt = max(
            receipts.values(),
            key=lambda receipt: receipt.get("observedAt", ""),
        )
        return self.last_sync_receipt

    def publish_object_sync(
        self,
        context: Any,
        cache_path: str,
        cultlib_py_src: str,
        session_id: str,
        display_name: str,
        unity_object_id: str,
        unity_path: str,
        sync_transform: bool,
        sync_parent: bool,
        sync_material: bool,
        sync_visibility: bool,
        sync_custom_properties: bool,
        unity_custom_property_component_type: str = "",
        unity_custom_property_path: str = "",
        blender_custom_property_path: str = "",
    ) -> dict[str, Any]:
        obj = context.active_object
        if obj is None:
            raise RuntimeError("Select a Blender object before publishing object sync.")

        now = _now()
        node, documents = self._open_node(cache_path, cultlib_py_src)
        normalized_session_id = session_id or "default"
        binding_id = _stable_id("object", normalized_session_id, obj.name, unity_object_id)
        session = _sync_session(normalized_session_id, display_name, now)
        binding = {
            "schema": SYNC_OBJECT_BINDING_SCHEMA,
            "bindingId": binding_id,
            "sessionId": normalized_session_id,
            "displayName": obj.name,
            "unityObjectId": unity_object_id,
            "unityPath": unity_path,
            "blenderObjectName": obj.name,
            "blenderCollectionName": obj.users_collection[0].name if obj.users_collection else "",
            "enabled": True,
            "authority": "blender-to-unity",
            "updatedAt": now,
        }

        node.database.put(documents["sync_session"], f"sync/sessions/{normalized_session_id}", session)
        node.database.put(documents["sync_object_binding"], f"sync/bindings/objects/{binding_id}", binding)
        self._put_sync_var(node, documents, normalized_session_id, binding_id, "transform", "Transform", "Transform", "location,rotationEuler,scale", "blender-to-unity", sync_transform, "linear", now)
        self._put_sync_var(node, documents, normalized_session_id, binding_id, "parent", "Parent", "parentId", "parentName", "blender-to-unity", sync_parent, "step", now)
        self._put_sync_var(node, documents, normalized_session_id, binding_id, "active-state", "Active State", "m_IsActive", "visible", "blender-to-unity", sync_visibility, "step", now)
        self._put_sync_var(node, documents, normalized_session_id, binding_id, "material", "Material", "Renderer.m_Materials", "materials", "blender-to-unity", sync_material, "step", now)
        unity_custom_path = _unity_custom_property_path(
            unity_custom_property_component_type,
            unity_custom_property_path,
        )
        blender_custom_path = _blender_custom_property_path(blender_custom_property_path)
        self._put_sync_var(node, documents, normalized_session_id, binding_id, "custom-property", "Custom Property", unity_custom_path, blender_custom_path, "blender-to-unity", sync_custom_properties, "step", now)
        return binding

    def publish_timeline_sync(
        self,
        context: Any,
        cache_path: str,
        cultlib_py_src: str,
        session_id: str,
        display_name: str,
        unity_timeline_object_id: str,
        unity_cinemachine_object_id: str,
        blender_action_name: str,
        sync_frame: bool,
        sync_camera: bool,
    ) -> dict[str, Any]:
        scene = context.scene
        if scene is None:
            raise RuntimeError("Open a Blender scene before publishing timeline sync.")

        now = _now()
        node, documents = self._open_node(cache_path, cultlib_py_src)
        normalized_session_id = session_id or "default"
        action_name = blender_action_name or _active_action_name(context)
        binding_id = _stable_id("timeline", normalized_session_id, scene.name, action_name, unity_timeline_object_id)
        session = _sync_session(normalized_session_id, display_name, now)
        binding = {
            "schema": SYNC_TIMELINE_BINDING_SCHEMA,
            "bindingId": binding_id,
            "sessionId": normalized_session_id,
            "displayName": action_name or scene.name,
            "unityTimelineObjectId": unity_timeline_object_id,
            "unityCinemachineObjectId": unity_cinemachine_object_id,
            "blenderSceneName": scene.name,
            "blenderActionName": action_name,
            "clockAuthority": "blender",
            "frameRate": float(scene.render.fps),
            "syncFrame": bool(sync_frame),
            "syncCamera": bool(sync_camera),
            "enabled": bool(sync_frame or sync_camera),
            "updatedAt": now,
        }

        node.database.put(documents["sync_session"], f"sync/sessions/{normalized_session_id}", session)
        node.database.put(documents["sync_timeline_binding"], f"sync/bindings/timelines/{binding_id}", binding)
        self._put_sync_var(node, documents, normalized_session_id, binding_id, "timeline-frame", "Timeline Frame", "Timeline.time", "scene.frame_current", "blender-to-unity", sync_frame, "linear", now)
        self._put_sync_var(node, documents, normalized_session_id, binding_id, "cinemachine-virtual-camera", "Cinemachine Camera", "CinemachineVirtualCamera", "camera", "blender-to-unity", sync_camera, "linear", now)
        return binding

    def publish_sync_var(
        self,
        cache_path: str,
        cultlib_py_src: str,
        session_id: str,
        session_display_name: str,
        sync_var_display_name: str,
        binding_id: str,
        kind: str,
        unity_property_path: str,
        blender_property_path: str,
        authority: str,
        enabled: bool,
        interpolation: str,
    ) -> dict[str, Any]:
        now = _now()
        node, documents = self._open_node(cache_path, cultlib_py_src)
        normalized_session_id = session_id or "default"
        normalized_kind = kind or "custom-property"
        normalized_binding_id = binding_id or _stable_id(
            "adhoc-binding",
            normalized_session_id,
            normalized_kind,
            unity_property_path,
            blender_property_path,
        )
        session = _sync_session(normalized_session_id, session_display_name, now)
        sync_var_id = _stable_id("var", normalized_session_id, normalized_binding_id, normalized_kind)
        sync_var = {
            "schema": SYNC_VAR_SCHEMA,
            "syncVarId": sync_var_id,
            "sessionId": normalized_session_id,
            "bindingId": normalized_binding_id,
            "displayName": sync_var_display_name or normalized_kind,
            "kind": normalized_kind,
            "unityPropertyPath": unity_property_path,
            "blenderPropertyPath": blender_property_path,
            "authority": authority or "blender-to-unity",
            "enabled": bool(enabled),
            "interpolation": interpolation or "step",
            "updatedAt": now,
        }
        node.database.put(documents["sync_session"], f"sync/sessions/{normalized_session_id}", session)
        node.database.put(documents["sync_var"], f"sync/vars/{sync_var_id}", sync_var)
        return sync_var

    def start_server(
        self,
        cache_path: str,
        cultlib_py_src: str,
        host: str,
        port: int,
        max_snapshot_documents: int,
        max_snapshot_bytes: int,
        debug_mirror_root: str = "",
        allow_non_loopback: bool = False,
        require_token: bool = False,
    ) -> dict[str, Any]:
        try:
            resolved_host = check_bind(host, allow_non_loopback)
        except BindRefused:
            self.enforce_bind_policy(allow_non_loopback)
            raise
        self.enforce_bind_policy(allow_non_loopback)
        node, documents = self._open_node(cache_path, cultlib_py_src)
        server_key = (
            self.resolve_cache_path(cache_path),
            str(Path(cultlib_py_src or DEFAULT_CULTLIB_PY_SRC)),
            node.runtime_id,
            resolved_host,
            int(port),
            int(max_snapshot_documents),
            int(max_snapshot_bytes),
            bool(require_token),
        )
        if self._server is not None and self._server_key == server_key:
            return self.server_status()

        self.stop_server()
        self._cultmesh_module = ""
        self._debug_mirror_root = self.resolve_debug_mirror_root(debug_mirror_root) if debug_mirror_root else ""
        purge_command_intents(node, documents["command_intent"], COMMAND_INTENT_SCHEMA, self._debug_mirror_root)
        cultmesh, _cultcache = _load_cultmesh(cultlib_py_src)
        self._cultmesh_module = str(getattr(cultmesh, "__file__", "") or "")
        verse_catalog = cultmesh.CultMesh.create_verse_catalog()
        peer_catalog = cultmesh.CultMesh.create_peer_catalog()
        server_class = cultmesh.CultMeshLocalServer
        guard = SessionGuard() if require_token else None
        if guard is not None:
            server_class = guarded_server_class(server_class, guard)
        # The add-on's own clients put command intents to this server, so it grants peer writes
        # explicitly: cultmesh_py refuses them by default, and the session token above is what
        # authenticates a peer when it is required. A cultmesh_py older than the gate has no
        # CultMeshGrantAllWrites and already accepts every write.
        grant_all = getattr(cultmesh, "CultMeshGrantAllWrites", None)
        authority_args = {"write_authority": grant_all()} if grant_all is not None else {}
        server = server_class(
            node=node,
            verse_catalog=verse_catalog,
            peer_catalog=peer_catalog,
            host=resolved_host,
            port=int(port),
            display_name="Brokkr Blender Editor",
            max_snapshot_documents=int(max_snapshot_documents),
            max_snapshot_bytes=int(max_snapshot_bytes),
            **authority_args,
        ).start()

        endpoint = f"cultnet://{resolved_host}:{server.port}"
        verse_catalog.upsert(cultmesh.CultMeshVerseDescriptor(
            verse_id="brokkr.blender",
            display_name="Brokkr Blender",
            authority_model="host-owned-editor-mirror",
            compatibility=cultmesh.CultMeshVerseCompatibility(
                transport_version="cultmesh.v0",
                rules_hash="brokkr.blender.v0",
            ),
            discovery_endpoints=(endpoint,),
            authority_runtime_ids=(node.runtime_id,),
            description="Blender editor mirror served by Brokkr through CultMesh Python.",
        ))
        peer_catalog.upsert(cultmesh.CultMeshPeerCard(
            peer_id=node.runtime_id,
            verse_id="brokkr.blender",
            endpoints=(endpoint,),
            roles=("shard-primary", "editor-host", "read-replica"),
            shard_ids=("primary",),
            region="local",
        ))

        self._server = server
        self._server_key = server_key
        self._guard = guard
        return self.server_status()

    def enforce_bind_policy(self, allow_non_loopback: bool) -> None:
        """Stop a running server that is bound beyond loopback when the allow is not set."""
        if self._server is not None and not allow_non_loopback and not is_loopback_host(self._server.host):
            self.stop_server()

    def stop_server(self) -> None:
        was_running = self._server is not None
        try:
            if was_running:
                self._server.stop()
        finally:
            try:
                if self._guard is not None:
                    self._guard.revoke()
            finally:
                try:
                    if was_running and self._node is not None:
                        purge_command_intents(self._node, self._documents["command_intent"], COMMAND_INTENT_SCHEMA, self._debug_mirror_root)
                finally:
                    self._server = None
                    self._server_key = None
                    self._guard = None

    @property
    def session_token(self) -> str:
        """The running server's token, or "" when the server is stopped or the token is off."""
        return self._guard.token if self._guard is not None else ""

    def server_status(self) -> dict[str, Any]:
        if self._server is None:
            return {
                "running": False,
                "endpoint": "",
                "host": "",
                "port": 0,
                "loopback": True,
                "tokenRequired": False,
                "cultmeshModule": "",
            }
        return {
            "running": True,
            "endpoint": f"cultnet://{self._server.host}:{self._server.port}",
            "host": self._server.host,
            "port": self._server.port,
            "loopback": is_loopback_host(self._server.host),
            "tokenRequired": self._guard is not None,
            "cultmeshModule": self._cultmesh_module,
        }

    def capture_snapshot(self, context: Any) -> dict[str, Any]:
        bpy = self.bpy
        scan = self._instance_scan() if any(o.type == "MESH" and len(o.modifiers) for o in bpy.data.objects) else None
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
            "objects": [self._object_snapshot(obj, scan) for obj in bpy.data.objects],
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
            if action == "setObjectVisibility":
                return self._set_object_visibility(context, command)
            if action == "setObjectParent":
                return self._set_object_parent(context, command)
            if action == "setObjectCustomProperty":
                return self._set_object_custom_property(context, command)
            if action == "selectObject":
                return self._select_object(context, command)
            if action == "assignMaterial":
                return self._assign_material(context, command)
            if action == "importGltf":
                return self._import_gltf(context, command)
            if action == "exportGltf":
                return self._export_gltf(context, command)
            if action == "setCamera":
                return self._set_camera(context, command)
            if action == "setLight":
                return self._set_light(context, command)
            if action == "setWorld":
                return self._set_world(context, command)
            if action == "renderStill":
                return self._render_still(context, command)
            if action in na.NodeActions.ACTIONS:
                message, name = self.nodes.execute(action, command)
                return self._receipt(command, "accepted", message, name)
            return self._receipt(command, "failed", f"Unsupported Blender command action: {action}", "")
        except sa.ActionRefused as error:
            return self._receipt(command, "failed", str(error), "")
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

    def _set_object_visibility(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_object(command)
        if obj is None:
            return self._receipt(command, "failed", "Target Blender object was not found.", "")

        visible = bool(command.get("visible", True))
        obj.hide_viewport = not visible
        obj.hide_render = not visible
        return self._receipt(command, "accepted", "Blender object visibility updated.", obj.name)

    def _set_object_parent(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_object(command)
        if obj is None:
            return self._receipt(command, "failed", "Target Blender object was not found.", "")

        parent_name = command.get("parentObjectName") or command.get("parentName") or ""
        parent = self.bpy.data.objects.get(parent_name) if parent_name else None
        if parent_name and parent is None:
            return self._receipt(command, "failed", f"Parent Blender object was not found: {parent_name}", obj.name)

        obj.parent = parent
        return self._receipt(command, "accepted", "Blender object parent updated.", obj.name)

    def _set_object_custom_property(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_object(command)
        if obj is None:
            return self._receipt(command, "failed", "Target Blender object was not found.", "")

        property_name = command.get("propertyName") or "brokkrValue"
        if property_name.startswith("customProperties."):
            property_name = property_name[len("customProperties."):]
        modifier_name = na.drives_modifier_input(obj, property_name)
        if modifier_name:
            return self._receipt(command, "failed", f"{property_name!r} is an input of Geometry Nodes modifier {modifier_name!r}; "
                                 "a custom property does not drive it, use setModifierInput.", obj.name)
        obj[property_name] = command.get("value")
        return self._receipt(command, "accepted", "Blender custom property updated.", obj.name)

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

    def _import_gltf(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        name = str(command.get("filepath") or "")
        path = sa.resolve_inside(self.import_dir, name, "import")
        sa.require_gltf(path)
        stamped = sa.fingerprint([path])  # before the parse, so a swap during it shows
        references = sa.gltf_references(path)
        existing = references  # gltf_references refuses a missing one
        checked = (stamped, sa.fingerprint(existing))
        # Re-check immediately before use: the same path, the same files, the same bytes' stats.
        # Blender then opens the files itself, so a swap in that last gap is not prevented
        # (residual TOCTOU): the import directory must only be writable by trusted users.
        if sa.resolve_inside(self.import_dir, name, "import") != path or \
                (sa.fingerprint([path]), sa.fingerprint(existing)) != checked:
            raise sa.ActionRefused("Import file changed while it was being checked.")
        before = set(self.bpy.data.objects.keys())
        self.bpy.ops.import_scene.gltf(filepath=str(path))
        added = sorted(set(self.bpy.data.objects.keys()) - before)
        return self._receipt(command, "accepted", f"Imported {len(added)} object(s) from {path.name}.", added[0] if added else "")

    def _export_gltf(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        """Write the scene (or the named objects) as .glb or .gltf under the output directory."""
        name = command.get("filepath")
        if not isinstance(name, str):
            raise sa.ActionRefused("filepath must be a string.")
        path = sa.resolve_inside(self.output_dir, name, "output", new_file=True)
        suffix = path.suffix.lower()
        if suffix not in sa.GLTF_EXTENSIONS:
            raise sa.ActionRefused(f"Export path must end in {' or '.join(sa.GLTF_EXTENSIONS)}.")
        options = {}
        for field, key in (("extras", "export_extras"), ("yUp", "export_yup"), ("applyModifiers", "export_apply")):
            value = command.get(field, True)
            if not isinstance(value, bool):
                raise sa.ActionRefused(f"{field} must be true or false.")
            options[key] = value
        names = command.get("selection")
        chosen = []
        if names is not None:
            if not isinstance(names, list) or not names or not all(isinstance(n, str) and n for n in names):
                raise sa.ActionRefused("selection must be a non-empty list of object names.")
            missing = [n for n in names if n not in self.bpy.data.objects]
            if missing:
                raise sa.ActionRefused(f"Selection object was not found: {missing[0]}")
            chosen = [self.bpy.data.objects[n] for n in dict.fromkeys(names)]
        binary = path.with_suffix(".bin")
        if suffix == ".gltf" and os.path.lexists(binary):
            raise sa.ActionRefused("output path already exists; output actions never overwrite: " + binary.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Re-check after the folders exist and just before use (residual TOCTOU as in renderStill).
        if sa.resolve_inside(self.output_dir, name, "output", new_file=True) != path:
            raise sa.ActionRefused("Output path changed while it was being checked.")
        objects = list(self.bpy.data.objects.values())
        saved = [(obj, obj.select_get()) for obj in objects]
        try:
            if chosen:
                for obj in objects:
                    obj.select_set(obj in chosen)
            result = self.bpy.ops.export_scene.gltf(
                filepath=str(path), export_format="GLB" if suffix == ".glb" else "GLTF_SEPARATE",
                use_selection=bool(chosen), **options)
        finally:
            for obj, state in saved:
                if obj.name in self.bpy.data.objects:
                    obj.select_set(state)
        if "FINISHED" not in result:
            raise sa.ActionRefused(f"glTF export did not finish: {sorted(result)}")
        if not path.is_file():
            raise sa.ActionRefused("glTF export wrote no file.")
        return self._receipt(command, "accepted", f"Exported glTF to {path} ({path.stat().st_size} bytes).", "")

    def _resolve_typed(self, command: dict[str, Any], object_type: str) -> Any:
        obj = self._resolve_object(command)
        if obj is None:
            raise sa.ActionRefused("Target Blender object was not found.")
        if obj.type != object_type:
            raise sa.ActionRefused(f"Target Blender object is not a {object_type}.")
        return obj

    def _set_camera(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_typed(command, "CAMERA")
        camera = obj.data
        # Validate everything before changing anything, so a refused intent leaves the camera alone.
        lens = sa.number(command, "lens", 1.0, sa.MAX_LENS_MM)
        camera_type = sa.choice(command, "cameraType", sa.CAMERA_TYPES)
        ortho_scale = sa.number(command, "orthoScale", 0.001, 100000.0)
        clip_start = sa.number(command, "clipStart", 0.0001, 1.0e6)
        clip_end = sa.number(command, "clipEnd", 0.001, 1.0e7)
        panorama_type = sa.choice(command, "panoramaType", self._panorama_types(camera))
        if lens is not None:
            camera.lens = lens
        if camera_type is not None:
            camera.type = camera_type
        if ortho_scale is not None:
            camera.ortho_scale = ortho_scale
        if clip_start is not None:
            camera.clip_start = clip_start
        if clip_end is not None:
            camera.clip_end = clip_end
        if panorama_type is not None:
            # Blender 4.2 moved panorama_type from camera.cycles to the camera itself.
            holder = camera if hasattr(camera, "panorama_type") else camera.cycles
            holder.panorama_type = panorama_type
        if command.get("active"):
            context.scene.camera = obj
        return self._receipt(command, "accepted", "Blender camera updated.", obj.name)

    def _panorama_types(self, camera: Any) -> tuple[str, ...]:
        holder = camera if hasattr(camera, "panorama_type") else getattr(camera, "cycles", camera)
        try:
            return tuple(item.identifier for item in holder.bl_rna.properties["panorama_type"].enum_items)
        except (KeyError, AttributeError):
            return ("EQUIRECTANGULAR", "EQUIDISTANT", "FISHEYE_EQUISOLID", "MIRRORBALL")

    def _set_light(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        obj = self._resolve_typed(command, "LIGHT")
        energy = sa.number(command, "energy", 0.0, 1.0e7)
        light_color = sa.color(command)
        light_type = sa.choice(command, "lightType", sa.LIGHT_TYPES)
        if energy is not None:
            obj.data.energy = energy
        if light_color is not None:
            obj.data.color = light_color
        if light_type is not None:
            obj.data.type = light_type
        return self._receipt(command, "accepted", "Blender light updated.", obj.name)

    def _set_world(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        world_color = sa.color(command)
        strength = sa.number(command, "strength", 0.0, 1.0e6)
        name = str(command.get("worldName") or "")
        scene = context.scene
        world = self.bpy.data.worlds.get(name) if name else scene.world
        if world is None:
            world = self.bpy.data.worlds.new(name or "Brokkr World")
        scene.world = world
        world.use_nodes = True
        background = world.node_tree.nodes.get("Background")
        if background is None:
            raise sa.ActionRefused("World has no Background node to configure.")
        if world_color is not None:
            background.inputs["Color"].default_value = (*world_color, 1.0)
        if strength is not None:
            background.inputs["Strength"].default_value = strength
        return self._receipt(command, "accepted", "Blender world updated.", world.name)

    def _render_still(self, context: Any, command: dict[str, Any]) -> dict[str, Any]:
        scene = context.scene
        render = scene.render
        name = str(command.get("outputPath") or "")
        path = sa.resolve_inside(self.output_dir, name, "output", new_file=True)
        file_format = sa.still_format(path)
        # The engine enum is dynamic (Cycles and add-on engines register at runtime), and RNA's
        # enum_items on a dynamic enum lists only its static defaults, so the running Blender is
        # asked by assignment below and a TypeError there is the refusal.
        engine = command.get("engine")
        if engine is not None and (not isinstance(engine, str) or not engine.strip()):
            raise sa.ActionRefused("engine must be a render engine identifier.")
        engine = engine.strip().upper() if engine else None
        width = sa.integer(command, "resolutionX", 1, sa.MAX_RESOLUTION)
        height = sa.integer(command, "resolutionY", 1, sa.MAX_RESOLUTION)
        camera_name = str(command.get("cameraName") or "")
        camera = None
        if camera_name:
            camera = self.bpy.data.objects.get(camera_name)
            if camera is None or camera.type != "CAMERA":
                raise sa.ActionRefused(f"Camera object was not found: {camera_name}")
        # Render settings are the intent's for this render only; put them back afterwards.
        saved = (render.engine, render.resolution_x, render.resolution_y, render.filepath,
                 render.image_settings.file_format, scene.camera)
        try:
            if engine is not None:
                try:
                    render.engine = engine
                except TypeError:
                    raise sa.ActionRefused(f"engine {engine} is not available in this Blender.") from None
            if width is not None:
                render.resolution_x = width
            if height is not None:
                render.resolution_y = height
            if camera is not None:
                scene.camera = camera
            render.filepath = str(path)
            render.image_settings.file_format = file_format
            # Folders are made only after every refusal that can still come from Blender (an unknown
            # engine), so a refused render leaves none behind. Then re-check after the folders exist
            # and immediately before use: no link was swapped in, and the name is still free. Blender
            # opens the file itself afterwards, so a swap in that last gap is not prevented (residual
            # TOCTOU): the output directory must only be writable by trusted users.
            path.parent.mkdir(parents=True, exist_ok=True)
            if sa.resolve_inside(self.output_dir, name, "output", new_file=True) != path:
                raise sa.ActionRefused("Output path changed while it was being checked.")
            self.bpy.ops.render.render(write_still=True)
        finally:
            (render.engine, render.resolution_x, render.resolution_y, render.filepath,
             render.image_settings.file_format, scene.camera) = saved
        return self._receipt(command, "accepted", f"Rendered still to {path.name}.", scene.name)

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

    def _object_snapshot(self, obj: Any, scan: Any = None) -> dict[str, Any]:
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
            "parentName": obj.parent.name if obj.parent else "",
            "collections": [collection.name for collection in obj.users_collection],
            "materials": [slot.material.name for slot in obj.material_slots if slot.material],
            "modifiers": [self._modifier_snapshot(modifier) for modifier in obj.modifiers],
            "constraints": [constraint.name for constraint in obj.constraints],
            "camera": self._camera_snapshot(data) if obj.type == "CAMERA" and data else None,
            "mesh": self._mesh_snapshot(data) if obj.type == "MESH" and data else None,
            "evaluated": self._evaluated_snapshot(obj, scan),
            "customProperties": self._custom_properties(obj.items()),
        }

    def _camera_snapshot(self, camera: Any) -> dict[str, Any]:
        return {
            "lensMillimeters": float(camera.lens),
            "fieldOfViewDegrees": math.degrees(float(camera.angle)),
            "clipStart": float(camera.clip_start),
            "clipEnd": float(camera.clip_end),
            "type": camera.type,
        }

    def _mesh_snapshot(self, mesh: Any) -> dict[str, Any]:
        return {
            "vertexCount": len(mesh.vertices),
            "edgeCount": len(mesh.edges),
            "polygonCount": len(mesh.polygons),
            "uvLayerCount": len(mesh.uv_layers),
            "shapeKeyCount": len(mesh.shape_keys.key_blocks) if mesh.shape_keys else 0,
        }

    def _instance_scan(self) -> Any:
        """One pass over the depsgraph's instances: per original parent object, the count, the first locations
        and the running bounds (world space). Nothing is kept per instance beyond the cap."""
        depsgraph = self.bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        found: dict[str, dict[str, Any]] = {}
        visited = 0
        complete = True
        for item in depsgraph.object_instances:
            visited += 1
            if visited > EVALUATED_INSTANCE_SCAN_LIMIT:
                complete = False
                break
            if not item.is_instance or item.parent is None:
                continue
            entry = found.setdefault(item.parent.original.name, {"count": 0, "first": [], "min": None, "max": None})
            point = tuple(float(c) for c in item.matrix_world.translation)
            entry["count"] += 1
            if len(entry["first"]) < EVALUATED_POSITION_CAP:
                entry["first"].append([round(c, 5) for c in point])
            entry["min"] = list(point) if entry["min"] is None else [min(a, b) for a, b in zip(entry["min"], point)]
            entry["max"] = list(point) if entry["max"] is None else [max(a, b) for a, b in zip(entry["max"], point)]
        return depsgraph, found, complete

    def _evaluated_snapshot(self, obj: Any, scan: Any) -> dict[str, Any] | None:
        """What the modifier stack produced, for mesh objects that have one. Vertex positions and their bounds
        are in the object's local space; instance locations and their bounds are world space. A Geometry Nodes
        object's own mesh is empty, so the base mesh counts say nothing about it. Above EVALUATED_VERTEX_LIMIT
        vertices only the counts are read, and any non-finite coordinate drops the positions and sets nonFinite."""
        if obj.type != "MESH" or not len(obj.modifiers) or scan is None:
            return None
        depsgraph, found, complete = scan
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            count = len(mesh.vertices)
            result = {"vertexCount": count, "edgeCount": len(mesh.edges), "polygonCount": len(mesh.polygons)}
            coords = array("f", bytes(12 * count)) if 0 < count <= EVALUATED_VERTEX_LIMIT else None
            if coords is not None:
                mesh.vertices.foreach_get("co", coords)
        finally:
            evaluated.to_mesh_clear()
        entry = found.get(obj.name)
        reached = entry is not None
        entry = entry or {"count": 0, "first": [], "min": [], "max": []}
        finite = all(math.isfinite(c) for c in coords) if coords is not None else True
        finite = finite and all(math.isfinite(c) for c in (entry["min"] or []) + (entry["max"] or []) + [c for p in entry["first"] for c in p])
        points = [coords[i:i + 3] for i in range(0, 3 * count, 3)] if coords is not None else []
        result.update({
            # An object the stopped scan never reached has an unknown count, not zero.
            "instanceCount": entry["count"] if complete or reached else None,
            "instancesComplete": complete,
            "positionsSkipped": count > EVALUATED_VERTEX_LIMIT,
            "nonFinite": not finite,
            "vertexBoundsMin": [min(p[a] for p in points) for a in range(3)] if points and finite else [],
            "vertexBoundsMax": [max(p[a] for p in points) for a in range(3)] if points and finite else [],
            "vertexLocations": [[round(c, 5) for c in p] for p in points[:EVALUATED_POSITION_CAP]] if finite else [],
            "instanceBoundsMin": entry["min"] if finite and entry["min"] else [],
            "instanceBoundsMax": entry["max"] if finite and entry["max"] else [],
            "instanceLocations": entry["first"] if finite else [],
            "truncated": count > EVALUATED_POSITION_CAP or entry["count"] > EVALUATED_POSITION_CAP,
        })
        return result

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
            "sync_session": cultcache.define_document_type(SYNC_SESSION_SCHEMA),
            "sync_object_binding": cultcache.define_document_type(SYNC_OBJECT_BINDING_SCHEMA),
            "sync_var": cultcache.define_document_type(SYNC_VAR_SCHEMA),
            "sync_timeline_binding": cultcache.define_document_type(SYNC_TIMELINE_BINDING_SCHEMA),
            "sync_receipt": cultcache.define_document_type(SYNC_RECEIPT_SCHEMA),
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

    def _put_sync_var(
        self,
        node: Any,
        documents: dict[str, Any],
        session_id: str,
        binding_id: str,
        kind: str,
        display_name: str,
        unity_property_path: str,
        blender_property_path: str,
        authority: str,
        enabled: bool,
        interpolation: str,
        updated_at: str,
    ) -> None:
        sync_var_id = _stable_id("var", session_id, binding_id, kind)
        node.database.put(documents["sync_var"], f"sync/vars/{sync_var_id}", {
            "schema": SYNC_VAR_SCHEMA,
            "syncVarId": sync_var_id,
            "sessionId": session_id,
            "bindingId": binding_id,
            "displayName": display_name,
            "kind": kind,
            "unityPropertyPath": unity_property_path,
            "blenderPropertyPath": blender_property_path,
            "authority": authority,
            "enabled": bool(enabled),
            "interpolation": interpolation,
            "updatedAt": updated_at,
        })


def _load_cultmesh(cultlib_py_src: str) -> tuple[Any, Any]:
    packages = Path(cultlib_py_src or DEFAULT_CULTLIB_PY_SRC)
    for name in CULTLIB_PY_PACKAGES:
        source = packages / name / "src"
        if source.exists():
            source_text = str(source)
            if source_text not in sys.path:
                sys.path.insert(0, source_text)
    try:
        import cultmesh_py  # type: ignore
        import cultcache_py  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Brokkr Blender target requires CultLib's Python packages. Set CultLib Python Source "
            "to the CultLib packages directory or install cultcache-py, cultnet-py and cultmesh-py into Blender's Python."
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


def _sync_session(session_id: str, display_name: str, updated_at: str) -> dict[str, Any]:
    return {
        "schema": SYNC_SESSION_SCHEMA,
        "sessionId": session_id,
        "displayName": display_name or "Brokkr Editor Sync",
        "owner": "brokkr.creative_tool_broker",
        "unityProviderId": "brokkr.unity_editor",
        "blenderProviderId": PROVIDER_ID,
        "mode": "manual",
        "enabled": True,
        "createdAt": updated_at,
        "updatedAt": updated_at,
    }


def _unity_custom_property_path(component_type: str, property_path: str) -> str:
    property_path = (property_path or "value").strip()
    component_type = (component_type or "").strip()
    if not component_type:
        return property_path
    return f"{component_type}::{property_path}"


def _blender_custom_property_path(property_path: str) -> str:
    property_path = (property_path or "value").strip()
    if property_path.startswith("customProperties."):
        return property_path
    return f"customProperties.{property_path}"


def _stable_id(*parts: str) -> str:
    return ":".join(str(part or "").replace(" ", "_").replace("/", "_").replace("\\", "_") for part in parts)


def _active_action_name(context: Any) -> str:
    obj = context.active_object
    if obj is not None and obj.animation_data and obj.animation_data.action:
        return obj.animation_data.action.name
    return ""
