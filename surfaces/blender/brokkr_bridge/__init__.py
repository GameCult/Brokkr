bl_info = {
    "name": "Brokkr",
    "author": "GameCult",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Brokkr",
    "description": "Blender adapter for the Brokkr CultMesh creative-tool broker.",
    "category": "System",
}

import bpy

PROVIDER_ID = "brokkr.blender_editor"
TOOL_KIND = "blender-editor"
DEFAULT_BROKER_URI = "cultmesh://brokkr"


class BrokkrPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    broker_uri: bpy.props.StringProperty(
        name="Broker URI",
        default=DEFAULT_BROKER_URI,
        description="CultMesh broker URI for Brokkr",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "broker_uri")


class BROKKR_PT_status(bpy.types.Panel):
    bl_label = "Brokkr"
    bl_idname = "BROKKR_PT_status"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Brokkr"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__name__].preferences
        layout.label(text=f"Provider: {PROVIDER_ID}")
        layout.label(text=f"Tool Kind: {TOOL_KIND}")
        layout.label(text=f"Broker: {prefs.broker_uri}")
        layout.operator("brokkr.capture_snapshot")


class BROKKR_OT_capture_snapshot(bpy.types.Operator):
    bl_idname = "brokkr.capture_snapshot"
    bl_label = "Capture Host Snapshot"
    bl_description = "Scaffold command: report the current Blender host snapshot to the console"

    def execute(self, context):
        snapshot = {
            "schema": "gamecult.brokkr.tool_host_snapshot.v0",
            "providerId": PROVIDER_ID,
            "toolKind": TOOL_KIND,
            "projectPath": bpy.data.filepath,
            "scene": context.scene.name if context.scene else "",
        }
        print(f"Brokkr snapshot scaffold: {snapshot}")
        return {"FINISHED"}


classes = (
    BrokkrPreferences,
    BROKKR_PT_status,
    BROKKR_OT_capture_snapshot,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

