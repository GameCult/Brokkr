# Brokkr Unity Adapter

This package lets the Unity Editor publish its scene, component, asset, command,
receipt, Quest, and Eve/CultUI state as typed CultCache documents synced through
CultMesh.

## Install By Local Path

Add this package to a Unity project's `Packages/manifest.json`:

```json
"com.gamecult.brokkr": "file:F:/Projects/Brokkr/surfaces/unity/Packages/com.gamecult.brokkr"
```

The package ships no assemblies. Its CultCache, CultNet and CultMesh runtime
comes from `org.gamecult.cultlib`, which the host manifest must also resolve:

```json
"org.gamecult.cultlib": "https://github.com/GameCult/CultLib.git?path=/unity/org.gamecult.cultlib#cultlib-unity-v1.0.60"
```

Then open `GameCult > Brokkr`.

## Local Smoke

In Unity:

1. Open `GameCult > Brokkr`.
2. Confirm `Broker URI` is `cultmesh://brokkr`.
3. Confirm `CultMesh Cache` points at `.brokkr/unity-editor.ccmp`.
4. Click `Start CultMesh Mirror`.
5. Click `Capture Snapshot`.
6. Click `Publish Mirror`.
7. To create a ScriptableObject through the mirror (tick `Agent Commands` first, and add `createScriptableObject` to `Allowed Actions`), fill `ScriptableObject Type`,
   `Asset Name`, and `Asset Path`, then click `Create ScriptableObject Asset`.
8. To instantiate or variant a prefab through the mirror, fill `Prefab Asset
   Path`, optional `Instance Name`, and optional `Variant Path`, then click the
   matching prefab command.
9. To publish object sync policy, select a GameObject, set the object lane
   toggles including transform, parent, active state, material, and property
   lanes, then click `Publish Object Sync`.
10. With the mirror running, run `brokkr-daemon sync-once` or `sync-loop`; the window
   shows the latest daemon
   sync pass receipt.
11. To publish an ad hoc sync variable, fill `Ad Hoc Sync Var` with a binding id
    or leave it blank for a generated id, set kind/paths/authority/interpolation,
    then click `Publish Sync Var`.

The Unity adapter writes the latest editor snapshot to:

```text
unity/host/current
```

Brokkr daemon sync receipts are read from:

```text
sync/receipts/{receiptId}
```

Ad hoc sync variables are written to:

```text
sync/vars/{syncVarId}
```

Verse-side command clients write `brokkr.unity.command_intent.v0` documents to:

```text
unity/commands/{commandId}
```

The editor service pulls the store about once a second while `Agent Commands` is on, admits each intent through the project policy, mutates the editor, and publishes receipts
to:

```text
unity/receipts/{commandId}
```

Recognized Unity asset commands include:

- `instantiatePrefab`
- `createPrefabVariant`
- `createScriptableObject`

The Unity plugin is still an adapter. Unity owns Unity editor truth; Brokkr owns
provider discovery; CultCache and CultMesh own the live mirror lane.

## Agent Commands

The editor executes intents that other processes write into `.brokkr/` only
while `Agent Commands` is ticked in the Brokkr window. It is off for every
project until you tick it, and the host snapshot reports the flag. Nothing
listens on the network: callers reach the editor through the directory store
at `.brokkr/unity-editor.ccmp`.

`Allowed Actions` lists what an agent may run. The default allows scene
mutation and editor lifecycle; `createScriptableObject`, `createPrefabVariant`
and `saveScene` are off until you add them. A refused intent gets a receipt
with `status: denied`. Captures land under `.brokkr/captures/`.

From a shell, with the project's cache path:

```powershell
dotnet run --project F:/Projects/Brokkr/brokkr-command/Brokkr.Command.csproj -- --unity-cache <project>/.brokkr/unity-editor.ccmp --action readHost
dotnet run --project F:/Projects/Brokkr/brokkr-command/Brokkr.Command.csproj -- --unity-cache <project>/.brokkr/unity-editor.ccmp --action createGameObject --name Marker
```

Turning `Agent Commands` on expires every intent already in `.brokkr/`: each
gets a receipt with `status: expired` and none runs, so enabling the sink
cannot execute anything you did not see. The expiry is one commit that only
lands if the store is exactly what the editor just read; an intent that arrives
mid-enable makes it read again, and if writers never let the store settle
(eight tries) the enable fails with a message and the sink stays off. Intents
that arrive after the tick are fresh, whatever clock wrote them. With about
2000 waiting intents the tick takes several seconds (the store writes one
receipt each); after that the editor handles at most 16 intents per update
tick.

The tick also writes an enable marker into `.brokkr/unity-editor.ccmp`, and the
editor keeps the matching token in its own preferences. The sink runs only
while the store carries that marker. If you re-clone the project, or copy a
`.brokkr/` folder in, the marker is missing or foreign, so the editor turns the
sink off and logs why; tick `Agent Commands` again to run intents from that
store. The token is not authentication and does not identify who wrote an
intent: anyone who can write `.brokkr/` can write intents, and `Allowed
Actions` is what limits them. Restoring a backup, checking out `.brokkr/` from
git, or a sync-conflict copy of the editor's own store carries a valid marker
and can bring back intents that were already answered, which then run again.

Before the editor runs an intent it writes a receipt with `status: attempted`.
If the editor stops, or cannot record the result, that intent is reported as
`interrupted` and is not run again automatically. Check the project first:
`interrupted` does not say whether the action happened, and some actions are
not idempotent. Re-sending `createGameObject` after an `interrupted` receipt
can create the object twice; a domain reload during `refreshAssets` can also
end as `interrupted` although the refresh completed. If the editor could not
write the `attempted` receipt, the intent normally never started and is retried
on the next tick; if the store fails in a way that leaves the marker behind,
it is reported as `interrupted` instead.

Receipts are kept for the newest 1000 answered intents, and no receipt is
deleted before it is ten minutes old, whatever the count (`brokkr-command`
refuses a `--wait-ms` over five minutes, so the receipt a caller waits on is
always still there). Older intents beyond the count are deleted together with
their receipts, at most 128 per tick. A `--command-id` is refused only while
its receipt exists, so an id can be reused after its receipt has been pruned.
`brokkr-command` exits 0 when the receipt is `accepted`, 1 for any other
receipt status (`failed`, `denied`, `expired`, `interrupted`), and 2 for bad
usage, a timeout, a store that cannot be opened, or any other failure. A
`--command-id` that already has a receipt is refused with exit 2; the check and
the write are two steps, so two callers naming the same new id in the same
instant can still collide.
