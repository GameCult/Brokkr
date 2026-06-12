# Blender Add-on Scaffold

Install `surfaces/blender/brokkr_bridge` as a Blender add-on directory during
local development.

The scaffold adds a Brokkr panel to the 3D View sidebar. It does not open a live
transport yet. Its first job is to preserve the adapter boundary: Blender emits
host snapshots and executes admitted Brokkr commands; Brokkr owns Verse-facing
broker state and receipts.

