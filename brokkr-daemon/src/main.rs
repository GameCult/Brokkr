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
    let command = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "provider".to_string());

    match command.as_str() {
        "provider" => print_provider(),
        "smoke" => print_provider(),
        _ => {
            eprintln!("usage: brokkr-daemon [provider|smoke]");
            std::process::exit(2);
        }
    }
}

fn print_provider() -> Result<()> {
    let advertisement = build_provider_advertisement();
    println!("{}", serde_json::to_string_pretty(&advertisement)?);
    Ok(())
}

fn build_provider_advertisement() -> ProviderAdvertisement {
    ProviderAdvertisement {
        schema: PROVIDER_SCHEMA,
        provider: ProviderIdentity {
            id: PROVIDER_ID,
            title: "Brokkr",
            description: "GameCult creative-tool broker for Unity, Blender, and future editor runtimes.",
            version: env!("CARGO_PKG_VERSION"),
        },
        authority: Authority {
            owner: "Brokkr",
            role: "CultMesh broker for creative editor observations, command admission, receipts, and Eve/CultUI projection.",
            state_owner: "Brokkr typed CultCache witnesses; host editors own host-local scene and asset truth.",
            presentation_owner: "Eve/CultUI lowers Brokkr surfaces without owning editor truth.",
            discovery_owner: "Odin discovers Brokkr through CultMesh provider advertisements.",
        },
        transports: vec![Transport {
            kind: "cultmesh",
            base_uri: CULTMESH_BASE_URI,
            status: "scaffold",
        }],
        tool_surfaces: vec![
            ToolSurface {
                id: "brokkr.unity_editor",
                title: "Unity Editor",
                tool_kind: "unity-editor",
                adapter: "surfaces/unity/Packages/com.gamecult.brokkr",
                capabilities: shared_capabilities(),
            },
            ToolSurface {
                id: "brokkr.blender_editor",
                title: "Blender Editor",
                tool_kind: "blender-editor",
                adapter: "surfaces/blender/brokkr_bridge",
                capabilities: shared_capabilities(),
            },
        ],
        eve_surfaces: vec![
            EveSurface {
                id: "brokkr.eve.tool_broker.v0",
                title: "Creative Tool Broker",
                cult_mesh_uri: "cultmesh://brokkr/eve/tool-broker",
                schema: "gamecult.eve.surface.v1",
            },
            EveSurface {
                id: "brokkr.eve.command_receipts.v0",
                title: "Command Receipts",
                cult_mesh_uri: "cultmesh://brokkr/eve/command-receipts",
                schema: "gamecult.eve.surface.v1",
            },
        ],
        command_policy: CommandPolicy {
            mode: "policy-gated",
            envelope_schema: "gamecult.brokkr.command_request.v0",
            receipt_schema: "gamecult.brokkr.command_receipt.v0",
            notes: vec![
                "Plugins are adapters and do not own Verse provider truth.",
                "All host mutations must produce command receipts.",
                "Unity and Blender commands share one envelope shape.",
            ],
        },
    }
}

fn shared_capabilities() -> Vec<&'static str> {
    vec![
        "host.status.read",
        "scene.tree.read",
        "selection.read",
        "asset.catalog.read",
        "command.palette.read",
        "command.execute",
        "receipt.read",
    ]
}
