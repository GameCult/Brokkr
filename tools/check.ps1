$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    cargo fmt --check
    cargo test --workspace
    cargo run -p brokkr-daemon -- provider | Out-Null
}
finally {
    Pop-Location
}

