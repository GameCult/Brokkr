param(
    [Parameter(Mandatory=$true)]
    [string]$Summary,

    [string]$Claim,
    [string]$Question,
    [string]$Tension,
    [string]$ActionImplication,
    [string[]]$Tags = @("brokkr", "repo-persona"),
    [string]$Kind = "project_seam",
    [string]$TargetKind = "repo",
    [string]$TargetId = "Brokkr",
    [string]$TargetLabel = "Brokkr",
    [string]$AnchorRef = "repo:Brokkr",
    [string]$AnchorKind = "repo",
    [string]$AnchorSummary = "Brokkr repository Persona state",
    [string]$StatePath = ".\.voidbot\state\brokkr.cc"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Claim) -and [string]::IsNullOrWhiteSpace($Question)) {
    throw "Memory writes must include either -Claim or -Question."
}

if ([string]::IsNullOrWhiteSpace($Tension)) {
    throw "Memory writes must include -Tension so the memory preserves its counterweight."
}

if ([string]::IsNullOrWhiteSpace($ActionImplication)) {
    throw "Memory writes must include -ActionImplication so the memory can steer future work."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$voidBotRoot = "E:\Projects\VoidBot"
$coreDistPath = Join-Path $voidBotRoot "packages\core\dist\index.js"
$identityPath = Join-Path $repoRoot ".voidbot\voice\identity.json"
$resolvedStatePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $repoRoot $StatePath))

if (!(Test-Path $coreDistPath)) {
    throw "Missing VoidBot built core at $coreDistPath. Build VoidBot before mutating Persona state."
}

$now = (Get-Date).ToUniversalTime().ToString("o")
$memoryId = "brokkr-" + ([guid]::NewGuid().ToString())
$operation = @{
    operation = "record_short_term_memory"
    memory = @{
        memoryId = $memoryId
        kind = $Kind
        target = @{
            kind = $TargetKind
            id = $TargetId
            label = $TargetLabel
        }
        summary = $Summary
        createdAt = $now
        updatedAt = $now
        tags = $Tags
        anchorRefs = @(
            @{
                ref = $AnchorRef
                kind = $AnchorKind
                summary = $AnchorSummary
            }
        )
        evidenceRefs = @()
    }
}

foreach ($field in @("Claim", "Question", "Tension", "ActionImplication")) {
    $value = Get-Variable -Name $field -ValueOnly
    if (![string]::IsNullOrWhiteSpace($value)) {
        $operation.memory[$field.Substring(0, 1).ToLowerInvariant() + $field.Substring(1)] = $value
    }
}

$operationJson = $operation | ConvertTo-Json -Depth 12 -Compress
$operationJsonBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($operationJson))

node -e @"
const core = require(process.argv[1]);
const fs = require('fs');
const identity = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const statePath = process.argv[3];
const operation = JSON.parse(Buffer.from(process.argv[4], 'base64').toString('utf8'));

(async () => {
  await core.ensureVoidSelfStateIdentityProfile({
    canonicalPath: statePath,
    identity: {
      agentId: identity.id,
      publicName: identity.displayName,
      publicDescription: identity.description
    }
  });
  const result = await core.applyVoidSelfStateOperation({
    canonicalPath: statePath,
    identity: {
      agentId: identity.id,
      publicName: identity.displayName,
      publicDescription: identity.description
    }
  }, operation);
  console.log(JSON.stringify({ ok: true, memoryId: operation.memory.memoryId, result }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"@ $coreDistPath $identityPath $resolvedStatePath $operationJsonBase64

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
