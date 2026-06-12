use anyhow::{Context, Result, bail};
use serde::{Deserialize, Serialize};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const PROVIDER_SCHEMA: &str = "gamecult.brokkr.provider_advertisement.v0";
const PROVIDER_ID: &str = "brokkr.creative_tool_broker";
const CULTMESH_BASE_URI: &str = "cultmesh://brokkr";
const DEFAULT_BIND: &str = "127.0.0.1:8798";

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

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ToolHostSnapshot {
    schema: String,
    provider_id: String,
    tool_kind: String,
    project_path: String,
    observed_at: String,
    unity_version: Option<String>,
    product_name: Option<String>,
    active_scene_path: Option<String>,
    open_scene_count: Option<u32>,
    selected_object_names: Vec<String>,
    asset_count: Option<u32>,
    capabilities: Vec<String>,
}

#[derive(Default)]
struct BrokerState {
    unity_snapshot: Option<ToolHostSnapshot>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct HealthResponse<'a> {
    ok: bool,
    provider_id: &'a str,
    version: &'a str,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct HostSnapshotsResponse {
    unity: Option<ToolHostSnapshot>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SnapshotReceipt<'a> {
    schema: &'a str,
    provider_id: &'a str,
    tool_kind: &'a str,
    accepted_at: String,
    status: &'a str,
}

fn main() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "provider".to_string());

    match command.as_str() {
        "provider" => print_provider(),
        "smoke" => print_provider(),
        "serve" => {
            let bind = match args.next().as_deref() {
                Some("--bind") => args.next().unwrap_or_else(|| DEFAULT_BIND.to_string()),
                Some(value) => value.to_string(),
                None => DEFAULT_BIND.to_string(),
            };
            serve(&bind)
        }
        _ => {
            eprintln!("usage: brokkr-daemon [provider|smoke|serve [--bind] [addr]]");
            std::process::exit(2);
        }
    }
}

fn print_provider() -> Result<()> {
    let advertisement = build_provider_advertisement();
    println!("{}", serde_json::to_string_pretty(&advertisement)?);
    Ok(())
}

fn serve(bind: &str) -> Result<()> {
    let listener =
        TcpListener::bind(bind).with_context(|| format!("failed to bind Brokkr on {bind}"))?;
    let state = Arc::new(Mutex::new(BrokerState::default()));
    eprintln!("Brokkr listening on http://{bind}");

    for stream in listener.incoming() {
        let stream = stream.context("failed to accept connection")?;
        let state = Arc::clone(&state);
        if let Err(error) = handle_connection(stream, state) {
            eprintln!("request failed: {error:#}");
        }
    }

    Ok(())
}

fn handle_connection(mut stream: TcpStream, state: Arc<Mutex<BrokerState>>) -> Result<()> {
    stream.set_read_timeout(Some(Duration::from_secs(5)))?;
    let request = read_http_request(&mut stream)?;

    let response = match (request.method.as_str(), request.path.as_str()) {
        ("GET", "/health") => json_response(
            200,
            &HealthResponse {
                ok: true,
                provider_id: PROVIDER_ID,
                version: env!("CARGO_PKG_VERSION"),
            },
        )?,
        ("GET", "/provider") => json_response(200, &build_provider_advertisement())?,
        ("GET", "/hosts") => {
            let state = state.lock().expect("broker state poisoned");
            json_response(
                200,
                &HostSnapshotsResponse {
                    unity: state.unity_snapshot.clone(),
                },
            )?
        }
        ("POST", "/hosts/unity/snapshot") => {
            let snapshot: ToolHostSnapshot = serde_json::from_slice(&request.body)
                .context("invalid Unity host snapshot JSON")?;
            validate_unity_snapshot(&snapshot)?;
            let receipt = SnapshotReceipt {
                schema: "gamecult.brokkr.snapshot_receipt.v0",
                provider_id: "brokkr.unity_editor",
                tool_kind: "unity-editor",
                accepted_at: unix_millis_timestamp(),
                status: "accepted",
            };
            state.lock().expect("broker state poisoned").unity_snapshot = Some(snapshot);
            json_response(202, &receipt)?
        }
        _ => text_response(404, "not found"),
    };

    stream.write_all(response.as_bytes())?;
    Ok(())
}

