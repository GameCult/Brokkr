using GameCult.Brokkr;
using GameCult.Caching;
using GameCult.Caching.MessagePack;
using GameCult.Mesh;
using GameCult.Networking;

namespace Brokkr.Contracts.Tests;

// The scenario harness: an editor without Unity. It opens the store exactly as BrokkrCultMeshMirror does (a CultMesh
// node with StartServer=false over a directory store and durable shard logs) and runs one service tick in the
// service order: pull, drain pending intents through the ledger, receipt, soft flush, host snapshot, soft flush.
// "Executing" an intent only records it, so the scenarios measure delivery and once-only execution, not Unity.
internal sealed class EditorProbe : IDisposable
{
    private readonly CultMeshNode node;
    private readonly BrokkrCommandLedger ledger;

    internal List<BrokkrUnityCommand> Executed { get; } = new();

    // What the "editor" answers with. Real Unity answers accepted or failed per the executor.
    internal Func<BrokkrUnityCommand, string> StatusFor { get; set; } = _ => "accepted";

    // What the host snapshot says about the sink; the real editor reports the operator's toggle.
    internal bool AgentCommandsEnabled { get; set; } = true;

    private EditorProbe(CultMeshNode node)
    {
        this.node = node;
        ledger = new BrokkrCommandLedger(node.Cache);
    }

    internal static async Task<EditorProbe> StartAsync(string cachePath)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(cachePath)!);
        var node = await CultMesh.CreateNodeAsync(cachePath, new CultMeshNodeOptions
        {
            StartServer = false,
            CacheOptions = new CultCacheOpenOptions { UseDirectoryStore = true },
            EnableDurableShardLogs = true,
            DatabaseOptions = new CultNetDatabaseOptions { RuntimeId = "brokkr-unity-editor" }
        });
        return new EditorProbe(node);
    }

    internal async Task TickAsync()
    {
        await ledger.PullAsync();
        while (ledger.TryNextPending(out var command))
        {
            Executed.Add(command);
            await node.Database.PutAsync(
                BrokkrCommandLedger.ReceiptKey(command.commandId),
                new BrokkrUnityCommandReceipt
                {
                    commandId = command.commandId,
                    status = StatusFor(command),
                    message = "probe",
                    observedAt = DateTime.UtcNow.ToString("O")
                });
            await node.FlushAsync(soft: true);
        }

        await node.Database.PutAsync(
            new CultRecordKey("unity/host/current"),
            new BrokkrHostSnapshot { observedAt = DateTime.UtcNow.ToString("O"), projectPath = "probe", agentCommandsEnabled = AgentCommandsEnabled });
        await node.FlushAsync(soft: true);
    }

    public void Dispose() => node.Dispose();
}

// A store on disk laid out the way a Unity project lays it out: <project>/.brokkr/unity-editor.ccmp.
internal sealed class ScratchProject : IDisposable
{
    internal string Root { get; } = Path.Combine(Path.GetTempPath(), "brokkr-tests-" + Guid.NewGuid().ToString("N"));

    internal string StorePath => Path.Combine(Root, ".brokkr", "unity-editor.ccmp");

    // What brokkr-command does: open the same directory store, write one intent, flush.
    internal async Task WriteCommandAsync(string commandId, string action = "refreshAssets")
    {
        using var writer = OpenCache();
        await writer.AddAsync(
            new BrokkrUnityCommand { commandId = commandId, action = action },
            new CultRecordHandle<BrokkrUnityCommand>(BrokkrCommandLedger.CommandKey(commandId)));
        await writer.FlushAsync();
    }

    internal CultCache OpenCache()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(StorePath)!);
        return CultCacheMessagePack.Create(StorePath, new CultCacheOpenOptions { UseDirectoryStore = true });
    }

    public void Dispose()
    {
        try { Directory.Delete(Root, recursive: true); } catch (IOException) { }
    }
}
