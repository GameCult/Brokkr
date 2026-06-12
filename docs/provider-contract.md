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
- `GET /unity/scene`
- `GET /unity/assets`
- `POST /commands/unity`
- `GET /hosts/unity/commands/next`
- `POST /hosts/unity/commands/receipt`
- `GET /unity/receipts`
- `GET /eve/unity/gui`
- `GET /eve/unity/tui`

The HTTP lane is a local adapter transport. It is not the canonical public
Verse contract.

## Unity Command Actions

All Unity writes use `gamecult.brokkr.unity_command.v0` and receive
`gamecult.brokkr.unity_command_receipt.v0`.

- `createGameObject`
- `attachComponent`
- `setComponentProperty`
- `instantiatePrefab`
- `createPrefabVariant`

Unity owns the mutation. Brokkr queues the command and records the receipt after
Unity executes it.

## Eve/CultUI Lowerings

`/eve/unity/gui` and `/eve/unity/tui` expose the Unity editor surface as
`gamecult.eve.surface.v1` projections. GUI and TUI clients should render these
documents as views over the same Brokkr state:

- scene graph
- component state
- asset library
- command affordances
- command receipts

These documents are not dashboard-owned truth. They are lowerable interface
state over Unity observations and Brokkr command receipts.
