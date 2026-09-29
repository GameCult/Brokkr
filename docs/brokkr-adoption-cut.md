# Brokkr: adopting `codex/cultmesh-unity-dll-refresh` — cut map

Status: cut map, nothing landed. Written by Imagination on 2026-09-29.

Measured against:
- Brokkr `main` at `7255203`;
- donor `origin/codex/cultmesh-unity-dll-refresh` at `9cc4bf3`, with merge-base `c40f5fe`: 22 commits ahead and 4 behind;
- CultLib `origin/main` at `93fe1b9`;
- the CultLib Unity release tag `cultlib-unity-v1.0.60`, which is `45c2f40` and an ancestor of `93fe1b9`.

This map supersedes the means in `docs/agent-access-cut.md` (Brokkr `main`, parked on 2026-09-18). Self should mark that doc as history and point it here once the operator rules on F1. That doc's probe findings are re-scored in §3.

Commits nothing, switches no tree. Builds ran on Yggdrasil only. Unity and Windows checks are flagged for the operator or Starfire; none of them were run.

---


## Rulings (operator, 2026-09-30)

- **F1: unpark agent access.** Operator: "me agreeing to do the Editor shenanigans then was not a
  permanent commitment to always do all the editor shenanigans". The maintenance cuts land first, then
  the agent-access cuts.
