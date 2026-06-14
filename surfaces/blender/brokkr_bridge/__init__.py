bl_info = {
    "name": "Brokkr",
    "author": "GameCult",
    "version": (0, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Brokkr",
    "description": "Blender adapter for the Brokkr CultMesh creative-tool broker.",
    "category": "System",
}

import bpy

from .blender_target import (
    DEFAULT_BROKER_URI,
    DEFAULT_CULTLIB_PY_SRC,
    DEFAULT_CULTMESH_CACHE_PATH,
    DEFAULT_DEBUG_MIRROR_ROOT,
    PROVIDER_ID,
    TOOL_KIND,
    BrokkrBlenderTarget,
)

_target = None


def target():
    global _target
    if _target is None:
        _target = BrokkrBlenderTarget(bpy)
    return _target


class BrokkrPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    broker_uri: bpy.props.StringProperty(
        name="Broker URI",
        default=DEFAULT_BROKER_URI,
        description="CultMesh broker URI for Brokkr",
    )

    cultmesh_cache_path: bpy.props.StringProperty(
        name="CultMesh Cache",
        subtype="FILE_PATH",
        default=DEFAULT_CULTMESH_CACHE_PATH,
        description="CultMesh node cache used for Blender mirror documents",
    )

    cultlib_py_src: bpy.props.StringProperty(
        name="CultLib Python Source",
        subtype="DIR_PATH",
        default=DEFAULT_CULTLIB_PY_SRC,
        description="Path to CultLib packages/cultcache-py/src when cultcache-py is not installed in Blender",
    )

    debug_mirror_root: bpy.props.StringProperty(
        name="Debug Export Root",
        subtype="DIR_PATH",
        default=DEFAULT_DEBUG_MIRROR_ROOT,
        description="Optional JSON debug export/import root; CultCache remains the mirror owner",
    )

    auto_capture: bpy.props.BoolProperty(
        name="Auto Capture",
        default=False,
        description="Capture and publish a Blender host snapshot on dependency graph updates",
    )

    serve_host: bpy.props.StringProperty(
        name="Serve Host",
        default="127.0.0.1",
        description="Host interface for the Blender CultMesh server",
    )

    serve_port: bpy.props.IntProperty(
        name="Serve Port",
        default=0,
        min=0,
        max=65535,
        description="Port for the Blender CultMesh server; 0 asks the OS for a free port",
    )

    max_snapshot_documents: bpy.props.IntProperty(
        name="Max Snapshot Documents",
        default=1000,
        min=1,
        description="Maximum documents returned by a served snapshot response",
    )

    max_snapshot_bytes: bpy.props.IntProperty(
        name="Max Snapshot Bytes",
        default=4194304,
        min=1024,
        description="Maximum encoded snapshot response size",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "broker_uri")
        layout.prop(self, "cultmesh_cache_path")
        layout.prop(self, "cultlib_py_src")
        layout.prop(self, "debug_mirror_root")
        layout.prop(self, "auto_capture")
        layout.prop(self, "serve_host")
        layout.prop(self, "serve_port")
        layout.prop(self, "max_snapshot_documents")
        layout.prop(self, "max_snapshot_bytes")


class BROKKR_PT_status(bpy.types.Panel):
    bl_label = "Brokkr"
    bl_idname = "BROKKR_PT_status"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Brokkr"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__name__].preferences
        adapter = target()

        layout.label(text=f"Provider: {PROVIDER_ID}")
        layout.label(text=f"Tool: {TOOL_KIND}")
        layout.label(text=f"Broker: {prefs.broker_uri}")
        layout.label(text=f"Node: {adapter.resolve_cache_path(prefs.cultmesh_cache_path)}")
        server = adapter.server_status()
        layout.label(text=f"Server: {server['endpoint'] if server['running'] else 'stopped'}")

        row = layout.row(align=True)
        row.operator("brokkr.capture_snapshot", icon="FILE_REFRESH")
        row.operator("brokkr.drain_commands", icon="PLAY")

        server_row = layout.row(align=True)
        server_row.operator("brokkr.start_server", icon="NETWORK_DRIVE")
        server_row.operator("brokkr.stop_server", icon="CANCEL")

        if adapter.last_snapshot:
            layout.separator()
            layout.label(text=f"Objects: {adapter.last_snapshot.get('objectCount', 0)}")
            layout.label(text=f"Materials: {adapter.last_snapshot.get('materialCount', 0)}")
            layout.label(text=f"Selected: {len(adapter.last_snapshot.get('selectedObjectNames', []))}")

        if adapter.last_receipt:
            layout.separator()
            layout.label(text=f"Last receipt: {adapter.last_receipt.get('status', '')}")
            layout.label(text=adapter.last_receipt.get("message", ""))


class BROKKR_OT_capture_snapshot(bpy.types.Operator):
    bl_idname = "brokkr.capture_snapshot"
    bl_label = "Capture Snapshot"
    bl_description = "Capture and publish the current Blender host snapshot"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        snapshot = target().publish_snapshot(
            context,
            prefs.cultmesh_cache_path,
            prefs.cultlib_py_src,
            prefs.debug_mirror_root,
        )
        self.report({"INFO"}, f"Brokkr mirrored Blender snapshot: {snapshot['observedAt']}")
        return {"FINISHED"}


class BROKKR_OT_drain_commands(bpy.types.Operator):
    bl_idname = "brokkr.drain_commands"
    bl_label = "Drain Commands"
    bl_description = "Execute pending Brokkr Blender command intents and publish receipts"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        receipts = target().drain_commands(
            context,
            prefs.cultmesh_cache_path,
            prefs.cultlib_py_src,
            prefs.debug_mirror_root,
        )
        self.report({"INFO"}, f"Brokkr processed {len(receipts)} Blender command(s)")
        return {"FINISHED"}


class BROKKR_OT_start_server(bpy.types.Operator):
    bl_idname = "brokkr.start_server"
    bl_label = "Start Server"
    bl_description = "Serve the Blender CultMesh node over the local CultNet/CultMesh endpoint"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        status = target().start_server(
            prefs.cultmesh_cache_path,
            prefs.cultlib_py_src,
            prefs.serve_host,
            prefs.serve_port,
            prefs.max_snapshot_documents,
            prefs.max_snapshot_bytes,
        )
        self.report({"INFO"}, f"Brokkr Blender server: {status['endpoint']}")
        return {"FINISHED"}


class BROKKR_OT_stop_server(bpy.types.Operator):
    bl_idname = "brokkr.stop_server"
    bl_label = "Stop Server"
    bl_description = "Stop the Blender CultMesh server"

    def execute(self, context):
        target().stop_server()
        self.report({"INFO"}, "Brokkr Blender server stopped.")
        return {"FINISHED"}


def _auto_capture(scene, depsgraph):
    context = bpy.context
    prefs = context.preferences.addons.get(__name__)
    if not prefs or not prefs.preferences.auto_capture:
        return
    target().publish_snapshot(
        context,
        prefs.preferences.cultmesh_cache_path,
        prefs.preferences.cultlib_py_src,
        prefs.preferences.debug_mirror_root,
    )


classes = (
    BrokkrPreferences,
    BROKKR_PT_status,
    BROKKR_OT_capture_snapshot,
    BROKKR_OT_drain_commands,
    BROKKR_OT_start_server,
    BROKKR_OT_stop_server,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    if _auto_capture not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_auto_capture)


def unregister():
    if _auto_capture in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_auto_capture)
    global _target
    if _target is not None:
        _target.stop_server()
    _target = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
