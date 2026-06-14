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
    DEFAULT_CULTCACHE_PATH,
    DEFAULT_CULTCACHE_PY_SRC,
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

    cultcache_path: bpy.props.StringProperty(
        name="CultCache Store",
        subtype="FILE_PATH",
        default=DEFAULT_CULTCACHE_PATH,
        description="CultCache store used for Blender mirror documents",
    )

    cultcache_py_src: bpy.props.StringProperty(
        name="CultCache Python Source",
        subtype="DIR_PATH",
        default=DEFAULT_CULTCACHE_PY_SRC,
        description="Path to cultcache-py/src when cultcache-py is not installed in Blender",
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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "broker_uri")
        layout.prop(self, "cultcache_path")
        layout.prop(self, "cultcache_py_src")
        layout.prop(self, "debug_mirror_root")
        layout.prop(self, "auto_capture")


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
        layout.label(text=f"Store: {adapter.resolve_cache_path(prefs.cultcache_path)}")

        row = layout.row(align=True)
        row.operator("brokkr.capture_snapshot", icon="FILE_REFRESH")
        row.operator("brokkr.drain_commands", icon="PLAY")

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
            prefs.cultcache_path,
            prefs.cultcache_py_src,
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
            prefs.cultcache_path,
            prefs.cultcache_py_src,
            prefs.debug_mirror_root,
        )
        self.report({"INFO"}, f"Brokkr processed {len(receipts)} Blender command(s)")
        return {"FINISHED"}


def _auto_capture(scene, depsgraph):
    context = bpy.context
    prefs = context.preferences.addons.get(__name__)
    if not prefs or not prefs.preferences.auto_capture:
        return
    target().publish_snapshot(
        context,
        prefs.preferences.cultcache_path,
        prefs.preferences.cultcache_py_src,
        prefs.preferences.debug_mirror_root,
    )


classes = (
    BrokkrPreferences,
    BROKKR_PT_status,
    BROKKR_OT_capture_snapshot,
    BROKKR_OT_drain_commands,
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
    _target = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
