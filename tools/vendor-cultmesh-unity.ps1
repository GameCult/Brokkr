$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$cultLibRoot = "E:\Projects\CultLib"
$pluginRoot = Join-Path $repoRoot "surfaces\unity\Packages\com.gamecult.brokkr\Plugins\CultMesh"
$staleUnityConflicts = @(
    "MessagePack.dll",
    "MessagePack.dll.meta",
    "System.Numerics.Vectors.dll",
    "System.Numerics.Vectors.dll.meta"
)

dotnet build (Join-Path $cultLibRoot "src\GameCult.Mesh\GameCult.Mesh.csproj") -c Debug
if ($LASTEXITCODE -ne 0) {
    throw "CultMesh build failed with exit code $LASTEXITCODE"
}

New-Item -ItemType Directory -Force -Path $pluginRoot | Out-Null

$sources = @(
    (Join-Path $cultLibRoot "bin\GameCult.Mesh\Debug\netstandard2.1\GameCult.Logging.dll"),
    (Join-Path $cultLibRoot "bin\GameCult.Mesh\Debug\netstandard2.1\GameCult.Caching.dll"),
    (Join-Path $cultLibRoot "bin\GameCult.Mesh\Debug\netstandard2.1\GameCult.Caching.MessagePack.dll"),
    (Join-Path $cultLibRoot "bin\GameCult.Mesh\Debug\netstandard2.1\GameCult.Networking.dll"),
    (Join-Path $cultLibRoot "bin\GameCult.Mesh\Debug\netstandard2.1\GameCult.Mesh.dll"),
    "$env:USERPROFILE\.nuget\packages\concurrenthashset\1.3.0\lib\netstandard2.0\ConcurrentCollections.dll",
    "$env:USERPROFILE\.nuget\packages\isopoh.cryptography.argon2\2.0.0\lib\netstandard2.0\Isopoh.Cryptography.Argon2.dll",
    "$env:USERPROFILE\.nuget\packages\isopoh.cryptography.blake2b\2.0.0\lib\netstandard2.0\Isopoh.Cryptography.Blake2b.dll",
    "$env:USERPROFILE\.nuget\packages\isopoh.cryptography.securearray\2.0.0\lib\netstandard2.0\Isopoh.Cryptography.SecureArray.dll",
    "$env:USERPROFILE\.nuget\packages\litenetlib\2.1.2\lib\netstandard2.1\LiteNetLib.dll",
    @{ Source = "$env:USERPROFILE\.nuget\packages\messagepack\3.1.7\lib\netstandard2.1\MessagePack.dll"; Target = "MessagePack.CultMesh.dll" },
    "$env:USERPROFILE\.nuget\packages\messagepack.annotations\3.1.7\lib\netstandard2.0\MessagePack.Annotations.dll",
    "$env:USERPROFILE\.nuget\packages\microsoft.bcl.asyncinterfaces\9.0.10\lib\netstandard2.1\Microsoft.Bcl.AsyncInterfaces.dll",
    "$env:USERPROFILE\.nuget\packages\microsoft.bcl.timeprovider\8.0.0\lib\netstandard2.0\Microsoft.Bcl.TimeProvider.dll",
    "$env:USERPROFILE\.nuget\packages\microsoft.net.stringtools\17.11.4\lib\netstandard2.0\Microsoft.NET.StringTools.dll",
    "$env:USERPROFILE\.nuget\packages\r3\1.3.0\lib\netstandard2.1\R3.dll",
    "$env:USERPROFILE\.nuget\packages\system.buffers\4.5.1\lib\netstandard2.0\System.Buffers.dll",
    "$env:USERPROFILE\.nuget\packages\system.collections.immutable\8.0.0\lib\netstandard2.0\System.Collections.Immutable.dll",
    "$env:USERPROFILE\.nuget\packages\system.componentmodel.annotations\5.0.0\lib\netstandard2.1\System.ComponentModel.Annotations.dll",
    "$env:USERPROFILE\.nuget\packages\system.io.pipelines\9.0.10\lib\netstandard2.0\System.IO.Pipelines.dll",
    "$env:USERPROFILE\.nuget\packages\system.memory\4.5.5\lib\netstandard2.0\System.Memory.dll",
    "$env:USERPROFILE\.nuget\packages\system.runtime.compilerservices.unsafe\6.0.0\lib\netstandard2.0\System.Runtime.CompilerServices.Unsafe.dll",
    "$env:USERPROFILE\.nuget\packages\system.text.encodings.web\9.0.10\lib\netstandard2.0\System.Text.Encodings.Web.dll",
    "$env:USERPROFILE\.nuget\packages\system.text.json\9.0.10\lib\netstandard2.0\System.Text.Json.dll",
    "$env:USERPROFILE\.nuget\packages\system.threading.channels\8.0.0\lib\netstandard2.1\System.Threading.Channels.dll",
    "$env:USERPROFILE\.nuget\packages\system.threading.tasks.extensions\4.5.4\lib\netstandard2.0\System.Threading.Tasks.Extensions.dll"
)

foreach ($staleFile in $staleUnityConflicts) {
    $stalePath = Join-Path $pluginRoot $staleFile
    if (Test-Path $stalePath) {
        Remove-Item -LiteralPath $stalePath -Force
    }
}

foreach ($source in $sources) {
    if ($source -is [System.Collections.IDictionary]) {
        $sourcePath = $source.Source
        $targetPath = Join-Path $pluginRoot $source.Target
    }
    else {
        $sourcePath = $source
        $targetPath = Join-Path $pluginRoot (Split-Path -Leaf $sourcePath)
    }

    if (!(Test-Path $sourcePath)) {
        throw "Missing CultMesh Unity dependency: $sourcePath"
    }

    Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
}

Write-Host "Vendored CultMesh Unity dependencies into $pluginRoot"
