use anyhow::{Context, Result, anyhow};
use cultcache_rs::{CacheBackingStore, CultCacheEnvelope, SingleFileMessagePackBackingStore};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::thread;
use std::time::Duration;

const PROVIDER_SCHEMA: &str = "gamecult.brokkr.provider_advertisement.v0";
const PROVIDER_ID: &str = "brokkr.creative_tool_broker";
const CULTMESH_BASE_URI: &str = "cultmesh://brokkr";

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProviderAdvertisement {
    schema: &'static str,
    provider: ProviderIdentity,
    authority: Authority,
    transports: Vec<Transport>,
    tool_surfaces: Vec<ToolSurface>,
    mirror_documents: Vec<MirrorDocument>,
    sync_organ: SyncOrgan,
    realtime_routes: Vec<RealtimeRoute>,
    eve_surfaces: Vec<EveSurface>,
    command_policy: CommandPolicy,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProviderIdentity {
    id: &'static str,
    title: &'static str,
    description: &'static str,
    version: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct Authority {
    owner: &'static str,
    role: &'static str,
    state_owner: &'static str,
    presentation_owner: &'static str,
    discovery_owner: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct Transport {
    kind: &'static str,
    base_uri: &'static str,
    status: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ToolSurface {
    id: &'static str,
    title: &'static str,
    tool_kind: &'static str,
    adapter: &'static str,
    capabilities: Vec<&'static str>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct MirrorDocument {
    name: &'static str,
    schema: &'static str,
    owner: &'static str,
    record_hint: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SyncOrgan {
    id: &'static str,
    owner: &'static str,
    role: &'static str,
    documents: Vec<SyncDocument>,
    sync_var_kinds: Vec<&'static str>,
    policies: Vec<&'static str>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SyncDocument {
    name: &'static str,
    schema: &'static str,
    owner: &'static str,
    record_hint: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RealtimeRoute {
    id: &'static str,
    owner: &'static str,
    source: &'static str,
    sink: &'static str,
    schema: &'static str,
    transport: &'static str,
    direction: &'static str,
    notes: Vec<&'static str>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EveSurface {
    id: &'static str,
    title: &'static str,
    cult_mesh_uri: &'static str,
    schema: &'static str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CommandPolicy {
    mode: &'static str,
    envelope_schema: &'static str,
    receipt_schema: &'static str,
    notes: Vec<&'static str>,
}

fn main() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "provider".to_string());

    match command.as_str() {
        "provider" | "smoke" => print_provider(),
        "sync-contract" => print_sync_contract(),
        "sync-once" => sync_once(SyncArgs::parse(args.collect())?),
        "sync-loop" => sync_loop(SyncLoopArgs::parse(args.collect())?),
        _ => {
            eprintln!(
                "usage: brokkr-daemon [provider|smoke|sync-contract|sync-once --unity-cache PATH --blender-cache PATH [--dry-run]|sync-loop --unity-cache PATH --blender-cache PATH [--interval-ms N] [--max-passes N] [--dry-run]]"
            );
            std::process::exit(2);
        }
    }
}

fn print_provider() -> Result<()> {
    println!(
        "{}",
        serde_json::to_string_pretty(&build_provider_advertisement())?
    );
    Ok(())
}

fn print_sync_contract() -> Result<()> {
    println!("{}", serde_json::to_string_pretty(&build_sync_organ())?);
    Ok(())
}

fn sync_once(args: SyncArgs) -> Result<()> {
    let report = run_sync_once(&args)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn sync_loop(args: SyncLoopArgs) -> Result<()> {
    let mut pass_count = 0usize;
    loop {
        pass_count += 1;
        let report = run_sync_once(&args.sync)?;
        println!("{}", serde_json::to_string(&report)?);
        io::stdout().flush()?;

        if args
            .max_passes
            .is_some_and(|max_passes| pass_count >= max_passes)
        {
            return Ok(());
        }

        thread::sleep(Duration::from_millis(args.interval_ms));
    }
}

fn build_provider_advertisement() -> ProviderAdvertisement {
    ProviderAdvertisement {
        schema: PROVIDER_SCHEMA,
        provider: ProviderIdentity {
            id: PROVIDER_ID,
            title: "Brokkr",
            description: "Creative-tool broker exposing Unity and Blender editor state as a CultMesh mirror.",
            version: env!("CARGO_PKG_VERSION"),
        },
        authority: Authority {
            owner: PROVIDER_ID,
            role: "creative-tool Verse broker",
            state_owner: "CultCache documents mirrored through CultMesh",
            presentation_owner: "Eve/CultUI projections over mirrored editor state",
            discovery_owner: "Odin rendezvous over Brokkr provider advertisement",
        },
        transports: vec![Transport {
            kind: "cultmesh",
            base_uri: CULTMESH_BASE_URI,
            status: "primary",
        }],
        tool_surfaces: vec![
            ToolSurface {
                id: "brokkr.unity_editor",
                title: "Unity Editor",
                tool_kind: "unity-editor",
                adapter: "surfaces/unity/Packages/com.gamecult.brokkr",
                capabilities: vec![
                    "cultcache.mirror.publish",
                    "cultcache.intent.watch",
                    "host.status.read",
                    "scene.tree.read",
                    "component.state.read",
                    "selection.read",
                    "asset.catalog.read",
                    "asset.prefab.instantiate",
                    "asset.prefab.variant.create",
                    "gameobject.create",
                    "component.attach",
                    "component.property.write",
                    "sync.session.publish",
                    "sync.object.bind",
                    "sync.var.publish",
                    "sync.timeline.bind",
                    "command.receipt.publish",
                    "eve.gui.publish",
                    "eve.tui.publish",
                    "quest.input.consume",
                    "quest.pose.consume",
                    "quest.video_input.publish",
                ],
            },
            ToolSurface {
                id: "brokkr.blender_editor",
                title: "Blender Editor",
                tool_kind: "blender-editor",
                adapter: "surfaces/blender/brokkr_bridge",
                capabilities: vec![
                    "cultcache.mirror.publish",
                    "cultcache.intent.watch",
                    "host.status.read",
                    "scene.tree.read",
                    "object.graph.read",
                    "object.transform.write",
                    "object.create",
                    "object.delete",
                    "asset.catalog.read",
                    "material.catalog.read",
                    "material.assign",
                    "selection.read",
                    "selection.write",
                    "sync.session.publish",
                    "sync.object.bind",
                    "sync.var.publish",
                    "sync.timeline.bind",
                    "command.receipt.publish",
                    "eve.gui.publish",
                    "eve.tui.publish",
                ],
            },
        ],
        mirror_documents: vec![
            MirrorDocument {
                name: "Unity host snapshot",
                schema: "brokkr.unity.host_snapshot.v0",
                owner: "brokkr.unity_editor",
                record_hint: "unity/host/current",
            },
            MirrorDocument {
                name: "Unity command intent",
                schema: "brokkr.unity.command_intent.v0",
                owner: "Verse command clients",
                record_hint: "unity/commands/{commandId}",
            },
            MirrorDocument {
                name: "Unity command receipt",
                schema: "brokkr.unity.command_receipt.v0",
                owner: "brokkr.unity_editor",
                record_hint: "unity/receipts/{commandId}",
            },
            MirrorDocument {
                name: "Unity snapshot receipt",
                schema: "brokkr.unity.snapshot_receipt.v0",
                owner: "brokkr.unity_editor",
                record_hint: "unity/receipts/snapshots/{observedAt}",
            },
            MirrorDocument {
                name: "Unity Quest route",
                schema: "brokkr.unity.quest_route.v0",
                owner: "brokkr.unity_editor",
                record_hint: "unity/quest-routes/{routeId}",
            },
            MirrorDocument {
                name: "Unity warped video frame",
                schema: "brokkr.unity.warped_video_frame.v0",
                owner: "brokkr.unity_editor",
                record_hint: "unity/quest/video/{frameId}",
            },
            MirrorDocument {
                name: "Blender host snapshot",
                schema: "brokkr.blender.host_snapshot.v0",
                owner: "brokkr.blender_editor",
                record_hint: "blender/host/current",
            },
            MirrorDocument {
                name: "Blender command intent",
                schema: "brokkr.blender.command_intent.v0",
                owner: "Verse command clients",
                record_hint: "blender/commands/{commandId}",
            },
            MirrorDocument {
                name: "Blender command receipt",
                schema: "brokkr.blender.command_receipt.v0",
                owner: "brokkr.blender_editor",
                record_hint: "blender/receipts/{commandId}",
            },
            MirrorDocument {
                name: "Brokkr sync session",
                schema: "brokkr.sync.session.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/sessions/{sessionId}",
            },
            MirrorDocument {
                name: "Brokkr object binding",
                schema: "brokkr.sync.object_binding.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/bindings/objects/{bindingId}",
            },
            MirrorDocument {
                name: "Brokkr sync var",
                schema: "brokkr.sync.var.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/vars/{syncVarId}",
            },
            MirrorDocument {
                name: "Brokkr timeline binding",
                schema: "brokkr.sync.timeline_binding.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/bindings/timelines/{bindingId}",
            },
            MirrorDocument {
                name: "Brokkr sync receipt",
                schema: "brokkr.sync.receipt.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/receipts/{receiptId}",
            },
        ],
        sync_organ: build_sync_organ(),
        realtime_routes: build_unity_quest_routes(),
        eve_surfaces: vec![
            EveSurface {
                id: "brokkr.eve.unity_editor_gui.v0",
                title: "Unity Editor GUI",
                cult_mesh_uri: "cultmesh://brokkr/eve/unity/gui",
                schema: "gamecult.eve.surface.v1",
            },
            EveSurface {
                id: "brokkr.eve.unity_editor_tui.v0",
                title: "Unity Editor TUI",
                cult_mesh_uri: "cultmesh://brokkr/eve/unity/tui",
                schema: "gamecult.eve.surface.v1",
            },
        ],
        command_policy: CommandPolicy {
            mode: "intent-documents-with-host-receipts",
            envelope_schema: "brokkr.unity.command_intent.v0",
            receipt_schema: "brokkr.unity.command_receipt.v0",
            notes: vec![
                "Verse clients write command intent documents into CultCache through CultMesh.",
                "Unity watches command intents, performs editor mutations, and publishes receipts.",
                "CultCache is durable mirror truth; Brokkr provider output is discovery metadata.",
            ],
        },
    }
}

fn build_sync_organ() -> SyncOrgan {
    SyncOrgan {
        id: "brokkr.sync_organ.v0",
        owner: PROVIDER_ID,
        role: "receipt-driven Unity/Blender correspondence and sync policy",
        documents: vec![
            SyncDocument {
                name: "Sync session",
                schema: "brokkr.sync.session.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/sessions/{sessionId}",
            },
            SyncDocument {
                name: "Object binding",
                schema: "brokkr.sync.object_binding.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/bindings/objects/{bindingId}",
            },
            SyncDocument {
                name: "Sync variable",
                schema: "brokkr.sync.var.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/vars/{syncVarId}",
            },
            SyncDocument {
                name: "Timeline binding",
                schema: "brokkr.sync.timeline_binding.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/bindings/timelines/{bindingId}",
            },
            SyncDocument {
                name: "Sync receipt",
                schema: "brokkr.sync.receipt.v0",
                owner: PROVIDER_ID,
                record_hint: "sync/receipts/{receiptId}",
            },
        ],
        sync_var_kinds: vec![
            "transform",
            "active-state",
            "material",
            "component-property",
            "custom-property",
            "timeline-frame",
            "timeline-time",
            "animation-clip",
            "camera-lens",
            "cinemachine-virtual-camera",
        ],
        policies: vec![
            "Editor hosts own mutations; sync records only declare correspondence and desired lanes.",
            "Sync writes become real only after host command receipts confirm accepted mutations.",
            "Manual, UI-triggered, and programmatic sync actions use the same sync documents.",
            "Timeline bindings carry frame/time authority explicitly so Blender animation and Unity Cinemachine can share a clock without stealing editor ownership.",
        ],
    }
}

fn build_unity_quest_routes() -> Vec<RealtimeRoute> {
    vec![
        RealtimeRoute {
            id: "brokkr.unity.quest_input.consume.v0",
            owner: "Brokkr",
            source: "muninn:starfire:quest-input",
            sink: "brokkr.unity_editor:playmode-input",
            schema: "muninn.quest_input_frame.v1",
            transport: "cultmesh",
            direction: "muninn-to-unity",
            notes: vec![
                "Muninn owns Quest access and input publication.",
                "Brokkr lowers this stream into the Unity editor play-mode adapter.",
            ],
        },
        RealtimeRoute {
            id: "brokkr.unity.quest_pose.consume.v0",
            owner: "Brokkr",
            source: "muninn:starfire:quest-poses",
            sink: "brokkr.unity_editor:deru-rig",
            schema: "muninn.quest_pose_frame.v1",
            transport: "cultmesh",
            direction: "muninn-to-unity",
            notes: vec![
                "Mimir remains the sensor-fusion authority for synthesized poses.",
                "Brokkr applies the pose stream to the Unity scene representation.",
            ],
        },
        RealtimeRoute {
            id: "brokkr.unity.quest_video.publish.v0",
            owner: "Brokkr",
            source: "brokkr.unity_editor:playmode-warped-frame",
            sink: "muninn:starfire:quest-warped-video-input",
            schema: "brokkr.unity.warped_video_frame.v0",
            transport: "cultmesh",
            direction: "unity-to-muninn",
            notes: vec![
                "Unity owns render output and warp correction for this frame stream.",
                "Muninn owns Quest device access and final delivery to the attached headset.",
            ],
        },
    ]
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SyncArgs {
    unity_cache: PathBuf,
    blender_cache: PathBuf,
    dry_run: bool,
}

impl SyncArgs {
    fn parse(args: Vec<String>) -> Result<Self> {
        let parsed = ParsedSyncCli::parse(args, false)?;
        parsed.sync_args()
    }
}

#[derive(Debug, Clone)]
struct SyncLoopArgs {
    sync: SyncArgs,
    interval_ms: u64,
    max_passes: Option<usize>,
}

impl SyncLoopArgs {
    fn parse(args: Vec<String>) -> Result<Self> {
        let parsed = ParsedSyncCli::parse(args, true)?;
        let interval_ms = parsed.interval_ms.unwrap_or(500);
        let max_passes = parsed.max_passes;
        Ok(Self {
            sync: parsed.sync_args()?,
            interval_ms,
            max_passes,
        })
    }
}

#[derive(Debug, Clone)]
struct ParsedSyncCli {
    unity_cache: Option<PathBuf>,
    blender_cache: Option<PathBuf>,
    dry_run: bool,
    interval_ms: Option<u64>,
    max_passes: Option<usize>,
}

impl ParsedSyncCli {
    fn parse(args: Vec<String>, allow_loop_options: bool) -> Result<Self> {
        let mut parsed = Self {
            unity_cache: None,
            blender_cache: None,
            dry_run: false,
            interval_ms: None,
            max_passes: None,
        };
        let mut index = 0;

        while index < args.len() {
            match args[index].as_str() {
                "--unity-cache" => {
                    index += 1;
                    parsed.unity_cache = args.get(index).map(PathBuf::from);
                }
                "--blender-cache" => {
                    index += 1;
                    parsed.blender_cache = args.get(index).map(PathBuf::from);
                }
                "--dry-run" => parsed.dry_run = true,
                "--interval-ms" if allow_loop_options => {
                    index += 1;
                    let value = args
                        .get(index)
                        .ok_or_else(|| anyhow!("--interval-ms requires a value"))?;
                    parsed.interval_ms = Some(value.parse().with_context(|| {
                        format!("failed to parse --interval-ms value: {value}")
                    })?);
                }
                "--max-passes" if allow_loop_options => {
                    index += 1;
                    let value = args
                        .get(index)
                        .ok_or_else(|| anyhow!("--max-passes requires a value"))?;
                    parsed.max_passes =
                        Some(value.parse().with_context(|| {
                            format!("failed to parse --max-passes value: {value}")
                        })?);
                }
                other => return Err(anyhow!("unknown sync argument: {other}")),
            }
            index += 1;
        }

        Ok(parsed)
    }

    fn sync_args(self) -> Result<SyncArgs> {
        Ok(SyncArgs {
            unity_cache: self
                .unity_cache
                .ok_or_else(|| anyhow!("sync requires --unity-cache"))?,
            blender_cache: self
                .blender_cache
                .ok_or_else(|| anyhow!("sync requires --blender-cache"))?,
            dry_run: self.dry_run,
        })
    }
}

#[derive(Debug, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct SyncPassReport {
    schema: &'static str,
    status: &'static str,
    dry_run: bool,
    object_bindings_seen: usize,
    sync_vars_seen: usize,
    unity_commands_written: usize,
    blender_commands_written: usize,
    receipts_written: usize,
    messages: Vec<String>,
}

#[derive(Debug, Clone)]
struct CacheDocument {
    key: String,
    value: Value,
}

#[derive(Debug, Clone)]
struct ObjectBinding {
    binding_id: String,
    session_id: String,
    display_name: String,
    unity_object_id: String,
    unity_path: String,
    blender_object_name: String,
    enabled: bool,
    authority: String,
}

#[derive(Debug, Clone)]
struct SyncVarBinding {
    sync_var_id: String,
    session_id: String,
    binding_id: String,
    kind: String,
    unity_property_path: String,
    blender_property_path: String,
    authority: String,
    enabled: bool,
}

#[derive(Debug, Clone)]
struct TimelineBinding {
    binding_id: String,
    session_id: String,
    unity_timeline_object_id: String,
    unity_cinemachine_object_id: String,
    blender_scene_name: String,
    blender_action_name: String,
    clock_authority: String,
    frame_rate: f64,
    sync_frame: bool,
    sync_camera: bool,
    enabled: bool,
}

#[derive(Debug, Clone)]
struct UnityObject {
    object_id: String,
    name: String,
    path: String,
    active_self: bool,
    local_position: Vec<f64>,
    local_euler_angles: Vec<f64>,
    local_scale: Vec<f64>,
}

#[derive(Debug, Clone)]
struct BlenderObject {
    name: String,
    object_type: String,
    location: Vec<f64>,
    rotation_euler: Vec<f64>,
    scale: Vec<f64>,
    visible: bool,
    materials: Vec<String>,
    camera_field_of_view_degrees: Option<f64>,
}

#[derive(Debug, Clone)]
struct BlenderTimeline {
    scene_name: String,
    frame_current: i64,
    camera_name: String,
}

fn run_sync_once(args: &SyncArgs) -> Result<SyncPassReport> {
    let mut unity_store = MirrorStore::open(&args.unity_cache)?;
    let mut blender_store = MirrorStore::open(&args.blender_cache)?;
    let mut documents = Vec::new();
    documents.extend(unity_store.documents()?);
    documents.extend(blender_store.documents()?);

    let object_bindings: Vec<_> = documents
        .iter()
        .filter(|document| document.key.starts_with("sync/bindings/objects/"))
        .filter_map(|document| parse_object_binding(&document.value))
        .collect();
    let sync_vars: Vec<_> = documents
        .iter()
        .filter(|document| document.key.starts_with("sync/vars/"))
        .filter_map(|document| parse_sync_var(&document.value))
        .collect();
    let timeline_bindings: Vec<_> = documents
        .iter()
        .filter(|document| document.key.starts_with("sync/bindings/timelines/"))
        .filter_map(|document| parse_timeline_binding(&document.value))
        .collect();
    let unity_objects = parse_unity_objects(&documents);
    let blender_objects = parse_blender_objects(&documents);
    let blender_timeline = parse_blender_timeline(&documents);

    let mut report = SyncPassReport {
        schema: "brokkr.sync.pass_report.v0",
        status: "ok",
        dry_run: args.dry_run,
        object_bindings_seen: object_bindings.len(),
        sync_vars_seen: sync_vars.len(),
        unity_commands_written: 0,
        blender_commands_written: 0,
        receipts_written: 0,
        messages: Vec::new(),
    };

    let mut emitted_command_ids = BTreeSet::new();

    for binding in object_bindings.iter().filter(|binding| binding.enabled) {
        let binding_vars: Vec<_> = sync_vars
            .iter()
            .filter(|sync_var| {
                sync_var.binding_id == binding.binding_id
                    && sync_var.session_id == binding.session_id
                    && sync_var.enabled
            })
            .collect();

        for sync_var in binding_vars {
            let authority = if sync_var.authority.trim().is_empty() {
                binding.authority.as_str()
            } else {
                sync_var.authority.as_str()
            };
            match (authority, sync_var.kind.as_str()) {
                ("unity-to-blender", "transform") => {
                    let Some(source) = find_unity_object(&unity_objects, binding) else {
                        report.messages.push(format!(
                            "missing Unity object for binding {}",
                            binding.binding_id
                        ));
                        continue;
                    };
                    let command_id = stable_id([
                        "sync",
                        &binding.binding_id,
                        &sync_var.sync_var_id,
                        "unity-to-blender-transform",
                    ]);
                    if emitted_command_ids.insert(command_id.clone()) {
                        let command = json!({
                            "schema": "brokkr.blender.command_intent.v0",
                            "commandId": command_id,
                            "action": "setObjectTransform",
                            "targetObjectName": binding.blender_object_name,
                            "location": source.local_position,
                            "rotationEuler": source.local_euler_angles,
                            "scale": source.local_scale,
                        });
                        if !args.dry_run {
                            blender_store.put_json_document(
                                "brokkr.blender.command_intent.v0",
                                &format!(
                                    "blender/commands/{}",
                                    command["commandId"].as_str().unwrap_or("sync")
                                ),
                                &command,
                            )?;
                        }
                        report.blender_commands_written += 1;
                    }
                }
                ("unity-to-blender", "active-state") => {
                    let Some(source) = find_unity_object(&unity_objects, binding) else {
                        continue;
                    };
                    let command_id = stable_id([
                        "sync",
                        &binding.binding_id,
                        &sync_var.sync_var_id,
                        "unity-to-blender-active",
                    ]);
                    if emitted_command_ids.insert(command_id.clone()) {
                        let command = json!({
                            "schema": "brokkr.blender.command_intent.v0",
                            "commandId": command_id,
                            "action": "setObjectVisibility",
                            "targetObjectName": binding.blender_object_name,
                            "visible": source.active_self,
                        });
                        if !args.dry_run {
                            blender_store.put_json_document(
                                "brokkr.blender.command_intent.v0",
                                &format!(
                                    "blender/commands/{}",
                                    command["commandId"].as_str().unwrap_or("sync")
                                ),
                                &command,
                            )?;
                        }
                        report.blender_commands_written += 1;
                    }
                }
                ("blender-to-unity", "transform") => {
                    let Some(source) = blender_objects.get(&binding.blender_object_name) else {
                        report.messages.push(format!(
                            "missing Blender object {} for binding {}",
                            binding.blender_object_name, binding.binding_id
                        ));
                        continue;
                    };
                    let command_id = stable_id([
                        "sync",
                        &binding.binding_id,
                        &sync_var.sync_var_id,
                        "blender-to-unity-transform",
                    ]);
                    if emitted_command_ids.insert(command_id.clone()) {
                        let command = unity_transform_command(
                            &command_id,
                            &binding.unity_object_id,
                            &source.location,
                            &source.rotation_euler,
                            &source.scale,
                        );
                        if !args.dry_run {
                            unity_store.put_messagepack_document(
                                "brokkr.unity.command_intent.v0",
                                &format!("unity/commands/{command_id}"),
                                &command,
                            )?;
                        }
                        report.unity_commands_written += 1;
                    }
                }
                ("blender-to-unity", "material") => {
                    let Some(source) = blender_objects.get(&binding.blender_object_name) else {
                        continue;
                    };
                    let material = source.materials.first().cloned().unwrap_or_default();
                    report.messages.push(format!(
                        "material sync requested for {} -> {} (source name={}, visible={}, material={}) but Unity material import mapping is not implemented yet",
                        binding.blender_object_name,
                        binding.unity_object_id,
                        source.name,
                        source.visible,
                        material
                    ));
                }
                _ => report.messages.push(format!(
                    "unsupported sync var {} kind={} authority={} unityPath={} blenderPath={}",
                    sync_var.sync_var_id,
                    sync_var.kind,
                    authority,
                    sync_var.unity_property_path,
                    sync_var.blender_property_path
                )),
            }
        }
    }

    for timeline in timeline_bindings.iter().filter(|binding| binding.enabled) {
        if !timeline.clock_authority.eq_ignore_ascii_case("blender") {
            report.messages.push(format!(
                "timeline binding {} requested clockAuthority={} but Brokkr currently implements Blender-authored timeline sync",
                timeline.binding_id, timeline.clock_authority
            ));
            continue;
        }

        let timeline_source = blender_timeline
            .iter()
            .find(|candidate| candidate.scene_name == timeline.blender_scene_name)
            .or_else(|| blender_timeline.first());

        if timeline.sync_frame {
            let Some(source) = timeline_source else {
                report.messages.push(
                    "timeline sync requested but no Blender scene snapshot is available"
                        .to_string(),
                );
                continue;
            };
            let command_id = stable_id([
                "sync",
                &timeline.binding_id,
                &timeline.blender_action_name,
                "timeline-frame",
                &source.frame_current.to_string(),
            ]);
            let seconds = source.frame_current as f64 / timeline.frame_rate.max(0.001);
            let command = unity_property_command(
                &command_id,
                &timeline.unity_timeline_object_id,
                "",
                "m_Time",
                &format!("{seconds:.6}"),
            );
            if !args.dry_run {
                unity_store.put_messagepack_document(
                    "brokkr.unity.command_intent.v0",
                    &format!("unity/commands/{command_id}"),
                    &command,
                )?;
            }
            report.unity_commands_written += 1;
        }

        if timeline.sync_camera {
            let Some(source_scene) = timeline_source else {
                report.messages.push(
                    "Cinemachine sync requested but no Blender scene snapshot is available"
                        .to_string(),
                );
                continue;
            };
            let Some(source_camera) = blender_objects.get(&source_scene.camera_name) else {
                report.messages.push(format!(
                    "Cinemachine sync requested for binding {} but Blender scene {} has no camera object named {}",
                    timeline.binding_id, source_scene.scene_name, source_scene.camera_name
                ));
                continue;
            };

            let transform_command_id = stable_id([
                "sync",
                &timeline.binding_id,
                &timeline.blender_action_name,
                "cinemachine-camera-transform",
            ]);
            if emitted_command_ids.insert(transform_command_id.clone()) {
                let command = unity_transform_command(
                    &transform_command_id,
                    &timeline.unity_cinemachine_object_id,
                    &source_camera.location,
                    &source_camera.rotation_euler,
                    &source_camera.scale,
                );
                if !args.dry_run {
                    unity_store.put_messagepack_document(
                        "brokkr.unity.command_intent.v0",
                        &format!("unity/commands/{transform_command_id}"),
                        &command,
                    )?;
                }
                report.unity_commands_written += 1;
            }

            if let Some(field_of_view) = source_camera.camera_field_of_view_degrees {
                let lens_command_id = stable_id([
                    "sync",
                    &timeline.binding_id,
                    &timeline.blender_action_name,
                    "cinemachine-camera-fov",
                ]);
                if emitted_command_ids.insert(lens_command_id.clone()) {
                    let command = unity_property_command(
                        &lens_command_id,
                        &timeline.unity_cinemachine_object_id,
                        "Cinemachine.CinemachineVirtualCamera",
                        "m_Lens.FieldOfView",
                        &format!("{field_of_view:.6}"),
                    );
                    if !args.dry_run {
                        unity_store.put_messagepack_document(
                            "brokkr.unity.command_intent.v0",
                            &format!("unity/commands/{lens_command_id}"),
                            &command,
                        )?;
                    }
                    report.unity_commands_written += 1;
                }
            } else {
                report.messages.push(format!(
                    "Cinemachine sync requested for binding {} but Blender object {} is {} without camera FOV data",
                    timeline.binding_id, source_camera.name, source_camera.object_type
                ));
            }
        }
    }

    let receipt = json!({
        "schema": "brokkr.sync.receipt.v0",
        "receiptId": stable_id(["sync-receipt", &chrono_like_timestamp_id()]),
        "sessionId": object_bindings
            .first()
            .map(|binding| binding.session_id.as_str())
            .or_else(|| timeline_bindings.first().map(|binding| binding.session_id.as_str()))
            .unwrap_or("default"),
        "status": report.status,
        "message": format!(
            "wrote {} Unity command(s) and {} Blender command(s)",
            report.unity_commands_written, report.blender_commands_written
        ),
        "observedAt": chrono_like_now(),
    });
    if !args.dry_run {
        unity_store.put_json_document(
            "brokkr.sync.receipt.v0",
            &format!(
                "sync/receipts/{}",
                receipt["receiptId"].as_str().unwrap_or("sync-receipt")
            ),
            &receipt,
        )?;
    }
    report.receipts_written += 1;

    Ok(report)
}

struct MirrorStore {
    store: SingleFileMessagePackBackingStore,
}

impl MirrorStore {
    fn open(path: &Path) -> Result<Self> {
        Ok(Self {
            store: SingleFileMessagePackBackingStore::new(path),
        })
    }

    fn documents(&mut self) -> Result<Vec<CacheDocument>> {
        let mut documents = Vec::new();
        for envelope in self.store.pull_all()? {
            let value = decode_payload(&envelope).with_context(|| {
                format!("failed to decode {} at {}", envelope.r#type, envelope.key)
            })?;
            documents.push(CacheDocument {
                key: envelope.key,
                value,
            });
        }
        Ok(documents)
    }

    fn put_json_document(&mut self, schema: &str, key: &str, value: &Value) -> Result<()> {
        let payload = serde_json::to_vec(value)?;
        self.store.push(&CultCacheEnvelope {
            key: key.to_string(),
            r#type: schema.to_string(),
            payload,
            stored_at: chrono_like_now(),
            schema_id: Some(schema.to_string()),
        })
    }

    fn put_messagepack_document(&mut self, schema: &str, key: &str, value: &Value) -> Result<()> {
        let payload = rmp_serde::to_vec(value)?;
        self.store.push(&CultCacheEnvelope {
            key: key.to_string(),
            r#type: schema.to_string(),
            payload,
            stored_at: chrono_like_now(),
            schema_id: Some(schema.to_string()),
        })
    }
}

fn decode_payload(envelope: &CultCacheEnvelope) -> Result<Value> {
    serde_json::from_slice(&envelope.payload)
        .or_else(|_| rmp_serde::from_slice(&envelope.payload))
        .with_context(|| {
            format!(
                "payload is neither MessagePack nor JSON for {}",
                envelope.key
            )
        })
}

fn parse_object_binding(value: &Value) -> Option<ObjectBinding> {
    Some(ObjectBinding {
        binding_id: field_string(value, 1, "bindingId")?,
        session_id: field_string(value, 2, "sessionId").unwrap_or_else(|| "default".to_string()),
        display_name: field_string(value, 3, "displayName").unwrap_or_default(),
        unity_object_id: field_string(value, 4, "unityObjectId").unwrap_or_default(),
        unity_path: field_string(value, 5, "unityPath").unwrap_or_default(),
        blender_object_name: field_string(value, 6, "blenderObjectName").unwrap_or_default(),
        enabled: field_bool(value, 8, "enabled").unwrap_or(true),
        authority: field_string(value, 9, "authority")
            .unwrap_or_else(|| "unity-to-blender".to_string()),
    })
}

fn parse_sync_var(value: &Value) -> Option<SyncVarBinding> {
    Some(SyncVarBinding {
        sync_var_id: field_string(value, 1, "syncVarId")?,
        session_id: field_string(value, 2, "sessionId").unwrap_or_else(|| "default".to_string()),
        binding_id: field_string(value, 3, "bindingId")?,
        kind: field_string(value, 5, "kind")?,
        unity_property_path: field_string(value, 6, "unityPropertyPath").unwrap_or_default(),
        blender_property_path: field_string(value, 7, "blenderPropertyPath").unwrap_or_default(),
        authority: field_string(value, 8, "authority").unwrap_or_default(),
        enabled: field_bool(value, 9, "enabled").unwrap_or(true),
    })
}

fn parse_timeline_binding(value: &Value) -> Option<TimelineBinding> {
    Some(TimelineBinding {
        binding_id: field_string(value, 1, "bindingId")?,
        session_id: field_string(value, 2, "sessionId").unwrap_or_else(|| "default".to_string()),
        unity_timeline_object_id: field_string(value, 4, "unityTimelineObjectId")
            .unwrap_or_default(),
        unity_cinemachine_object_id: field_string(value, 5, "unityCinemachineObjectId")
            .unwrap_or_default(),
        blender_scene_name: field_string(value, 6, "blenderSceneName").unwrap_or_default(),
        blender_action_name: field_string(value, 7, "blenderActionName").unwrap_or_default(),
        clock_authority: field_string(value, 8, "clockAuthority")
            .unwrap_or_else(|| "blender".to_string()),
        frame_rate: field_f64(value, 9, "frameRate").unwrap_or(24.0),
        sync_frame: field_bool(value, 10, "syncFrame").unwrap_or(false),
        sync_camera: field_bool(value, 11, "syncCamera").unwrap_or(false),
        enabled: field_bool(value, 12, "enabled").unwrap_or(true),
    })
}

fn parse_unity_objects(documents: &[CacheDocument]) -> Vec<UnityObject> {
    let Some(snapshot) = documents
        .iter()
        .find(|document| document.key == "unity/host/current")
        .map(|document| &document.value)
    else {
        return Vec::new();
    };
    let Some(objects) = field_array(snapshot, 12, "sceneObjects") else {
        return Vec::new();
    };
    objects
        .iter()
        .filter_map(|value| {
            Some(UnityObject {
                object_id: field_string(value, 0, "objectId")?,
                name: field_string(value, 1, "name").unwrap_or_default(),
                path: field_string(value, 2, "path").unwrap_or_default(),
                active_self: field_bool(value, 4, "activeSelf").unwrap_or(true),
                local_position: field_vec3(value, 10, "localPosition").unwrap_or_default(),
                local_euler_angles: field_vec3(value, 11, "localEulerAngles").unwrap_or_default(),
                local_scale: field_vec3(value, 12, "localScale")
                    .unwrap_or_else(|| vec![1.0, 1.0, 1.0]),
            })
        })
        .collect()
}

fn parse_blender_objects(documents: &[CacheDocument]) -> BTreeMap<String, BlenderObject> {
    let Some(snapshot) = documents
        .iter()
        .find(|document| document.key == "blender/host/current")
        .map(|document| &document.value)
    else {
        return BTreeMap::new();
    };
    let Some(objects) = field_array(snapshot, 17, "objects") else {
        return BTreeMap::new();
    };
    objects
        .iter()
        .filter_map(|value| {
            let name = field_string(value, 0, "name")?;
            Some((
                name.clone(),
                BlenderObject {
                    name,
                    object_type: field_string(value, 1, "type").unwrap_or_default(),
                    location: field_vec3(value, 4, "location").unwrap_or_default(),
                    rotation_euler: field_vec3(value, 5, "rotationEuler").unwrap_or_default(),
                    scale: field_vec3(value, 6, "scale").unwrap_or_else(|| vec![1.0, 1.0, 1.0]),
                    visible: field_bool(value, 7, "visible").unwrap_or(true),
                    materials: field_array(value, 10, "materials")
                        .map(|items| {
                            items
                                .iter()
                                .filter_map(Value::as_str)
                                .map(str::to_string)
                                .collect()
                        })
                        .unwrap_or_default(),
                    camera_field_of_view_degrees: value
                        .get("camera")
                        .and_then(|camera| field_f64(camera, 1, "fieldOfViewDegrees")),
                },
            ))
        })
        .collect()
}

fn parse_blender_timeline(documents: &[CacheDocument]) -> Vec<BlenderTimeline> {
    let Some(snapshot) = documents
        .iter()
        .find(|document| document.key == "blender/host/current")
        .map(|document| &document.value)
    else {
        return Vec::new();
    };
    let Some(scenes) = field_array(snapshot, 16, "scenes") else {
        return Vec::new();
    };
    scenes
        .iter()
        .filter_map(|value| {
            Some(BlenderTimeline {
                scene_name: field_string(value, 0, "name")?,
                frame_current: field_i64(value, 1, "frameCurrent").unwrap_or(0),
                camera_name: field_string(value, 4, "cameraName").unwrap_or_default(),
            })
        })
        .collect()
}

fn find_unity_object<'a>(
    objects: &'a [UnityObject],
    binding: &ObjectBinding,
) -> Option<&'a UnityObject> {
    objects
        .iter()
        .find(|object| {
            !binding.unity_object_id.is_empty() && object.object_id == binding.unity_object_id
        })
        .or_else(|| {
            objects
                .iter()
                .find(|object| !binding.unity_path.is_empty() && object.path == binding.unity_path)
        })
        .or_else(|| {
            objects.iter().find(|object| {
                !binding.display_name.is_empty() && object.name == binding.display_name
            })
        })
}

fn unity_transform_command(
    command_id: &str,
    target_object_id: &str,
    location: &[f64],
    rotation: &[f64],
    scale: &[f64],
) -> Value {
    json!([
        "brokkr.unity.command_intent.v0",
        command_id,
        "setGameObjectTransform",
        target_object_id,
        "",
        "",
        "",
        "",
        "",
        "",
        vec3_csv(location),
        vec3_csv(rotation),
        vec3_csv(scale)
    ])
}

fn unity_property_command(
    command_id: &str,
    target_object_id: &str,
    component_type: &str,
    property_path: &str,
    value: &str,
) -> Value {
    json!([
        "brokkr.unity.command_intent.v0",
        command_id,
        "setComponentProperty",
        target_object_id,
        "",
        component_type,
        property_path,
        value,
        "",
        "",
        "",
        "",
        ""
    ])
}

fn field_string(value: &Value, slot: usize, name: &str) -> Option<String> {
    value
        .get(name)
        .and_then(Value::as_str)
        .or_else(|| value.as_array()?.get(slot)?.as_str())
        .map(str::to_string)
}

fn field_bool(value: &Value, slot: usize, name: &str) -> Option<bool> {
    value
        .get(name)
        .and_then(Value::as_bool)
        .or_else(|| value.as_array()?.get(slot)?.as_bool())
}

fn field_f64(value: &Value, slot: usize, name: &str) -> Option<f64> {
    value
        .get(name)
        .and_then(Value::as_f64)
        .or_else(|| value.as_array()?.get(slot)?.as_f64())
}

fn field_i64(value: &Value, slot: usize, name: &str) -> Option<i64> {
    value
        .get(name)
        .and_then(Value::as_i64)
        .or_else(|| value.as_array()?.get(slot)?.as_i64())
}

fn field_array<'a>(value: &'a Value, slot: usize, name: &str) -> Option<&'a Vec<Value>> {
    value
        .get(name)
        .and_then(Value::as_array)
        .or_else(|| value.as_array()?.get(slot)?.as_array())
}

fn field_vec3(value: &Value, slot: usize, name: &str) -> Option<Vec<f64>> {
    let raw = value.get(name).or_else(|| value.as_array()?.get(slot))?;
    if let Some(items) = raw.as_array() {
        return Some(items.iter().filter_map(Value::as_f64).take(3).collect());
    }
    raw.as_str().map(parse_vec3)
}

fn parse_vec3(value: &str) -> Vec<f64> {
    value
        .trim_matches(|candidate| candidate == '(' || candidate == ')')
        .split(',')
        .filter_map(|part| part.trim().parse::<f64>().ok())
        .take(3)
        .collect()
}

fn vec3_csv(values: &[f64]) -> String {
    let x = values.first().copied().unwrap_or(0.0);
    let y = values.get(1).copied().unwrap_or(0.0);
    let z = values.get(2).copied().unwrap_or(0.0);
    format!("{x},{y},{z}")
}

fn stable_id<const N: usize>(parts: [&str; N]) -> String {
    parts
        .iter()
        .map(|part| part.replace([' ', '/', '\\'], "_"))
        .collect::<Vec<_>>()
        .join(":")
}

fn chrono_like_now() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    format!("{}.{:09}Z", now.as_secs(), now.subsec_nanos())
}

fn chrono_like_timestamp_id() -> String {
    chrono_like_now().replace(['.', ':', 'Z'], "_")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn provider_advertises_muninn_owned_quest_routes_for_unity() {
        let provider = build_provider_advertisement();
        let unity = provider
            .tool_surfaces
            .iter()
            .find(|surface| surface.id == "brokkr.unity_editor")
            .expect("Unity surface should be advertised");
        let blender = provider
            .tool_surfaces
            .iter()
            .find(|surface| surface.id == "brokkr.blender_editor")
            .expect("Blender surface should be advertised");

        assert!(unity.capabilities.contains(&"quest.input.consume"));
        assert!(unity.capabilities.contains(&"quest.pose.consume"));
        assert!(unity.capabilities.contains(&"quest.video_input.publish"));
        assert!(!blender.capabilities.contains(&"quest.input.consume"));
        assert!(blender.capabilities.contains(&"object.graph.read"));
        assert!(blender.capabilities.contains(&"object.transform.write"));
        assert!(blender.capabilities.contains(&"material.assign"));

        let route_sources: Vec<_> = provider
            .realtime_routes
            .iter()
            .map(|route| (route.id, route.source, route.sink, route.transport))
            .collect();

        assert!(route_sources.contains(&(
            "brokkr.unity.quest_input.consume.v0",
            "muninn:starfire:quest-input",
            "brokkr.unity_editor:playmode-input",
            "cultmesh"
        )));
        assert!(route_sources.contains(&(
            "brokkr.unity.quest_pose.consume.v0",
            "muninn:starfire:quest-poses",
            "brokkr.unity_editor:deru-rig",
            "cultmesh"
        )));
        assert!(route_sources.contains(&(
            "brokkr.unity.quest_video.publish.v0",
            "brokkr.unity_editor:playmode-warped-frame",
            "muninn:starfire:quest-warped-video-input",
            "cultmesh"
        )));
    }

    #[test]
    fn provider_advertises_blender_mirror_documents() {
        let provider = build_provider_advertisement();
        let documents: Vec<_> = provider
            .mirror_documents
            .iter()
            .map(|document| (document.schema, document.owner, document.record_hint))
            .collect();

        assert!(documents.contains(&(
            "brokkr.blender.host_snapshot.v0",
            "brokkr.blender_editor",
            "blender/host/current"
        )));
        assert!(documents.contains(&(
            "brokkr.blender.command_intent.v0",
            "Verse command clients",
            "blender/commands/{commandId}"
        )));
        assert!(documents.contains(&(
            "brokkr.blender.command_receipt.v0",
            "brokkr.blender_editor",
            "blender/receipts/{commandId}"
        )));
    }

    #[test]
    fn provider_advertises_sync_organ_documents_and_timeline_vars() {
        let provider = build_provider_advertisement();
        let sync_documents: Vec<_> = provider
            .sync_organ
            .documents
            .iter()
            .map(|document| (document.schema, document.record_hint))
            .collect();
        let mirror_documents: Vec<_> = provider
            .mirror_documents
            .iter()
            .map(|document| (document.schema, document.owner))
            .collect();

        assert_eq!(provider.sync_organ.owner, PROVIDER_ID);
        assert!(sync_documents.contains(&("brokkr.sync.session.v0", "sync/sessions/{sessionId}")));
        assert!(sync_documents.contains(&(
            "brokkr.sync.object_binding.v0",
            "sync/bindings/objects/{bindingId}"
        )));
        assert!(sync_documents.contains(&("brokkr.sync.var.v0", "sync/vars/{syncVarId}")));
        assert!(sync_documents.contains(&(
            "brokkr.sync.timeline_binding.v0",
            "sync/bindings/timelines/{bindingId}"
        )));
        assert!(sync_documents.contains(&("brokkr.sync.receipt.v0", "sync/receipts/{receiptId}")));
        assert!(mirror_documents.contains(&("brokkr.sync.var.v0", PROVIDER_ID)));
        assert!(
            provider
                .sync_organ
                .sync_var_kinds
                .contains(&"timeline-frame")
        );
        assert!(
            provider
                .sync_organ
                .sync_var_kinds
                .contains(&"cinemachine-virtual-camera")
        );
    }

    #[test]
    fn sync_loop_args_parse_bounded_polling_options() -> Result<()> {
        let args = SyncLoopArgs::parse(vec![
            "--unity-cache".to_string(),
            "unity.ccmp".to_string(),
            "--blender-cache".to_string(),
            "blender.ccmp".to_string(),
            "--interval-ms".to_string(),
            "25".to_string(),
            "--max-passes".to_string(),
            "3".to_string(),
            "--dry-run".to_string(),
        ])?;

        assert_eq!(args.sync.unity_cache, PathBuf::from("unity.ccmp"));
        assert_eq!(args.sync.blender_cache, PathBuf::from("blender.ccmp"));
        assert!(args.sync.dry_run);
        assert_eq!(args.interval_ms, 25);
        assert_eq!(args.max_passes, Some(3));

        Ok(())
    }

    #[test]
    fn sync_loop_with_max_passes_runs_bounded_sync_pass() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let unity_path = temp.path().join("unity.ccmp");
        let blender_path = temp.path().join("blender.ccmp");
        seed_sync_stores(&unity_path, &blender_path, "unity-to-blender")?;

        sync_loop(SyncLoopArgs {
            sync: SyncArgs {
                unity_cache: unity_path,
                blender_cache: blender_path.clone(),
                dry_run: false,
            },
            interval_ms: 1,
            max_passes: Some(1),
        })?;

        let mut blender_store = MirrorStore::open(&blender_path)?;
        assert!(
            blender_store
                .documents()?
                .iter()
                .any(|document| document.key.starts_with("blender/commands/"))
        );

        Ok(())
    }

    #[test]
    fn sync_once_writes_unity_transform_to_blender_command() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let unity_path = temp.path().join("unity.ccmp");
        let blender_path = temp.path().join("blender.ccmp");
        seed_sync_stores(&unity_path, &blender_path, "unity-to-blender")?;
        assert_seed_contains_sync_docs(&unity_path)?;

        let report = run_sync_once(&SyncArgs {
            unity_cache: unity_path.clone(),
            blender_cache: blender_path.clone(),
            dry_run: false,
        })?;

        assert_eq!(report.blender_commands_written, 1, "{report:#?}");
        let mut blender_store = MirrorStore::open(&blender_path)?;
        let command = blender_store
            .documents()?
            .into_iter()
            .find(|document| document.key.starts_with("blender/commands/"))
            .expect("Brokkr should emit a Blender command");

        assert_eq!(command.value["action"], "setObjectTransform");
        assert_eq!(command.value["targetObjectName"], "Cube");
        assert_eq!(command.value["location"], json!([1.0, 2.0, 3.0]));
        assert_eq!(command.value["rotationEuler"], json!([4.0, 5.0, 6.0]));
        assert_eq!(command.value["scale"], json!([1.0, 1.0, 1.0]));

        Ok(())
    }

    #[test]
    fn sync_once_writes_blender_transform_to_unity_command() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let unity_path = temp.path().join("unity.ccmp");
        let blender_path = temp.path().join("blender.ccmp");
        seed_sync_stores(&unity_path, &blender_path, "blender-to-unity")?;
        assert_seed_contains_sync_docs(&unity_path)?;

        let report = run_sync_once(&SyncArgs {
            unity_cache: unity_path.clone(),
            blender_cache: blender_path,
            dry_run: false,
        })?;

        assert_eq!(report.unity_commands_written, 1, "{report:#?}");
        let mut unity_store = MirrorStore::open(&unity_path)?;
        let command = unity_store
            .documents()?
            .into_iter()
            .find(|document| document.key.starts_with("unity/commands/"))
            .expect("Brokkr should emit a Unity command");

        assert_eq!(
            command.value.as_array().and_then(|items| items.get(2)),
            Some(&json!("setGameObjectTransform"))
        );
        assert_eq!(
            command.value.as_array().and_then(|items| items.get(3)),
            Some(&json!("unity-cube"))
        );
        assert_eq!(
            command.value.as_array().and_then(|items| items.get(10)),
            Some(&json!("10,20,30"))
        );
        assert_eq!(
            command.value.as_array().and_then(|items| items.get(11)),
            Some(&json!("0.1,0.2,0.3"))
        );
        assert_eq!(
            command.value.as_array().and_then(|items| items.get(12)),
            Some(&json!("2,2,2"))
        );

        Ok(())
    }

    #[test]
    fn sync_once_writes_cinemachine_camera_commands_from_blender_scene_camera() -> Result<()> {
        let temp = tempfile::tempdir()?;
        let unity_path = temp.path().join("unity.ccmp");
        let blender_path = temp.path().join("blender.ccmp");
        seed_cinemachine_stores(&unity_path, &blender_path)?;

        let report = run_sync_once(&SyncArgs {
            unity_cache: unity_path.clone(),
            blender_cache: blender_path,
            dry_run: false,
        })?;

        assert_eq!(report.unity_commands_written, 2, "{report:#?}");
        let mut unity_store = MirrorStore::open(&unity_path)?;
        let commands: Vec<_> = unity_store
            .documents()?
            .into_iter()
            .filter(|document| document.key.starts_with("unity/commands/"))
            .map(|document| document.value)
            .collect();

        let transform = commands
            .iter()
            .find(|command| {
                command.as_array().and_then(|items| items.get(2))
                    == Some(&json!("setGameObjectTransform"))
            })
            .expect("Cinemachine camera sync should emit a transform command");
        assert_eq!(
            transform.as_array().and_then(|items| items.get(3)),
            Some(&json!("unity-vcam"))
        );
        assert_eq!(
            transform.as_array().and_then(|items| items.get(10)),
            Some(&json!("3,4,5"))
        );

        let field_of_view = commands
            .iter()
            .find(|command| {
                command.as_array().and_then(|items| items.get(6))
                    == Some(&json!("m_Lens.FieldOfView"))
            })
            .expect("Cinemachine camera sync should emit a lens FOV command");
        assert_eq!(
            field_of_view.as_array().and_then(|items| items.get(2)),
            Some(&json!("setComponentProperty"))
        );
        assert_eq!(
            field_of_view.as_array().and_then(|items| items.get(5)),
            Some(&json!("Cinemachine.CinemachineVirtualCamera"))
        );
        assert_eq!(
            field_of_view.as_array().and_then(|items| items.get(7)),
            Some(&json!("54.000000"))
        );

        Ok(())
    }

    fn seed_sync_stores(unity_path: &Path, blender_path: &Path, authority: &str) -> Result<()> {
        let mut unity_store = MirrorStore::open(unity_path)?;
        let mut blender_store = MirrorStore::open(blender_path)?;

        unity_store.put_json_document(
            "brokkr.unity.host_snapshot.v0",
            "unity/host/current",
            &json!({
                "sceneObjects": [{
                    "objectId": "unity-cube",
                    "name": "Cube",
                    "path": "/Cube",
                    "activeSelf": true,
                    "localPosition": [1.0, 2.0, 3.0],
                    "localEulerAngles": [4.0, 5.0, 6.0],
                    "localScale": [1.0, 1.0, 1.0]
                }]
            }),
        )?;
        unity_store.put_json_document(
            "brokkr.sync.object_binding.v0",
            "sync/bindings/objects/binding-cube",
            &json!({
                "schema": "brokkr.sync.object_binding.v0",
                "bindingId": "binding-cube",
                "sessionId": "session-main",
                "displayName": "Cube",
                "unityObjectId": "unity-cube",
                "unityPath": "/Cube",
                "blenderObjectName": "Cube",
                "enabled": true,
                "authority": authority
            }),
        )?;
        unity_store.put_json_document(
            "brokkr.sync.var.v0",
            "sync/vars/var-cube-transform",
            &json!({
                "schema": "brokkr.sync.var.v0",
                "syncVarId": "var-cube-transform",
                "sessionId": "session-main",
                "bindingId": "binding-cube",
                "displayName": "Transform",
                "kind": "transform",
                "unityPropertyPath": "Transform",
                "blenderPropertyPath": "location,rotationEuler,scale",
                "authority": authority,
                "enabled": true
            }),
        )?;

        blender_store.put_json_document(
            "brokkr.blender.host_snapshot.v0",
            "blender/host/current",
            &json!({
                "objects": [{
                    "name": "Cube",
                    "location": [10.0, 20.0, 30.0],
                    "rotationEuler": [0.1, 0.2, 0.3],
                    "scale": [2.0, 2.0, 2.0],
                    "visible": true,
                    "materials": ["Mat"]
                }],
                "scenes": [{
                    "name": "Scene",
                    "frameCurrent": 48
                }]
            }),
        )?;

        Ok(())
    }

    fn seed_cinemachine_stores(unity_path: &Path, blender_path: &Path) -> Result<()> {
        let mut unity_store = MirrorStore::open(unity_path)?;
        let mut blender_store = MirrorStore::open(blender_path)?;

        unity_store.put_json_document(
            "brokkr.sync.timeline_binding.v0",
            "sync/bindings/timelines/timeline-camera",
            &json!({
                "schema": "brokkr.sync.timeline_binding.v0",
                "bindingId": "timeline-camera",
                "sessionId": "session-main",
                "displayName": "Camera",
                "unityTimelineObjectId": "unity-director",
                "unityCinemachineObjectId": "unity-vcam",
                "blenderSceneName": "Scene",
                "blenderActionName": "CameraAction",
                "clockAuthority": "blender",
                "frameRate": 24.0,
                "syncFrame": false,
                "syncCamera": true,
                "enabled": true
            }),
        )?;
        blender_store.put_json_document(
            "brokkr.blender.host_snapshot.v0",
            "blender/host/current",
            &json!({
                "objects": [{
                    "name": "Camera",
                    "type": "CAMERA",
                    "location": [3.0, 4.0, 5.0],
                    "rotationEuler": [0.0, 0.5, 1.0],
                    "scale": [1.0, 1.0, 1.0],
                    "visible": true,
                    "materials": [],
                    "camera": {
                        "lensMillimeters": 35.0,
                        "fieldOfViewDegrees": 54.0,
                        "clipStart": 0.1,
                        "clipEnd": 1000.0,
                        "type": "PERSP"
                    }
                }],
                "scenes": [{
                    "name": "Scene",
                    "frameCurrent": 48,
                    "cameraName": "Camera"
                }]
            }),
        )?;

        Ok(())
    }

    fn assert_seed_contains_sync_docs(unity_path: &Path) -> Result<()> {
        let mut unity_store = MirrorStore::open(unity_path)?;
        let keys: Vec<_> = unity_store
            .documents()?
            .into_iter()
            .map(|document| document.key)
            .collect();
        assert!(
            keys.iter()
                .any(|key| key == "sync/bindings/objects/binding-cube"),
            "{keys:#?}"
        );
        assert!(
            keys.iter().any(|key| key == "sync/vars/var-cube-transform"),
            "{keys:#?}"
        );
        Ok(())
    }
}
