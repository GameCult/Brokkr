# Brokkr Provider Contract

Provider id: `brokkr.creative_tool_broker`

CultMesh base URI: `cultmesh://brokkr`

Local adapter HTTP endpoint: `http://127.0.0.1:8798`

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

## Local Adapter Endpoints

- `GET /health`
- `GET /provider`
- `GET /hosts`
- `POST /hosts/unity/snapshot`

The HTTP lane is a local adapter transport. It is not the canonical public
Verse contract.