fn validate_unity_snapshot(snapshot: &ToolHostSnapshot) -> Result<()> {
    if snapshot.schema != "gamecult.brokkr.tool_host_snapshot.v0" {
        bail!("unexpected snapshot schema: {}", snapshot.schema);
    }
    if snapshot.provider_id != "brokkr.unity_editor" {
        bail!("unexpected provider id: {}", snapshot.provider_id);
    }
    if snapshot.tool_kind != "unity-editor" {
        bail!("unexpected tool kind: {}", snapshot.tool_kind);
    }
    Ok(())
}

struct HttpRequest {
    method: String,
    path: String,
    body: Vec<u8>,
}

fn read_http_request(stream: &mut TcpStream) -> Result<HttpRequest> {
    let mut buffer = Vec::new();
    let mut chunk = [0_u8; 4096];
    let header_end;

    loop {
        let bytes_read = stream.read(&mut chunk)?;
        if bytes_read == 0 {
            bail!("connection closed before headers");
        }
        buffer.extend_from_slice(&chunk[..bytes_read]);
        if let Some(index) = find_header_end(&buffer) {
            header_end = index;
            break;
        }
        if buffer.len() > 64 * 1024 {
            bail!("request headers too large");
        }
    }

    let header_text = std::str::from_utf8(&buffer[..header_end]).context("headers not utf-8")?;
    let mut lines = header_text.lines();
    let request_line = lines.next().context("missing request line")?;
    let mut parts = request_line.split_whitespace();
    let method = parts.next().context("missing method")?.to_string();
    let path = parts.next().context("missing path")?.to_string();

    let mut content_length = 0_usize;
    for line in lines {
        if let Some(value) = line.strip_prefix("Content-Length:") {
            content_length = value.trim().parse().context("bad Content-Length")?;
        } else if let Some(value) = line.strip_prefix("content-length:") {
            content_length = value.trim().parse().context("bad Content-Length")?;
        }
    }

    let body_start = header_end + 4;
    while buffer.len() < body_start + content_length {
        let bytes_read = stream.read(&mut chunk)?;
        if bytes_read == 0 {
            bail!("connection closed before body");
        }
        buffer.extend_from_slice(&chunk[..bytes_read]);
    }

    Ok(HttpRequest {
        method,
        path,
        body: buffer[body_start..body_start + content_length].to_vec(),
    })
}

fn find_header_end(buffer: &[u8]) -> Option<usize> {
    buffer.windows(4).position(|window| window == b"\r\n\r\n")
}

fn json_response<T: Serialize>(status: u16, value: &T) -> Result<String> {
    let body = serde_json::to_string_pretty(value)?;
    Ok(http_response(status, "application/json", &body))
}

fn text_response(status: u16, body: &str) -> String {
    http_response(status, "text/plain; charset=utf-8", body)
}

fn http_response(status: u16, content_type: &str, body: &str) -> String {
    let reason = match status {
        200 => "OK",
        202 => "Accepted",
        404 => "Not Found",
        _ => "OK",
    };
    format!(
        "HTTP/1.1 {status} {reason}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    )
}

fn unix_millis_timestamp() -> String {
    let millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    format!("unix-ms:{millis}")
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
        transports: vec![
            Transport {
                kind: "cultmesh",
                base_uri: CULTMESH_BASE_URI,
                status: "scaffold",
            },
            Transport {
                kind: "http-local",
                base_uri: "http://127.0.0.1:8798",
                status: "active-local-adapter",
            },
        ],
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
