# Brokkr Agent Access: Cut Map

Status: cut map, nothing landed. Ends: an agent process on this box sends a typed
`brokkr.unity.command_intent.v0` to a live Unity editor, the editor executes it,
and the agent reads back `brokkr.unity.command_receipt.v0` plus a refreshed
`brokkr.unity.host_snapshot.v0`. Immediate consumer: rigging scenes in
`F:\Projects\Aetheria` (Unity 6000.3.24f1, built-in pipeline).

This is the thin slice under the named CultMesh MCP bridge campaign
(`F:\Projects\CultLib\src\GameCult.Mesh\docs\mcp-bridge-campaign.md`). It is built
so the bridge subsumes it: the seam is a typed operation invoke + receipt read
over an already-hosted CultNet endpoint, which is exactly what the campaign's
"operation binding descriptor" lowers. Nothing here becomes a second description
of what Brokkr offers.

Written by Imagination, 2026-09-18, against Brokkr `94b9334`, CultLib `fa327a0`.

## What probing established

Names in the repo do not match the machine. These are the measured facts.

**The daemon builds and is green, and is not a daemon.**
`cargo build --workspace` and `cargo test --workspace` pass (20 tests, 0.27s),
`cargo fmt --check` clean, against `cultcache-rs` pinned at CultLib
`c2a9a6e5` (`brokkr-daemon/Cargo.toml:10`), which resolves and compiles.
`brokkr-daemon/src/main.rs:127-141` dispatches exactly four subcommands:
`provider|smoke`, `sync-contract`, `sync-once`, `sync-loop`. There is no `serve`.
`README.md:57` tells you to run `cargo run -p brokkr-daemon -- serve` under the
heading "Unity Smoke"; that command exits 2. The process needs no config, no
port, no CultMesh node, no credentials and no Odin, because it opens nothing but
two files. `sync-loop` is a polling scheduler over two `.ccmp` paths, not a
service. `tools/check.ps1:112` and `tools/vendor-cultmesh-unity.ps1:4` both point
at `E:\Projects\...`, a drive this box does not have.

**The daemon's write path is the file, not the mesh.**
`MirrorStore::open` (`brokkr-daemon/src/main.rs:1400-1404`) wraps
`SingleFileMessagePackBackingStore` on the Unity `.ccmp` directly and pushes
envelopes into it (`:1421-1443`). In `cultcache-rs`
(`F:\Projects\CultLib\packages\cultcache-rs\src\lib.rs:652-700`) that store is
whole-file read-modify-write under a sibling `.lock` held with `fs2`. So
cross-process writes to the file are safe at the file level.

**But a file write does not wake the editor.** The Unity mirror subscribes to
`node.Database.Watch<BrokkrUnityCommand>()`
(`surfaces/unity/Packages/com.gamecult.brokkr/Editor/BrokkrCultMeshMirror.cs:44-52`),
which observes in-process database mutations. Nothing in the package re-pulls the
backing store, and Unity's next `FlushAsync(soft: true)` (`:68`, `:78`, `:89`)
rewrites the whole file from memory. An external file poke is therefore both
invisible and liable to be clobbered. **This is the single most load-bearing
finding: the `.ccmp`-poke option is not viable for live command delivery.**

**The live path already exists and is a network one.**
`CultMesh.StartNodeAsync` forces `StartServer = true`
(`F:\Projects\CultLib\src\GameCult.Mesh\CultMesh.cs:596-602`) and
`CultNetLocal.CreateHostAsync` starts the host (`GameCult.Networking\CultNetLocal.cs:146-163`),
so the Unity editor is already hosting a CultNet server. A remote
`CultNetDocumentPutRawMessage` is applied into the hosted database by
`CultNetDatabaseServer.HandlePutAsync`
(`GameCult.Networking\CultNetDatabaseServer.cs:236`), which is exactly the
mutation the editor's `Watch` observes. The typed client side of that message
exists in C# (`CultNetDocumentRegistry.CreateRawDocumentPutMessage`
at `GameCult.Networking\CultNetDocumentRegistry.cs:212`;
`CultNetDatabaseSubscriptionClient.cs:237`). `cultnet-rs` has RUDP, framing,
schema discovery and snapshot query, but no evidenced typed document-put client —
treat a Rust caller as unproven work, not a swap.

