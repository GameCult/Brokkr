use anyhow::Result;
use serde::Serialize;

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
        _ => {
            eprintln!("usage: brokkr-daemon [provider|smoke]");
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
                adapter: "surfaces/blender/brokkr_blender",
                capabilities: vec![
                    "cultcache.mirror.publish",
                    "cultcache.intent.watch",
                    "host.status.read",
                    "scene.tree.read",
                    "asset.catalog.read",
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
        ],
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
}
