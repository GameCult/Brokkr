param(
    [string]$StatePath = ".\.voidbot\state\brokkr.cc",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$voidBotRoot = "E:\Projects\VoidBot"
$coreDistPath = Join-Path $voidBotRoot "packages\core\dist\index.js"
$identityPath = Join-Path $repoRoot ".voidbot\voice\identity.json"
$resolvedStatePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $repoRoot $StatePath))

if (!(Test-Path $coreDistPath)) {
    throw "Missing VoidBot built core at $coreDistPath. Build VoidBot before reading Persona state."
}

node -e @"
const core = require(process.argv[1]);
const fs = require('fs');
const identity = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const statePath = process.argv[3];
core.loadVoidSelfStateTypedDocuments({
  canonicalPath: statePath,
  identity: {
    agentId: identity.id,
    publicName: identity.displayName,
    publicDescription: identity.description
  }
}).then((state) => {
  if (process.argv[4] === '--json') {
    console.log(JSON.stringify(state, null, 2));
    return;
  }
  console.log(core.renderVoidSelfStateSummary(state));
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
"@ $coreDistPath $identityPath $resolvedStatePath $(if ($Json) { "--json" } else { "" })

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