- **F2: re-land as fresh commits (Self's default).** No merge, so 7.5 MB of DLL blobs never enter
  `main`'s history.
- **F3: park the prefab CDN pipeline** at `parked/brokkr-prefab-cdn`, with a note.
- **F4 A: file transport.** Commands travel through the directory store at `<project>/.brokkr/`. There
  is no network listener.
- **F5 A: the command sink is off by default,** with one visible toggle per project that also shows in
  the host snapshot.
- **F6 A: command ids are single-use.** Each writer mints a fresh id, and sync puts a pass or content
  hash into the id.

## 0. The split the operator has to see first

The donor contains **four** things, not three. The operator's adoption covered "DLL refresh, editor command control, durable commands after external pulls". It did not name the fourth: a prefab CDN pipeline that shipped inside commit `8d5b580`. That commit also carries the auto-starting editor bridge, so it cannot be taken whole under either heading.

| Donor content | Commits | Category | Recommendation |
|---|---|---|---|
| 17 DLL refresh commits (`eeb4e82`..`969d44c`, excluding `8d5b580`) | 17 | **churn**: every DLL they refresh is deleted later by `560c547` | Drop. Do not merge the history (F2). |
| Delete the 27 vendored DLLs and `tools/vendor-cultmesh-unity.ps1`; depend on `org.gamecult.cultlib`; invert `check.ps1` | part of `560c547` | **maintenance** | Keep the intent. Rewrite the shape (M1). |
| Editor lifecycle actions (`refreshAssets`, `setEditorPlayState`, `setEditorPaused`, `captureEditorView`) and host-snapshot play-state fields | part of `560c547` | **agent access** (parked) | Keep, gated on F1 (A4). |
| `BrokkrEditorDaemonBridge` plus two re-registration hooks, auto-started by default | part of `8d5b580` | **agent access** (parked) | Rewrite (A1). |
| Directory store, `StartServer=false`, `brokkr-command`/`brokkr-contracts`, Rust `unity-command` removed | `821f9d3` | **agent access** (parked) | Keep the mechanism (it is probe-proven, §2). Rewrite the edges (A1, A3). |
| `readHost` CLI | `d90b2c4` | **agent access** (parked) | Keep (A3). |
| Durable-command dedup after external pull | `9cc4bf3` | **agent access** (parked) | Keep the idea. The identity rule is wrong (F6, A2). |
| Unity prefab mirror snapshot, Blender import/publish, README "Prefab CDN Pipeline", daemon advertisement rows, `tools/brokkr-unity-cache.py` (1,658 lines) | `8d5b580` | **prefab CDN pipeline**: a fourth capability, not in the brief | Park at a tag (F3). |

**The line:** only M1 and M2 are maintenance. Everything under "agent access" is the capability the operator parked on 2026-09-18 ("screw it, I'll do any editor shenanigans we need for now"). Landing any A-cut means unparking it. Adopting the branch does not settle that question; F1 does.

---

## 1. Operator forks

One decision per fork. Each fork lists what depends on its answer.

### F1. Unpark agent access to the editor, or land maintenance only? (most blocking)

**Context.** The parked map states its own unpark condition (`docs/agent-access-cut.md:6-8`): "when editor work becomes repetitive enough to be worth six cuts in this repo, or when the CultMesh MCP bridge campaign ... takes it up."

The second trigger has not fired. `CultLib src/GameCult.Mesh/docs/mcp-bridge-campaign.md:5-7` reads "named, not started ... for another day", with nobody assigned.

The first trigger is a fact only the operator knows. The donor does change the price. The hard part the parked map called unviable (commands from another process reaching a live editor) now works: it was probed at 114 of 114 (§2). What remains is five mostly-rewrite cuts, A1-A5, instead of six mostly-new ones.

- **A:** Land M1 and M2 only. Agent access stays parked. The donor's agent-access code is not landed and survives at a tag (F2), with this map as its landing plan.
- **B:** Land M1, M2 and A1-A5. Agent access is unparked.
- **C:** Merge the donor as it is.

**Recommended: A, unless the first unpark trigger has fired.** In that case choose B, because B costs little more.

Against C: the donor has four defects that the operator would inherit silently.
- Split command authority: the window drains commands too (A1).
- Default-on command execution in every project that installs the package (F5).
- A dedup rule that permanently freezes any command id that gets reused (F6).
- A Python CultCache fallback (F3).

**Depends on F1:** every A-cut, F4, F5, F6.

### F2. Merge the donor's history, or re-land its content from `main`?

**Context.** Merging `9cc4bf3` would put 40 DLL blobs (7,540,224 bytes) into `main`'s reachable history, only for them to be deleted again. The merge is textually clean (`git merge-tree --write-tree main 9cc4bf3` gives tree `deb2a56` with no conflicts). It is also semantically dirty: the donor's asmdef shape, its version pin to 1.0.16, and its E:\ paths all come across.

- **A:** Re-land. Fresh commits from `main`. Take files from the donor with `git checkout 9cc4bf3 -- <path>` where a cut says so. Tag the donor as `parked/codex-unity-dll-refresh` so the provenance and the prefab work (F3) survive. The remote branch can go once the tag exists.
- **B:** Merge, then fix forward.

**Recommended: A.** It is cheaper for every future clone, and each cut stays separately falsifiable by Soul.

### F3. What happens to the prefab CDN pipeline (`8d5b580`)?

**Context.** CultLib's `src/GameCult.Mesh/docs/distributed-cdn.md:28-38,167-169` names `brokkr.unity.prefab_mirror_snapshot.v0` and `brokkr.prefab.snapshot.v0` as the authoring path into `CultMeshEntityPrefabPackage`, and that package does exist (`CultMesh.cs:697-716`). There is no consumer, though:
- Nothing outside Brokkr's donor branch reads either schema. An `rg` across `F:\Projects` for .cs/.rs/.ts/.py/.md files found only that doc and its vendored copies.
- The "deployer" in the donor README is prose only.
- Blender reads the Unity snapshot from *its own* cache (`blender_target.py` `import_latest_unity_prefab_mirror`, `node.database.snapshot()` on `cache_path`). Nothing moves the snapshot out of Unity's cache, so the chain only closes if both editors share one store. The Unity side is now a directory store and `cultcache-py` has only a single-file store (`packages/cultcache-py/src/cultcache_py/stores.py:83`), so they cannot share one.
- `tools/brokkr-unity-cache.py:77-139` re-implements the CultCache single-file store in raw msgpack when `cultcache_py` fails to import. It defaults to `E:\` paths (`:24`, `:69-70`) and hand-encodes Eve TUI graphs (`:587-1181`). This is heretek by the substrate doctrine.

Options:
- **A:** Park the whole of `8d5b580`'s prefab content at the F2 tag, with a note. It is design intent without a consumer. CultLib's doc stays as intent.
- **B:** Land the Unity and Blender halves and cut the Python tool.
- **C:** Land it as it is.

**Recommended: A.** Per Eureka, a surface with design intent and no consumer is parked, not deleted. Leaving it parked also costs nothing, since M1 does not depend on it. Taking it up later is its own campaign, because it needs a store both editors can open, which is a CultLib (`cultcache-py`) gap.

### F4 (only if F1=B). How do commands travel: the directory-store file, or a CultNet put?

**Context.** The parked map chose a CultNet put to the editor's hosted server (its Q1/Q2). It called the file route dead, but only for the single-file store with no pull. The donor switched to a directory store, `StartServer=false`, and a pull once a second.

Measured (§2): 114 of 114 commands were delivered, each executed exactly once, and no command or receipt was lost. That held against an "editor" flushing every 20 ms on current CultLib. The directory store takes a per-commit lease and rewrites only its dirty keys (`DirectoryMessagePackBackingStore.cs:171-223, 247-297`).

- **A:** File transport (the donor's). There is no listener, so no LAN exposure, and admission starts at filesystem permissions. Discovery is the fixed path `<project>/.brokkr/unity-editor.ccmp`. Parked Q6 (the hard-coded port 3075) goes away. Costs: latency of up to about one pull interval, and a pull of the whole manifest each second.
- **B:** CultNet put (the parked Cuts 4-5). This needs an endpoint document, a port option in CultLib, and admission on a network path.

**Recommended: A.** It is proven, local-only, and has one fewer organ. When the MCP bridge campaign lands it runs on the same box and can write the same intent document. It does not need a network door.

### F5 (only if F1=B). Should the command sink be on or off by default?

**Context.** `BrokkrEditorDaemonBridge.cs:35` defaults `AutoStart` to **true** per project, and `:63` forces the global `AutoPollCommands = true`. So installing the package turns every project into a sink that executes, unattended, anything written into `.brokkr/`. `main` defaults to off (`BrokkrSettings.cs:25`).

- **A:** Off by default. The operator enables it per project with one visible toggle, which also shows in the host snapshot.
- **B:** On by default.

**Recommended: A.** Consent is a structural affordance. An endpoint that mutates a live project should never be switched on by an import.

### F6 (only if F1=B). Is a command id single-use, or a reusable "desired state" slot?

**Context.** The Rust sync reuses ids built from stable names: `stable_id(["sync", binding_id, sync_var_id, "blender-to-unity-transform"])` (`brokkr-daemon/src/main.rs:1068-1073` at `9cc4bf3`, with the same pattern at `:790-1227`). The donor's dedup treats any id that has a receipt as done forever (`BrokkrCultMeshMirror.cs:199-216` and `:180-197` at `9cc4bf3`). Once one transform has been synced, every later value written to that id is silently ignored. The gamecult-ops census also found this (`gamecult-ops/docs/repo-census-2026-09/repos/Brokkr.md`, "Branch state").

- **A:** Single-use ids. An intent is a one-shot act, and every writer mints a fresh id; sync puts a pass or content hash in the id. The receipt answers exactly that id.
- **B:** Reusable slots. A receipt records the command revision it answered (the command's `StoredAt`), and the drain re-runs when the stored command is newer.

**Recommended: A.** It matches the intent/receipt contract the MCP bridge will lower (one operation invoked, one receipt). With A the dedup stays a set of ids. B turns commands into desired state, which is sync's job, and sync has no live path into Unity anyway (follow-up X1).

### Still live from the parked map

- **Parked Q3 (unfocused ticking):** measure before building a keep-awake. The drain is still `EditorApplication.update`.
- **Parked Q4 (`saveScene`):** recommendation unchanged, A, shipped denied.

Parked Q1 (A: .NET caller) and Q7 (A: depend on CultLib) are settled by the donor's shape. Parked Q2 and Q6 are superseded by F4.

---

## 2. What probing established

**The merge is clean.** `git merge-tree --write-tree --name-only main origin/codex/cultmesh-unity-dll-refresh` gives `deb2a56`, exit 0. The merged tree keeps `main`'s CultLib Python path fix (`blender_target.py:17-20`, from `12f9169`) and `main`'s git pin for cultcache-rs (from `94b9334`).

**The merged Rust builds and is green.** Yggdrasil, rust image: the branch tree at `9cc4bf3` with `main`'s `brokkr-daemon/Cargo.toml` and `Cargo.lock` overlaid, which is exactly the merged Rust. `cargo build --workspace` finished in 13.4 s. `cargo test --workspace` ran 20 passed and 0 failed.

**The donor's .NET side compiles against current CultLib.** Yggdrasil, dotnet image: CultLib cloned at `93fe1b9`. `dotnet build -c Release brokkr-command/Brokkr.Command.csproj -p:CultLibRoot=/tmp/CultLib` succeeded. That also compiles `Runtime/*.cs` through `brokkr-contracts`, so Brokkr's document types have no API drift against CultLib `main` (which is at or after 1.0.60).

**Durable commands after an external pull work on current CultLib (Linux).** The probe is a console app that mirrors `BrokkrCultMeshMirror` and `BrokkrEditorDaemonBridge` at `9cc4bf3`:
- the same `CultMesh.CreateNodeAsync` options (`StartServer=false`, `UseDirectoryStore=true`, `EnableDurableShardLogs=true`, `RuntimeId`);
- per tick: pull, scan receipts, execute, write a receipt, soft flush, then publish a host snapshot and soft flush again.

The donor's own `brokkr-command` binary acted as the writer, three processes at a time.

| Editor poll | Commands | CLI exit 0 | Executed / distinct | Record pages |
|---|---|---|---|---|
| 1000 ms (donor cadence) | 24 | 24 | 24 / 24 | 49 (24 commands + 24 receipts + 1 host) |
| 20 ms (contention) | 90 | 90 | 90 / 90 | 181 (90 + 90 + 1) |

The probe source is at `scratchpad/brokkr-probe/` (`editor-probe/`, `run.sh`), and the log at `scratchpad/brokkr-probe/dotnet.log`. It proves only Linux file semantics. **A Windows repeat is a Starfire check**, because CultLib has already fixed Windows-specific atomic-replace races once (`c2a9a6e`).

**Which of the 27 DLLs canonical CultLib now serves.** On `main` they live under `surfaces/unity/Packages/com.gamecult.brokkr/Plugins/CultMesh/`: 55 tracked files (27 `.dll`, 27 `.meta`, `CultMesh.meta`), 3,474,533 bytes. `Plugins.meta` sits at the package root.

| Served by `org.gamecult.cultlib` 1.0.60 (`unity/org.gamecult.cultlib/Runtime/Plugins`, same names) | 23 |
|---|---|
| ConcurrentCollections, GameCult.Caching, GameCult.Caching.MessagePack, GameCult.Logging, GameCult.Mesh, GameCult.Networking, Isopoh.Cryptography.Argon2/Blake2b/SecureArray, LiteNetLib, MessagePack, MessagePack.Annotations, Microsoft.Bcl.AsyncInterfaces, Microsoft.Bcl.TimeProvider, Microsoft.NET.StringTools, R3, System.Collections.Immutable, System.ComponentModel.Annotations, System.IO.Pipelines, System.Runtime.CompilerServices.Unsafe, System.Text.Encodings.Web, System.Text.Json, System.Threading.Channels | |

| Not shipped by CultLib, supplied by Unity's .NET Standard 2.1 profile | 4 |
|---|---|
| System.Buffers, System.Memory, System.Numerics.Vectors, System.Threading.Tasks.Extensions. CultLib's publish allowlist (`scripts/build-unity-package.ps1:104-130`) leaves them out on purpose, and Aetheria compiles against it. | |

CultLib additionally ships `GameCult.Mesh.Quic.Native`, `GameCult.Networking.WebSockets` and native `x86_64/` plugins, which Brokkr never had. **All 27 can go.** None needs a replacement inside Brokkr.

**The canonical consumer shape exists, and the donor does not use it.** CultLib's own Studio package is the proven pattern:
- it declares `"org.gamecult.cultlib": "1.0.60"` (`src/GameCult.Unity/Assets/Caching/package.json`);
- its asmdef is `references: ["GameCult.CultLib"]` with `overrideReferences: false` (`.../Editor/GameCult.Unity.Caching.Editor.asmdef`);
- CultLib's DLL `.meta` files carry importer defaults, so they are auto-referenced;
- Aetheria already resolves Studio this way (`Aetheria/Packages/manifest.json:54-55`).

The donor instead sets `overrideReferences: true` and hand-lists 21 precompiled names in both asmdefs, which duplicates CultLib's own list. It also pins **1.0.16** (`package.json`, and `tools/check.ps1:58` at `9cc4bf3`) while the host resolves 1.0.60.

**On `main`, the API used by the Unity code exists in 1.0.60 by name and signature:**
- `CultMesh.StartNodeAsync` and `CreateNodeAsync` (`CultMesh.cs:585, 596`);
- `CultNetDatabase.PutAsync<T>(CultRecordKey,T)` (`CultNetDatabase.cs:803`) and `Watch<T>()` (`:1052`);
- `CultMeshNode.FlushAsync(bool soft)` (`CultMesh.cs:433`).

A real Unity compile is the operator's check (M1 verification).

**Defects in the donor, found by reading source. Soul should falsify them rather than trust them:**

- **Two drains, one queue, in one process (PLAUSIBLE, needs Unity).**
  - `BrokkrWindow` at `9cc4bf3` owns a second `BrokkrCultMeshMirror` on the same path (`:21`, `StartMirror :415-427`). It drains commands on its own `EditorApplication.update` (`:106`, `:862-876`), gated on the global `AutoPollCommands`, which the bridge forces to `true` (`BrokkrEditorDaemonBridge.cs:63`).
  - The window's node never pulls, but `StartAsync` calls `RefreshCommandState` (`BrokkrCultMeshMirror.cs:56`). A command that is pending when the window's mirror starts is therefore queued by both mirrors.
  - Failure scenario: `createGameObject` runs twice and produces two objects.
  - Both nodes also open the same default shard-log path under `EnableDurableShardLogs`.
- **Registration compensators.** Start is re-registered from four places: the static constructor, `[InitializeOnLoadMethod]`, an `AssetPostprocessor` on every import (`BrokkrDaemonBridgePostprocessor.cs`, 16 lines), and `[DidReloadScripts]` (`BrokkrDaemonBridgeReloadHook.cs`, 13 lines). `[InitializeOnLoad]` already re-runs after every domain reload, so the other three are repair loops.
- **Arbitrary file write.** `captureEditorView` writes to any rooted `outputPath` (`BrokkrUnityCommandExecutor.cs:84-92` at `9cc4bf3`). Any writer that can reach the command sink can overwrite any file the editor user can write.
- **Main-thread blocking.** `.GetAwaiter().GetResult()` on the editor main thread (`BrokkrEditorDaemonBridge.cs:107,122-123`). It is safe only if every await in CultLib's pull and flush path uses `ConfigureAwait(false)`. `CultMesh.cs:1607` does; the rest is unverified. This is a Soul target, not a cut.
- **The Rust sync path writes a different store kind.**
  - `MirrorStore` (`main.rs:1411-1418` at `9cc4bf3`) opens `SingleFileMessagePackBackingStore` on the same `.ccmp`, and `cultcache-rs` has no directory store (`packages/cultcache-rs/src/lib.rs:401,1029,1403` lists single-file and redb only).
  - Meanwhile `CultCacheMessagePack.Create` (`CultCacheMessagePack.cs:52`) makes Unity read that path as a directory manifest.
  - PLAUSIBLE: sync commands are unreadable, or they clobber the manifest. This is follow-up X1, outside this adoption.

---

## 3. The parked cut map, re-scored against the donor

| Parked cut | What the donor covers | Verdict |
|---|---|---|
| **1. Cut the stale claims** | None. It adds more `E:\` literals (README `:43-45` in the Unity README, `brokkr-unity-cache.py:24,69-70`) and keeps `README.md` "Unity Smoke" `cargo run -p brokkr-daemon -- serve` (`:89` merged, `:61` on `main`). | **Still needed:** M2. |
| **2. Installable beside CultLib** | Mostly. It deletes the DLLs, the vendor script and the check. Wrong shape: `overrideReferences: true` plus a hand-listed precompiled set, pinned to 1.0.16. | **Rewrite:** M1. |
| **3. Move the drain off the window** | Partly. A static bridge drains, but the window still drains too, and the bridge is on by default. | **Rewrite:** A1. |
| **4. Reachable and awake** | Superseded: the transport is now the directory-store file (F4). The endpoint document, pid check and port are all moot. Measuring unfocused ticks is still live (parked Q3). | **Cut, except the measurement** (A4's operator check). |
| **5. `brokkr-ctl`** | Partly. `brokkr-command` handles lifecycle actions and `readHost`. It maps only 6 of the 17 intent fields (`Program.cs:37-46` versus `BrokkrHostSnapshot.cs` `BrokkrUnityCommand` `[Key(0..16)]`). Its `CultLibRoot` default points at a non-existent `..\..\CultLib-codex-cultmesh-reliability` (`Brokkr.Command.csproj:7`, `Brokkr.Contracts.csproj:8`). The parked rule "never open the `.ccmp`" is reversed, and legitimately so, under F4=A. | **Rewrite:** A3. |
| **6. Admission and save** | None. Removing the server does remove the LAN surface. The capture action adds an arbitrary-path write. | **Still needed:** A4, plus parked Q4. |

The parked findings, re-scored:
- "no serve": still true.
- "vendored collision": retired by M1.
- "file-poke dead": overtaken by the directory store plus pull, with the probe as evidence.
- "no admission": still true.

---

## 4. Identity, lifecycle, authority (settled before any cut)

| Persistent kind | What names it | What happens to it over time | Who decides |
|---|---|---|---|
| Unity command intent `brokkr.unity.command_intent.v0` | `unity/commands/{commandId}`. Single-use ids if F6=A. | Written once by a caller. Executed at most once. Never rewritten or deleted in this slice. | Callers write. `BrokkrEditorService` alone decides execution (A1). The executor decides the outcome. |
| Unity command receipt `brokkr.unity.command_receipt.v0` | `unity/receipts/{commandId}`, one per intent | Written once, after execution. It is the only proof of "done". | The service alone writes it. Callers only read. |
| Host snapshot `brokkr.unity.host_snapshot.v0` | `unity/host/current` (overwritten) | Refreshed after each command and on demand. | The service alone. The window displays it. |
| The Unity mirror store | `<project>/.brokkr/unity-editor.ccmp` plus `.records/`, a directory store | Lives as long as the project. It is not version-controlled. | CultLib's directory store owns durability and the multi-writer lease. Brokkr owns only the keys. |
| Agent-command enable flag | a per-project EditorPrefs key (A1) | Off until the operator enables it. It is echoed in the host snapshot. | The operator only (F5). |
| The Unity package's CultLib assemblies | `org.gamecult.cultlib` in the host manifest | Moves when the host bumps CultLib. | The host project (M1). Brokkr ships none. |
| Prefab mirror and prefab snapshot | `prefabs/...` | Parked (F3). | Not in scope. |
| Sync-generated Unity commands (Rust) | `stable_id` slots | Broken on both `main` and the donor. | Follow-up X1. Not in scope. |

---

## 5. Cuts

Deletes come first in every cut. Maintenance cuts are anchored against Brokkr `main` `7255203`. Agent-access cuts are anchored against `main` for code that exists there and against the donor `9cc4bf3` for files taken from it. All work happens on one branch, `adopt-dll-refresh` from `main`, in a worktree Self creates, for example `F:\Projects\Brokkr-adopt`. No Hands pass runs in `F:\Projects\Brokkr` itself.

### M1. Drop the vendored CultLib; depend on `org.gamecult.cultlib`

- **Repo/branch:** Brokkr, `adopt-dll-refresh` from `7255203`. No dependencies.
- **First:** record Aetheria's resolved CultLib lines from `F:\Projects\Aetheria\Packages\packages-lock.json` (the entries for `org.gamecult.cultlib` and `org.gamecult.caching.unity`), so any regression can be attributed.
- **Deletes first:**
  - `surfaces/unity/Packages/com.gamecult.brokkr/Plugins/`, the entire tree: 27 `.dll`, 27 `.meta`, `CultMesh.meta`; 55 files, 3,474,533 bytes;
  - `surfaces/unity/Packages/com.gamecult.brokkr/Plugins.meta`;
  - `tools/vendor-cultmesh-unity.ps1` (52 lines).
- **Keeps and moves:** nothing. The donor's history is not merged (F2). Its commit `560c547` is the reference for which files go, not a source of content.
- **Adds:** nothing new beyond the edits below.
- **Per-file changes:**
  - `surfaces/unity/Packages/com.gamecult.brokkr/package.json:6-7`: add `"dependencies": { "org.gamecult.cultlib": "1.0.60" }`. This is the version CultLib's `unity/org.gamecult.cultlib/package.json` declares and Studio uses. Leave `"unity": "2022.3"` as it is.
  - `Editor/GameCult.Brokkr.Editor.asmdef:4-10`: references become `["GameCult.Brokkr", "GameCult.CultLib"]`. `overrideReferences` stays `false` and `precompiledReferences` stays `[]`, matching `CultLib src/GameCult.Unity/Assets/Caching/Editor/GameCult.Unity.Caching.Editor.asmdef`. **Do not** take the donor's `overrideReferences: true` or its 21-name list.
  - `Runtime/GameCult.Brokkr.asmdef:4-7`: references become `["GameCult.CultLib"]`. The rest is unchanged.
  - `tools/check.ps1:51-66`: replace the required-DLL assertion with two checks. First, no `*.dll` exists anywhere under `surfaces/unity/Packages/com.gamecult.brokkr`. Second, `package.json` declares an `org.gamecult.cultlib` dependency. **Do not pin a version string in the check** (the donor's `:58` pinned 1.0.16). A version equality test pins spelling, not behaviour.
  - `surfaces/unity/README.md:15-19`: replace the vendoring step with the host-manifest requirement: `"org.gamecult.cultlib": "https://github.com/GameCult/CultLib.git?path=/unity/org.gamecult.cultlib#cultlib-unity-v1.0.60"`. The donor's `README` wording ("Brokkr does not carry a private CultMesh runtime...") may be reused, with the tag corrected.
- **Authority map:**
  - Owner: `org.gamecult.cultlib` owns every CultCache, CultNet and CultMesh assembly in a Unity project. `com.gamecult.brokkr` owns Brokkr's document types, editor code and window only.
  - Inputs: the host project's resolved CultLib version.
  - Outputs: the `GameCult.Brokkr` and `GameCult.Brokkr.Editor` assemblies.
  - Derived state: none.
  - Forbidden writers: the Brokkr package may not ship any assembly, and no script may re-vendor one.
  - Shared paths: every host project resolves exactly one CultLib.
  - Deletion line: `Plugins/`, `Plugins.meta` and the vendor script go before any asmdef edit.
- **Verification:**
  - builds: `cargo build --workspace && cargo test --workspace` on Yggdrasil (rust image). It is unchanged by this cut, but it guards the branch.
  - negative: `git ls-files surfaces/unity | rg -i '\.dll$'` returns nothing. `rg -n 'vendor-cultmesh-unity' .` returns nothing outside history docs. `rg -n '"overrideReferences": true' surfaces/unity` returns nothing.
  - operator/Starfire:
    1. Add `"com.gamecult.brokkr": "file:F:/Projects/Brokkr-adopt/surfaces/unity/Packages/com.gamecult.brokkr"` to Aetheria's manifest.
    2. Open Unity 6000.3.24f1.
    3. `Editor.log` shows no duplicate-assembly error and no `CS0246`/`CS0234` from `GameCult.Brokkr*`.
    4. `packages-lock.json` gains only `com.gamecult.brokkr`.
    5. `GameCult > Brokkr` opens.
    6. **Revert the manifest line afterwards.** Installing Brokkr in Aetheria is not part of this cut.
    This is also the first real test of whether `main`'s editor code compiles against 1.0.60.
- **Operator questions:** none beyond F2.

### M2. Cut the stale claims

- **Repo/branch:** same branch, after M1.
- **Deletes first:**
  - `README.md:58-72` (the "Unity Smoke" `cargo run -p brokkr-daemon -- serve` and the `file:E:/...` manifest line);
  - `tools/check.ps1:90-94` (the dead `E:\Projects\CultLib-main-work` Blender probe, which is silently skipped).
- **Per-file changes:**
  - `README.md`: in place of the deleted lines, name the four real subcommands (`main.rs:131-140`). Say that `brokkr-daemon` is a CLI over cache files, not a service. The install path becomes `file:F:/Projects/Brokkr/...`.
  - `surfaces/unity/README.md:12`: `E:/` becomes `F:/`.
  - `tools/check.ps1:90`: the Blender CultMesh smoke takes `-CultLibRoot` (default `F:\Projects\CultLib`), puts the three `packages/*/src` directories on the path the way `blender_target.py:17-20` does, and **fails** when the root is absent instead of skipping.
- **Authority map:** Owner: the docs and `tools/` describe the real CLI (`main.rs:131-140`). Forbidden writers: docs may not name subcommands that do not exist. Deletion line: every `E:\` literal in `README.md`, `surfaces/unity/README.md` and `tools/check.ps1`.
- **Verification:**
  - negative: `rg -n 'E:[\\/]Projects' README.md surfaces tools` returns nothing. `rg -n 'brokkr-daemon -- serve'` returns nothing.
  - Starfire: `tools/check.ps1` runs to completion with no skipped branch. It is Windows PowerShell and light (`cargo test` of one crate). Run it one job at a time.
- **Out of scope, recorded:** `.voidbot/voice/identity.json:4,18,22` and `tools/persona-*.ps1` carry `E:\`. They are VoidBot's Persona surface, so they are routed to VoidBot's owner, not fixed here.

---

**Gate: the A-cuts land only if F1 = B. They also assume F4=A, F5=A and F6=A; a different answer re-maps A1-A3.**

### A1. One command owner: `BrokkrEditorService` over the directory store

- **Repo/branch:** same branch, after M1.
- **Deletes first:** all on `main`.
  - `Editor/BrokkrWindow.cs`: the auto-poll drain in `OnEditorUpdate` at `:775-790`, where `autoPollCommands` gates `PollAndExecuteCommand`. Also the `autoPollCommands` field `:13`, its load `:70`, its toggle `:122` and save `:129`, and the `Poll Mirror Command` button `:182` together with `PollAndExecuteCommand` `:377-400`.
  - The window's mirror ownership: the field `:19`, `StartMirror :363-375`, and the `OnDisable` dispose `:111`.
  - `PublishCommandAndPoll :519-523` becomes publish-only. The window no longer executes.
  - `Editor/BrokkrSettings.cs:23-27` (`AutoPollCommands`, a key global to the whole machine).
  - **Never bring over** from the donor `BrokkrDaemonBridgePostprocessor.cs` (16 lines), `BrokkrDaemonBridgeReloadHook.cs` (13 lines), or their metas.
- **Keeps and moves (from `9cc4bf3`):**
  - `Editor/BrokkrCultMeshMirror.cs`: take the donor's `StartAsync :29-74` (with `CreateNodeAsync`, `StartServer=false`, `UseDirectoryStore=true`), `PullExternalUpdatesAsync :83-88`, `TryDequeueCommand :161-178`, `RefreshCommandState :180-197`, `TryQueueCommand :199-206` and `HasReceipt :208-216`. Leave out the prefab publish `:90-98` (parked under F3).
  - `Editor/BrokkrEditorDaemonBridge.cs` becomes `Editor/BrokkrEditorService.cs`. It is not a daemon (the census makes the same point). Keep `[InitializeOnLoad]`, the single `EditorApplication.update` registration, `DrainCommands`, and the pull cadence.
- **Adds:**
  - The per-project `AgentCommandsEnabled` (EditorPrefs key suffixed with `Application.dataPath`, **default false**), replacing `AutoStart` (`:33-37`, default true) and deleting the `AutoPollCommands = true` write at `:63`.
  - The window gets one toggle bound to it and a read-only display of service state.
  - The service publishes the flag in `BrokkrHostSnapshot` (add a field at the next free key, `[Key(18)]`), so a caller can see why nothing executes.
- **Split for testability.** The dedup and queue rules (`RefreshCommandState`, `TryQueueCommand`, `HasReceipt`, and the ordering by `StoredAt` then key) are pure CultCache logic. Move them into `Runtime/BrokkrCommandLedger.cs` over a `CultCache`, so `brokkr-contracts` compiles them outside Unity. The mirror calls the ledger. **Owner:** the ledger. **Consumer:** the service. **Invariant it protects:** each intent id executes at most once, and at least once while the sink is enabled. No other surface can test this invariant.
- **Authority map:**
  - Owner: `BrokkrEditorService` owns the mirror lifecycle, the pull cadence and the drain. `BrokkrCommandLedger` owns "is this id pending".
  - Inputs: `AgentCommandsEnabled`, `CultMeshCachePath`, the pulled store.
  - Outputs: executed mutations, receipts, the host snapshot.
  - Derived state: the window's `lastReceipt`, `lastSnapshot` and `lastSyncReceipt` are display-only. **The window is no longer an owner. It is a caller and a display.**
  - Forbidden writers: nothing except the service calls `TryDequeueCommand` or `BrokkrUnityCommandExecutor.Execute`. No second `BrokkrCultMeshMirror` instance may exist in the process. No asset-import or reload hook may start the service.
  - Shared paths: window buttons, `brokkr-command`, and future MCP-bridge calls all write `unity/commands/{id}`. The service drains all of them through one path.
  - Deletion line: the window's drain, the window's mirror and `AutoPollCommands` are deleted before the service is wired.
- **Verification:**
  - builds: on Yggdrasil (dotnet image, CultLib at `93fe1b9` or later), `dotnet build brokkr-command -p:CultLibRoot=...` plus a new `brokkr-contracts.Tests` (xunit, +1 test target). Justification: the ledger rule has no other defence.
  - tests, each pinning a behaviour:
    - `ExternallyWrittenCommandIsPendingAfterPull`: a second cache instance writes the intent, the ledger pulls, and the command is pending.
    - `CommandWithReceiptIsNeverPendingAgain`: this pins F6=A.
    - `TwoLedgersOverOneStoreExecuteOnce`: two processes run over one store, and exactly one receipt exists per id. This is the Unity double-drain scenario at the layer where the rule is decided.
    - `PendingOrderIsStoredAtThenKey`.
    Commit the §2 probe as this test project's scenario harness, because a harness that dies with the scratchpad defends nothing.
  - mutation: Stryker.NET, scoped to `BrokkrCommandLedger.cs`, on Yggdrasil.
  - negative: `rg -n 'EditorApplication.update' surfaces/unity` matches only `BrokkrEditorService.cs` and the window's display repaint, and the window's handler contains no `Execute`. `rg -n 'new BrokkrCultMeshMirror' surfaces/unity` returns one hit. `rg -n 'AssetPostprocessor|DidReloadScripts' surfaces/unity` returns nothing.
  - operator/Starfire:
    1. With the flag **off**, a CLI command times out and nothing mutates.
    2. With the flag on and the **window closed**, a command executes.
    3. With the window open, a command issued while it starts executes **once**: the Hierarchy shows a single object.
    4. Undo removes it.

### A2. Single-use command identity (F6=A)

- **Deletes first:** none in Unity. The dedup already treats ids as single-use. What changes is the contract.
- **Per-file changes:** `docs/provider-contract.md` states it: an intent id is minted once per act, a receipt answers exactly that id, and rewriting an id is a caller defect. `brokkr-command/Program.cs:118` already mints `Guid` ids unless `--command-id` is given; keep that.
- **Not in this cut:** the Rust sync's `stable_id` slots (X1).
- **Verification:** the test `RewrittenCommandIdIsNotReExecuted` pins the chosen semantics explicitly, so a later switch to F6=B has to break a named test.

### A3. `brokkr-command`: the full intent and a sane CultLib root

- **Deletes first:** `brokkr-command/Brokkr.Command.csproj:7` and `brokkr-contracts/Brokkr.Contracts.csproj:8`, the `CultLibRoot` default `..\..\CultLib-codex-cultmesh-reliability`, which does not exist. It becomes `..\..\CultLib`.
- **Keeps (from `9cc4bf3`):** `brokkr-command/` (Program.cs, 121 lines; csproj), `brokkr-contracts/` (csproj; compiles `Runtime/*.cs`), and `readHost` (`:10-35`).
- **Per-file changes:** `Program.cs:37-46,79-120`. Map every `BrokkrUnityCommand` field (`[Key(3)]`..`[Key(16)]`: `targetObjectId`, `name`, `componentType`, `propertyPath`, `assetPath`, `parentObjectId`, `localPosition`, `localEulerAngles`, `localScale`, plus the six already mapped) to `--kebab` options. The exit code stays derived from the receipt's `status` (`:73`), never from the write succeeding.
- **Authority map:**
  - Owner: none. `brokkr-command` is a caller.
  - Output: one intent per invocation, written through `CultCacheMessagePack` with `UseDirectoryStore=true`.
  - Forbidden writers: it never writes receipts, snapshots or the enable flag, and it never opens the store as single-file.
  - Deletion line: if it grows policy or a receipt ledger of its own, cut it back to a caller.
- **Verification:**
  - Yggdrasil builds.
  - The A1 harness drives every action name through the CLI against the probe editor, checking one receipt per id.
  - Starfire: the parked Cut 5 steps 2-7 (`docs/agent-access-cut.md:333-357`), using `brokkr-command` for `brokkr-ctl`.

### A4. Admission and the lifecycle actions

- **First:** Starfire measures parked Q3. With the service enabled and Unity unfocused, time the receipt for one command. If it arrives within the ~1 s pull interval, no keep-awake gets built.
- **Keeps (from `9cc4bf3`):** the executor's `refreshAssets`, `setEditorPlayState`, `setEditorPaused` and `captureEditorView` (`BrokkrUnityCommandExecutor.cs:30-33, 43-140`), and the play-state fields in `BrokkrHostSnapshot` (`[Key(14..17)]`).
- **Adds:**
  - `BrokkrCommandPolicy`, consulted by the service before `Execute`. It is a per-project action allowlist. By default it allows scene mutation and lifecycle actions, and denies the asset-creating actions (`createScriptableObject`, `createPrefabVariant`).
  - `captureEditorView` is confined to paths under the project root.
  - A denial yields `status=denied` with a reason.
  - `requestedBy` on the intent (next free key).
  - `saveScene`, only if parked Q4 = A, shipped denied.
- **Authority map:**
  - Owner: `BrokkrCommandPolicy` owns admission.
  - Forbidden writers: the executor never runs unadmitted, and the window's buttons go through the same policy. Operator and agent share one admission path.
- **Verification:**
  - negative: a `createScriptableObject` under the default policy produces `denied`, and no asset exists (checked through `AssetDatabase`, not the receipt).
  - negative: a `captureEditorView` with `outputPath=C:/Windows/x.png` or `../../x.png` produces `denied`, and no file exists.
  - negative: `rg -n 'Execute\(' surfaces/unity` shows the policy call on its only call site.
  - operator: entering and leaving play mode through the CLI survives the domain reload. The service restarts from `[InitializeOnLoad]`, and a command issued after the reload executes.

### A5. The Rust advertisement follows the landed actions

- `brokkr-daemon/src/main.rs`: take the donor's three `capabilities` rows (`editor.assets.refresh`, `editor.lifecycle.write`, `editor.view.capture`; donor diff at `:222-227`). Do **not** take the prefab `MirrorDocument` rows or their test asserts (parked under F3).
- Verification: `cargo test --workspace` on Yggdrasil. The existing advertisement test gains the three capabilities.

---

## 6. Follow-ups outside this adoption

- **X1. Unity sync from the Rust daemon is broken on both `main` and the donor.**
  - On `main`, external writes never reach the editor, because it watches without pulling.
  - Under A1, the daemon's single-file writes land on a directory-store manifest (`main.rs:1411-1418`; `cultcache-rs` has no directory store). Its `stable_id` slots also collide with single-use ids (F6).
  - The fix belongs to its owner: `cultcache-rs` grows the directory store (a CultLib foundation change, with C# as the parity reference), and sync mints per-pass ids.
  - It can wait: nothing runs `sync-loop` (there is no service or unit file), and the operator drives the editor by hand.
- **X2. Prefab CDN pipeline:** parked under F3. Taking it up needs a store both editors can open. That is a gap in `cultcache-py`, which has no directory store.
- **X3.** `.voidbot` `E:\` paths: VoidBot's owner decides.
- **X4.** CultLib's `mcp-bridge-campaign.md` asks "what a provider must publish before it is usable through the bridge, and whether Brokkr already publishes it". Under F4=A the answer is: the intent and receipt documents at a known store path, with no endpoint. Self should record that answer in the campaign doc if F1=B lands.

---

## 7. Subtraction ledger (estimate)

| Cut | Removed | Added | Targets and deps |
|---|---|---|---|
| M1 | 55 files under `Plugins/` plus `Plugins.meta` (3.47 MB tracked). The vendor script (52 lines). About 16 lines of `check.ps1`. | About 8 lines of JSON and PowerShell. | −0 targets. +1 UPM dependency declared. |
| M2 | About 20 lines of docs and a dead script branch. | About 12 lines. | none |
| A1 | Window drain, window mirror, `AutoPollCommands` (about 60 lines on `main`). The donor's two hooks are never landed (29 lines). | Service about 120 lines (from the donor's 144), ledger about 70 lines (moved), flag about 15 lines, tests about 150 lines. | **+1 test target** (`brokkr-contracts.Tests`) |
| A2 | none | About 10 lines of docs plus 1 test | none |
| A3 | 2 bogus defaults | About 60 lines of option mapping over the donor's 121 lines plus 2 csproj | **+2 .NET targets** (`Brokkr.Command`, `Brokkr.Contracts`) |
| A4 | none | Policy about 100 lines. Donor executor actions: 105 lines. Snapshot fields: 10 lines. | none |
| A5 | none | 3 rows | none |

- **Maintenance only (F1=A):** about −3.47 MB of binary and about −60 lines of text, with no target added. This is the big negative the adoption is for.
- **With agent access (F1=B):** still about −3.4 MB net in shipped bytes, plus about 700 lines of text and three .NET targets. Those buy the capability that nothing else provides.
- **Versus merging as-is (F1=C, F2=B):** that path is +3,168/−141 lines, +2 targets, +7.5 MB of DLL history, and a 1,658-line Python tool with a hand-rolled CultCache fallback.

The budget is pressure, not a metric.

**Build budget.**
- Rust: `brokkr-daemon` only, dev profile. 13.4 s on the Yggdrasil rust image; target Linux, build host Yggdrasil.
- .NET: `Brokkr.Command` (net10.0) and `Brokkr.Contracts` (netstandard2.1) compile CultLib's `GameCult.Caching` and `GameCult.Caching.MessagePack` from source. About 9 s on the Yggdrasil dotnet image. The test target adds `GameCult.Mesh` and `GameCult.Networking` for the scenario harness.
- The Unity compile runs only on Starfire, by the operator, one editor at a time.
- No workspace-wide build is activated.
