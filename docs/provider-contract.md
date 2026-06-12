# Brokkr Provider Contract

Provider id: `brokkr.creative_tool_broker`

CultMesh base URI: `cultmesh://brokkr`

Primary Eve surface id: `brokkr.eve.tool_broker.v0`

## Tool Kinds

- `unity-editor`
- `blender-editor`

## Capability Families

- `host.status.read`
- `scene.tree.read`
- `selection.read`
- `asset.catalog.read`
- `command.palette.read`
- `command.execute`
- `receipt.read`

The scaffold advertises command execution as policy-gated. No host command
should execute unless the host plugin recognizes the command family and Brokkr
has issued a command request with a receipt id.

