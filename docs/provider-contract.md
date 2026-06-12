# Brokkr Provider Contract

Provider id: `brokkr.creative_tool_broker`

CultMesh base URI: `cultmesh://brokkr`

Primary Eve surface id: `brokkr.eve.tool_broker.v0`

## Tool Kinds

- `unity-editor`
- `blender-editor`

## Capability Families

- `cultcache.mirror.publish`
- `cultcache.intent.watch`
- `host.status.read`
- `scene.tree.read`
- `component.state.read`
- `selection.read`
- `asset.catalog.read`
- `asset.prefab.instantiate`
- `asset.prefab.variant.create`
- `gameobject.create`
- `component.attach`
- `component.property.write`
- `command.receipt.publish`
- `eve.gui.publish`
- `eve.tui.publish`

## Mirror Documents

- `brokkr.unity.host_snapshot.v0` at `unity/host/current`
- `brokkr.unity.command_intent.v0` at `unity/commands/{commandId}`
- `brokkr.unity.command_receipt.v0` at `unity/receipts/{commandId}`
- `brokkr.unity.snapshot_receipt.v0` at `unity/receipts/snapshots/{observedAt}`
- `brokkr.unity.quest_route.v0` at `unity/quest-routes/{routeId}`
- `brokkr.unity.warped_video_frame.v0` at `unity/quest/video/{frameId}`

## Unity Command Actions

All Unity writes use `brokkr.unity.command_intent.v0` and receive
`brokkr.unity.command_receipt.v0`.

- `createGameObject`
- `attachComponent`
- `setComponentProperty`
- `instantiatePrefab`
- `createPrefabVariant`

Unity owns the mutation. Brokkr advertises the command surface; Verse clients
write typed command intents; Unity executes recognized intents and publishes
receipts.

## Eve/CultUI Lowerings

Unity publishes lowerable Eve/CultUI documents through CultMesh. GUI and TUI
clients render those documents as views over the same mirrored state:

- scene graph
- component state
- asset library
- command affordances
- command receipts

These documents are interface state over Unity observations and receipts. They
do not own editor truth.
