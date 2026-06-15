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
- `brokkr.blender.host_snapshot.v0` at `blender/host/current`
- `brokkr.blender.command_intent.v0` at `blender/commands/{commandId}`
- `brokkr.blender.command_receipt.v0` at `blender/receipts/{commandId}`
- `brokkr.sync.session.v0` at `sync/sessions/{sessionId}`
- `brokkr.sync.object_binding.v0` at `sync/bindings/objects/{bindingId}`
- `brokkr.sync.var.v0` at `sync/vars/{syncVarId}`
- `brokkr.sync.timeline_binding.v0` at `sync/bindings/timelines/{bindingId}`
- `brokkr.sync.receipt.v0` at `sync/receipts/{receiptId}`

## Sync Organ

Brokkr owns sync correspondence and policy documents. Editor hosts still own
scene mutation. A sync record can request or describe a lane, but it is not real
editor state until Unity or Blender publishes accepted command receipts and a
fresh host snapshot.

Primary sync documents:

- `brokkr.sync.session.v0`: shared sync session and mode.
- `brokkr.sync.object_binding.v0`: Unity GameObject to Blender object/collection
  correspondence.
- `brokkr.sync.var.v0`: per-lane sync options such as transform, material,
  component property, custom property, timeline frame, camera lens, or
  Cinemachine virtual camera.
- `brokkr.sync.timeline_binding.v0`: Blender scene/action timeline to Unity
  Timeline/Cinemachine correspondence.
- `brokkr.sync.receipt.v0`: daemon sync pass receipts.

Operational commands:

- `brokkr-daemon sync-once --unity-cache .brokkr/unity-editor.ccmp --blender-cache .brokkr/blender-editor.ccmp`
- `brokkr-daemon sync-loop --unity-cache .brokkr/unity-editor.ccmp --blender-cache .brokkr/blender-editor.ccmp --interval-ms 500`

`sync-loop` owns scheduling only. It repeatedly invokes the same sync decision
primitive as `sync-once`, writes command intents and sync receipts through the
mirrors, and prints per-pass telemetry to stdout.

Implemented sync lanes:

- Unity GameObject transform to Blender object transform.
- Unity GameObject active state to Blender object visibility.
- Blender object transform to Unity GameObject transform.
- Blender scene frame to Unity timeline time through `setComponentProperty`.
- Blender scene camera transform/FOV to a Unity Cinemachine virtual camera
  GameObject/component. The FOV write uses `componentType =
  Cinemachine.CinemachineVirtualCamera` and property path `m_Lens.FieldOfView`.
- Blender object custom property to Unity serialized property through
  `setComponentProperty`. The syncvar uses `blenderPropertyPath =
  customProperties.name` and `unityPropertyPath = Component.Type::propertyPath`
  when a Unity component should receive the value.

## Unity Command Actions

All Unity writes use `brokkr.unity.command_intent.v0` and receive
`brokkr.unity.command_receipt.v0`.

- `createGameObject`
- `attachComponent`
- `setGameObjectTransform`
- `setComponentProperty`
- `instantiatePrefab`
- `createPrefabVariant`

Unity owns the mutation. Brokkr advertises the command surface; Verse clients
write typed command intents; Unity executes recognized intents and publishes
receipts. `setComponentProperty` writes the target object by default; when
`componentType` is present, Unity resolves that component on the target
GameObject and writes the serialized property there.

## Blender Command Actions

All Blender writes use `brokkr.blender.command_intent.v0` and receive
`brokkr.blender.command_receipt.v0`.

- `createObject`
- `deleteObject`
- `setObjectTransform`
- `setObjectVisibility`
- `selectObject`
- `assignMaterial`

Blender owns the mutation. Brokkr advertises the command surface; Verse clients
write typed command intents; Blender executes recognized intents and publishes
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