**The port is a constant.** `GameCult.Networking\Server.cs:26`:
`private const int ServerPort = 3075;`. Not in `CultNetHostOptions`
(`CultNetLocal.cs:13-44`), not in `CultMeshNodeOptions` (`CultMesh.cs:20-50`).
One Unity editor per machine can host a Brokkr mirror. Security is
`ServerSecurityOptions.Development()` by default (`CultNetLocal.cs:149`).

**Command delivery depends on an open window and an off-by-default toggle.**
The mirror is owned by `BrokkrWindow`, an `EditorWindow`. `OnEnable` hooks
`EditorApplication.update` (`BrokkrWindow.cs:102`); `OnDisable` unhooks it *and
disposes the mirror* (`:110-114`). The drain is `OnEditorUpdate`
(`:775-788`), gated on `autoPollCommands`, which defaults to `false`
(`BrokkrSettings.cs:23-27`), throttled to one command per second, and it
dequeues exactly one command per tick (`:382-393`). So today: no window open, no
commands; window open but toggle off, no commands; window closed mid-run, mirror
gone. `EditorApplication.update` also does not tick dependably while the editor
is unfocused, which is the normal state when an agent is driving it.

**There is no scene save.** Every scene-mutating action ends at
`EditorSceneManager.MarkSceneDirty` (`BrokkrUnityCommandExecutor.cs:45, 64, 92,
96, 141, 160, 175, 195, 263`). Only the asset commands call
`AssetDatabase.SaveAssets` (`:219, 240, 367`). An agent's whole rig lives in the
editor's memory until a human presses Ctrl+S.

**Addressing is sound.** Object ids are
`GlobalObjectId.GetGlobalObjectIdSlow(target).ToString()`
(`BrokkrUnitySnapshotBuilder.cs:183-186`), carried in the host snapshot and
resolved back on execute. Read snapshot, get ids, issue commands: that loop is
already coherent.

**The Unity package cannot go into Aetheria as-is.** It vendors
`GameCult.Caching.dll`, `GameCult.Caching.MessagePack.dll`, `GameCult.Mesh.dll`,
`GameCult.Networking.dll`, `GameCult.Logging.dll`, `MessagePack.dll`, `R3.dll`
and 20 more into `Plugins/CultMesh/`. Aetheria already resolves
`org.gamecult.cultlib` at `cultlib-unity-v1.0.60`
(`F:\Projects\Aetheria\Packages\manifest.json:57`), whose
`Runtime/Plugins/` ships the identical assembly names behind a
`GameCult.CultLib` asmdef with `overrideReferences: true`. Duplicate assembly
names are a Unity compile failure, not a warning. The vendored copies are also
stale: `GameCult.Mesh.dll` is 75,776 bytes in Brokkr against 675,840 bytes in
cultlib 1.0.60. `package.json` declares no dependencies at all and pins
`"unity": "2022.3"`.

**There is no admission. None.** No allowlist, no policy, no caller identity, no
signature, no dry-run, anywhere in `BrokkrUnityCommandExecutor.cs` or
`BrokkrCultMeshMirror.cs`. Anything that can reach the endpoint gets
`createScriptableObject`, `createPrefabVariant` and arbitrary serialized property
writes on a live project. The receipt (`BrokkrHostSnapshot.cs:215-226`) carries
`commandId`, `status`, `message`, `objectId`, `observedAt` — the executor's own
account of what it did. It is evidence, not proof: no requester identity, no
before/after, nothing signed.

## Ordered cuts

### Cut 1. Cut the stale claims

- **Repo/branch:** Brokkr, `agent-access` from `94b9334`. No dependencies.
- **First:** none.
- **Deletes first:** `README.md:49-64` (the `serve` invocation and the
  `file:E:/Projects/...` manifest line). `tools/check.ps1:112-118` (the
  `E:\Projects\CultLib-main-work` Blender probe branch — it is dead on this box
  and silently skipped, which is worse than absent).
- **Keeps and moves:** nothing.
- **Adds:** a README line naming the four real subcommands and saying plainly
  that `brokkr-daemon` is a CLI over `.ccmp` files, not a listening service.
- **Per-file changes:**
  - `README.md:49-64`: replace the Unity Smoke section with the real install
    path from Cut 2 and the real agent path from Cut 5.
  - `tools/vendor-cultmesh-unity.ps1:4`: `$cultLibRoot` from `E:\Projects\CultLib`
    to a `-CultLibRoot` parameter defaulting to `F:\Projects\CultLib`.
  - `tools/check.ps1:112`: same, parameterized; fail loudly when absent instead
    of skipping.
- **Authority map:** Owner: README and `tools/` describe the daemon's real CLI
  surface. Inputs: `main.rs:127-141`. Outputs: operator-followable commands.
  Derived state: none. Forbidden writers: docs may not invent subcommands.
  Shared paths: n/a. Deletion line: every `E:\` literal in the repo.
- **Verification:**
  - tests: `tools/check.ps1` runs to completion on this box with no skipped
    branch.
  - negative: `rg -n 'E:\\\\Projects' F:\Projects\Brokkr` returns nothing.
  - negative: `rg -n 'brokkr-daemon -- serve'` returns nothing.

### Cut 2. Make the Unity package installable beside CultLib

- **Repo/branch:** Brokkr, same branch. Depends on nothing; blocks Cut 5's
  verification.
- **First:** record Aetheria's resolved hashes from
  `F:\Projects\Aetheria\Packages\packages-lock.json:245-266` so a regression is
  attributable.
- **Deletes first:** the entire
  `surfaces/unity/Packages/com.gamecult.brokkr/Plugins/CultMesh/` tree (27 DLLs
  plus `.meta` files) and `Plugins.meta`, `Plugins/CultMesh.meta`. These are the
  collision and they are stale.
- **Keeps and moves:** `tools/vendor-cultmesh-unity.ps1` is retired with them;
  the package stops carrying its own copy of CultLib.
- **Adds:** a `dependencies` block in `package.json` naming
  `org.gamecult.cultlib` at the same git tag Aetheria pins, and
  `"unity": "6000.3"` only if 2022.3 support is actually abandoned (see Q7).
- **Per-file changes:**
  - `surfaces/unity/Packages/com.gamecult.brokkr/Editor/GameCult.Brokkr.Editor.asmdef:4-9`:
    references `["GameCult.Brokkr", "GameCult.Caching", "GameCult.Mesh",
    "GameCult.Networking", "R3"]` become `["GameCult.Brokkr", "GameCult.CultLib"]`.
  - `surfaces/unity/Packages/com.gamecult.brokkr/Runtime/GameCult.Brokkr.asmdef:4-7`:
    references `["GameCult.Caching", "MessagePack"]` become `["GameCult.CultLib"]`.
  - `surfaces/unity/Packages/com.gamecult.brokkr/package.json:5`: add
    `"dependencies": {"org.gamecult.cultlib": "https://github.com/GameCult/CultLib.git?path=/unity/org.gamecult.cultlib#cultlib-unity-v1.0.60"}`.
  - `tools/check.ps1:100-111`: the required-DLL assertion inverts — assert the
    vendored tree is *absent* and the asmdefs reference `GameCult.CultLib`.
- **Authority map:**
  - Owner: `org.gamecult.cultlib` owns the CultCache/CultNet/CultMesh assemblies
    in every Unity project. `com.gamecult.brokkr` owns only Brokkr's document
    types, editor service, executor and window.
  - Inputs: the host project's resolved CultLib package version.
  - Outputs: `GameCult.Brokkr` and `GameCult.Brokkr.Editor` assemblies.
  - Derived state: none.
  - Forbidden writers: the Brokkr package may no longer ship any assembly whose
    name CultLib also ships.
  - Shared paths: Aetheria and any future host project resolve one CultLib.
  - Deletion line: `Plugins/CultMesh/` and the vendoring script, before any
    asmdef edit.
- **Verification:**
  - builds: add `"com.gamecult.brokkr": "file:F:/Projects/Brokkr/surfaces/unity/Packages/com.gamecult.brokkr"`
    to `F:\Projects\Aetheria\Packages\manifest.json`, open Unity 6000.3.24f1,
    and confirm a clean compile with no duplicate-assembly error in
    `Editor.log`. This is also the first real test of whether the package's
    source compiles against cultlib 1.0.60's API at all — the vendored DLLs were
    an order of magnitude smaller, so drift is likely and `StartNodeAsync`,
    `CultMeshNodeOptions.EnableDurableShardLogs`, `CultNetDatabaseOptions.RuntimeId`
    and `node.Database.Watch<T>()` each need to still exist.
  - negative: `packages-lock.json` gains `com.gamecult.brokkr` and nothing else;
    no new transitive package appears.
  - operator: Unity's Package Manager shows Brokkr with no errors and
    `GameCult > Brokkr` opens.

### Cut 3. Move command drain off the window

- **Repo/branch:** Brokkr, same branch. Depends on Cut 2.
- **First:** none.
- **Deletes first:** `BrokkrWindow.cs:113-114` (mirror disposal in `OnDisable`),
  `:102`/`:110` (the `EditorApplication.update` hook/unhook), `:775-788`
  (`OnEditorUpdate`), `:377-400` region's ownership of dequeue-and-execute, and
  the `private BrokkrCultMeshMirror mirror` field at `:18`.
- **Keeps and moves:** `PollAndExecuteCommand`'s body moves into the new service
  unchanged in behaviour except for the batch rule below. The window keeps its
  buttons, which now call the service.
- **Adds:** `Editor/BrokkrEditorService.cs`, `[InitializeOnLoad]`, static, owning
  one `BrokkrCultMeshMirror` for the editor's lifetime, hooking
  `EditorApplication.update` once, draining *all* queued commands per tick rather
  than one per second, and surviving domain reload by re-opening on the static
  constructor. Gate on an `EditorPrefs` enable flag (renamed from
  `AutoPollCommands`, default still false) so an unattended project does not
  silently host a mutation endpoint.
- **Per-file changes:**
  - `BrokkrCultMeshMirror.cs:16`: the `Queue<BrokkrUnityCommand>` stays, but the
    service owns dequeuing. No change to the watch.
  - `BrokkrWindow.cs:65-114`: `OnEnable`/`OnDisable` stop touching the mirror;
    they read service state for display only.
  - `BrokkrSettings.cs:23-27`: `AutoPollCommands` becomes `AgentCommandsEnabled`,
    same default `false`.
- **Authority map:**
  - Owner: `BrokkrEditorService` owns mirror lifecycle and command drain.
  - Inputs: `AgentCommandsEnabled`, `CultMeshCachePath`, the watch queue.
  - Outputs: executed mutations, `brokkr.unity.command_receipt.v0`, refreshed
    `brokkr.unity.host_snapshot.v0`.
  - Derived state: `BrokkrWindow`'s `lastReceipt`, `lastSnapshot`,
    `lastSyncReceipt` are display-only. The window is no longer an owner.
  - Forbidden writers: `BrokkrWindow.OnDisable` may not dispose the mirror;
    nothing but the service may call `TryDequeueCommand`.
  - Shared paths: window-button commands, agent-sent commands and daemon
    `sync-once` commands all land in the same queue and take the same
    `BrokkrUnityCommandExecutor.Execute` path.
  - Deletion line: the window's mirror field and update hook, deleted before the
    service is wired.
- **Verification:**
  - builds: Aetheria compiles.
  - operator: enable the flag, **close the Brokkr window**, send a command, see
    it execute. That negative — the old path could not do this — is the point of
    the cut.
  - negative: `rg -n 'EditorApplication.update' surfaces/unity` matches only
    `BrokkrEditorService.cs`.

### Cut 4. Make the editor reachable and awake

- **Repo/branch:** Brokkr, same branch. Depends on Cut 3.
- **First:** measure it. With the service running, unfocus Unity, send a command
  from a second process, and time the receipt. If it lands in under a second the
  unfocused-tick worry is theoretical on Unity 6000.3 and this cut shrinks to
  endpoint publication alone. **Do not build the compensator before the
  measurement.**
- **Deletes first:** nothing.
- **Adds:**
  - `Runtime/BrokkrEndpoint.cs`: `brokkr.unity.endpoint.v0` — host, port,
    `projectPath`, `unityVersion`, `startedAt`, `agentCommandsEnabled`, process
    id. Published by the service on start into the mirror at
    `unity/endpoint/current`, and written as a plain sibling file
    `<project>/.brokkr/endpoint.cc` so an agent can find a live editor without
    already being connected to it. The file is a discovery pointer, not
    authority; the document in the mirror is the truth.
  - Only if the measurement demands it: a keep-awake that does not lie about
    ownership. `EditorApplication.update` stays the single drain; the addition is
    a background `System.Threading.Timer` that calls
    `EditorApplication.QueuePlayerLoopUpdate()`/`delayCall` to force ticks while
    `agentCommandsEnabled` is set. The timer schedules; it never executes a
    command off the main thread.
- **Per-file changes:** `BrokkrEditorService.cs` publishes the endpoint on start
  and clears it on `quitting`.
- **Authority map:** Owner: the service owns the endpoint document. Inputs:
  `node.Server` port, `Application`. Outputs: `brokkr.unity.endpoint.v0`.
  Derived state: `.brokkr/endpoint.cc` is a discovery cache; a stale one must be
  detectable (check pid, refuse on mismatch). Forbidden writers: the agent CLI
  may read it and must never write it. Deletion line: n/a.
- **Verification:**
  - operator: with Unity unfocused and a browser in front, an agent command
    executes within a stated bound; record the measured latency in the doc.
  - negative: kill Unity, and the CLI reports "no live editor" from the pid
    check rather than hanging on a connect.

### Cut 5. `brokkr-ctl`: the agent's hands

- **Repo/branch:** Brokkr, same branch. Depends on Cuts 2-4.
- **First:** none.
- **Deletes first:** nothing. This is net-new surface and must justify itself:
  it buys the named capability (an agent process drives a live editor) that no
  existing owner provides, because `brokkr-daemon` writes files the editor cannot
  see and the Unity window is not callable from outside Unity.
- **Adds:** `tools/brokkr-ctl/` — a .NET console project referencing CultLib's
  `GameCult.Mesh`/`GameCult.Networking` projects and Brokkr's document types.
  Subcommands, all reading `.brokkr/endpoint.cc` for the target:
  - `snapshot [--project PATH]` — connect, read `unity/host/current`, print it.
  - `send --action <a> [--target-object-id ID] [--name N] [--component-type T]
    [--property-path P] [--value V] [--asset-path A] [--parent-object-id P]
    [--local-position x,y,z] [...]` — build a `BrokkrUnityCommand`, put it at
    `unity/commands/{guid}`, then block on the matching
    `unity/receipts/{commandId}` with a timeout, print the receipt, exit non-zero
    on `status != accepted`.
  - `send --file plan.cc` — a batch of intents applied in order, stopping at the
    first failure, printing every receipt. This is what makes scene rigging
    usable instead of a hundred process launches.
  - `watch-receipts` — tail receipts.
  The document types are shared with the Unity package rather than redeclared:
  the `Runtime/` `.cs` files are compiled into `brokkr-ctl` by `<Compile Include>`
  so there is exactly one definition of `brokkr.unity.command_intent.v0`.
- **Authority map:**
  - Owner: `brokkr-ctl` owns nothing. It is a caller. Unity owns the mutation;
    the receipt owns the outcome; the snapshot owns editor truth.
  - Inputs: CLI args, `.brokkr/endpoint.cc`.
  - Outputs: one `brokkr.unity.command_intent.v0` per invocation, to the live
    node over CultNet.
  - Derived state: printed text is telemetry. Exit code is derived from the
    receipt `status`, never from "the put succeeded".
  - Forbidden writers: `brokkr-ctl` must never open the `.ccmp` file. That path
    is invisible to a running editor and clobbered by its next flush. It must
    never write receipts, snapshots or endpoint documents.
  - Shared paths: `brokkr-ctl`, the Brokkr window's buttons and
    `brokkr-daemon sync-once` all produce the same intent document and go through
    the same executor. No second commit primitive.
  - Deletion line: if `brokkr-ctl` grows its own policy, its own receipt ledger,
    or its own idea of editor state, cut it back to a caller.
- **Verification — this is the decisive one:**
  1. Open `F:\Projects\Aetheria` in Unity 6000.3.24f1 with the Brokkr package
     installed. Enable agent commands. Note `.brokkr/endpoint.cc`.
  2. From a Claude Code session, run
     `brokkr-ctl send --action createGameObject --name BrokkrProofOfLife`.
     Assert: exit 0, receipt `status=accepted`, receipt `objectId` is a
     `GlobalObjectId` string.
  3. `brokkr-ctl send --action attachComponent --target-object-id <that id>
     --component-type UnityEngine.BoxCollider` → accepted.
  4. `brokkr-ctl send --action setGameObjectTransform --target-object-id <that id>
     --local-position 1,2,3` → accepted.
  5. `brokkr-ctl snapshot` → the returned `brokkr.unity.host_snapshot.v0`
     contains a `BrokkrGameObjectSnapshot` named `BrokkrProofOfLife` with
     `localPosition` `(1.0, 2.0, 3.0)` and a `BoxCollider` in `components`.
  6. **The layer the operator sees:** the operator looks at the Unity Hierarchy
     and the Inspector and confirms the object, the collider and the transform
     are there, and that the scene shows dirty. A receipt that says accepted while
     the Hierarchy is empty is the failure this step exists to catch — the
     executor writes its own receipt, so the receipt alone cannot prove the
     mutation.
  7. Undo (Ctrl+Z) removes it, proving the `Undo.RegisterCreatedObjectUndo` path
     at `BrokkrUnityCommandExecutor.cs:43` is real and the operator retains a way
     out.
  8. Negative: with agent commands disabled, step 2 times out and exits non-zero
     without mutating anything.

### Cut 6. Admission and the save question

- **Repo/branch:** Brokkr, same branch. Depends on Cut 5.
- **First:** verify what `Server` binds. `Server.cs:26` fixes the port at 3075
  but the bind address was not established in this pass. If it binds `0.0.0.0`,
  every machine on the LAN can currently mutate an open Unity project, and this
  cut is urgent rather than tidy.
- **Deletes first:** nothing, because there is nothing. Stated plainly: today
  admission is absent, not weak.
- **Adds:**
  - Loopback-only binding for the Brokkr mirror node, or an explicit
    operator opt-in to bind wider.
  - A `BrokkrCommandPolicy` consulted by the service before
    `BrokkrUnityCommandExecutor.Execute`: an action allowlist and an asset-path
    prefix allowlist, defaulting to scene mutation permitted and asset-creating
    actions (`createScriptableObject`, `createPrefabVariant`) denied. Denials
    produce a `status=denied` receipt, so a refusal is as inspectable as an
    acceptance.
  - `requestedBy` on the intent and `deniedReason` on the receipt, so a receipt
    says who asked, not only what happened.
  - A `saveScene` action, gated by the same policy and denied by default (Q4).
- **Authority map:** Owner: `BrokkrCommandPolicy` owns admission. Inputs:
  the intent, EditorPrefs policy. Outputs: permit/deny. Derived state: the
  receipt's `status`. Forbidden writers: the executor may not bypass the policy;
  the window's own buttons go through it too, so operator and agent share one
  admission path rather than two truths. Deletion line: n/a.
- **Verification:**
  - negative: a `createScriptableObject` intent under default policy yields
    `status=denied` and creates no asset — verified by `AssetDatabase` absence,
    not by the receipt.
  - negative: `rg -n 'Execute\(' surfaces/unity` shows the policy call on every
    path into the executor.

## Subtraction ledger (estimate)

| Cut | Removed | Added | Deps/targets |
|---|---|---|---|
| 1 | ~30 lines docs/scripts, 1 dead branch | ~15 lines | — |
| 2 | 27 DLLs + 27 `.meta` (~6 MB), 1 script (~55 lines) | ~6 lines manifest | −0 packages in Brokkr, +1 UPM dep declared, +1 UPM dep in Aetheria |
| 3 | ~45 lines from `BrokkrWindow.cs` | ~90 lines (`BrokkrEditorService.cs`) | — |
| 4 | — | ~70 lines + 1 document type | +1 schema |
| 5 | — | ~350 lines | **+1 build target** (`tools/brokkr-ctl`, .NET console), +2 project references to CultLib |
| 6 | — | ~120 lines | — |

Net: strongly negative in shipped bytes (the vendored DLL tree dwarfs everything
added), net +1 executable target and +2 schemas. The one new target is the whole
point of the campaign's gap and is the thing the MCP bridge later wraps rather
than replaces. Build budget: `cargo build/test --workspace` already runs in 24s
cold, and nothing here touches the Rust crate. The new .NET target builds
`GameCult.Mesh` + `GameCult.Networking` from CultLib source — check that cost on
first build; if it exceeds a few seconds, reference the packed assemblies
instead. Build host is this Windows box and the artifacts run on it, so no
cross-platform claim is being made.

## Operator forks

**Q1 — Where the agent-side tool lives, and in what language. Most blocking:
everything after Cut 2 assumes an answer.**
- A: `tools/brokkr-ctl`, a .NET console in this repo, CultNet client over the
  Unity node's port.
- B: Extend `brokkr-daemon` in Rust with a `send`/`snapshot` subcommand.
- C: No tool; agents poke the `.ccmp` file.

**Recommended: A.** C is dead on the evidence — a file write is invisible to the
running editor's `Watch` and gets clobbered by its next flush. B needs a typed
document-put client in `cultnet-rs` that does not exist today; the RUDP and
schema primitives are there, so it is buildable, but it is a campaign-sized
detour to reach parity with a C# client that already works. A reuses
`CultNetDocumentRegistry.CreateRawDocumentPutMessage` and the same document
`.cs` files Unity compiles, so there is exactly one definition of the intent
schema. When the MCP bridge lands in Rust, `brokkr-ctl` is what it replaces, and
the intent/receipt contract it exercised is what the bridge lowers.

**Q2 — Does the editor poll or subscribe?**
- A: Subscribe. The mirror already does (`BrokkrCultMeshMirror.cs:44-52`); the
  bug is that the *drain* of the subscription queue is window-owned and
  rate-limited to one command per second.
- B: Add an explicit poll of the backing store.

**Recommended: A.** B would mean re-pulling the `.ccmp` in the editor and
creating a second delivery path with different semantics — two truths about how
a command arrives. Cut 3 fixes the real defect (ownership and batching) without
inventing a lane.

**Q3 — Unfocused ticking.**
- A: Measure first (Cut 4's "First"), and only add a keep-awake timer if the
  measurement shows a stall.
- B: Add the timer now.
- C: Require the editor focused; document it and move on.

**Recommended: A.** B is a compensator bought before the symptom is confirmed on
Unity 6000.3. C is honest but makes the tool useless for the actual use — an
agent drives Unity while the operator is elsewhere.

**Q4 — Does scene save become a command?**
- A: New `saveScene` action, denied by default in policy, opt-in per project.
- B: Save stays the operator's, always.

**Recommended: A, shipped denied.** B is safer today and is what Cut 5's
verification assumes, but it means an agent rigging fifty objects leaves all of
it in volatile editor memory, and one crash or one mis-clicked "Don't Save"
takes the lot. A with a default denial keeps the operator's hand on the switch
while making the capability exist and inspectable. If you would rather not have
the action in the codebase at all, B is defensible; say so and Cut 6 drops it.

**Q5 — MCP server now, or CLI the bridge wraps?**
- A: CLI now; the campaign's generic CultMesh MCP bridge wraps or replaces it.
- B: A Brokkr-specific MCP server now.

**Recommended: A.** The campaign doc is explicit that Brokkr-specific tooling
treats the symptom and that the missing organ is general
(`mcp-bridge-campaign.md`, "Brokkr-specific tooling would treat the symptom").
A Brokkr MCP server is exactly the thing the campaign says not to build, and it
would have to be deleted. A CLI is a caller — the bridge invokes the same typed
operation over the same endpoint, and `brokkr-ctl` either becomes a thin shim or
goes away without anything else moving. It also answers the campaign's own open
question ("what a provider must publish before it is usable through the bridge,
and whether Brokkr already publishes it") with a worked example: Brokkr publishes
the commands and receipts but not the endpoint, which is Cut 4.

**Q6 — The hard-coded port 3075 (`Server.cs:26`).**
- A: Accept it; one Brokkr-hosting Unity editor per machine, and the endpoint
  document says which project owns it.
- B: Push a port option into `CultNetHostOptions` in CultLib.

**Recommended: A for this slice, B as a CultLib follow-up.** B is a change to
shared substrate every runtime depends on, and it does not belong inside an
unblock-the-work cut. A is honest as long as `brokkr-ctl` refuses clearly when
`.brokkr/endpoint.cc` names a different project than the one asked for — which
is worth stating as a requirement, because the silent failure (commands landing
in the wrong Unity project) is exactly the class of damage this whole effort
exists to stop.

**Q7 — Does `com.gamecult.brokkr` stay self-contained?**
- A: Depend on `org.gamecult.cultlib`; drop the vendored DLLs (Cut 2 as written).
- B: Keep vendoring, and make it installable only in projects without CultLib.

**Recommended: A.** B cannot serve the immediate consumer at all: Aetheria has
CultLib and the assembly names collide. A also ends the staleness — the vendored
`GameCult.Mesh.dll` is a tenth the size of the one Aetheria resolves, which means
the package has been compiling against a CultMesh from a different era. Expect
Cut 2 to surface real API drift; that is the cut doing its job, not a surprise.
