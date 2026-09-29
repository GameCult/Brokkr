using GameCult.Brokkr;
using GameCult.Caching;
using GameCult.Caching.MessagePack;
using GameCult.Mesh;
using GameCult.Networking;

namespace Brokkr.Contracts.Tests;

// The scenario harness: an editor without Unity. It opens the store exactly as BrokkrCultMeshMirror does (a CultMesh
// node with StartServer=false over a directory store and durable shard logs) and runs one service tick in the
// service order: pull, drain pending intents through BrokkrCommandDrain (the same class the service uses), host
// snapshot, soft flush. "Executing" an intent only records it, so the scenarios measure delivery and once-only
// execution, not Unity.
internal sealed class EditorProbe : IDisposable
{
    private readonly CultMeshNode node;
    private readonly BrokkrCommandLedger ledger;
    private readonly BrokkrCommandPolicy policy = new("probe", BrokkrCommandPolicy.DefaultAllowedActions.Concat(new[]
    {
        "createPrefabVariant", "createScriptableObject"
    }));

    internal List<BrokkrUnityCommand> Executed { get; } = new();

    // What the "editor" answers with. Real Unity answers accepted or failed per the executor.
    internal Func<BrokkrUnityCommand, string> StatusFor { get; set; } = _ => "accepted";

    // What the host snapshot says about the sink; the real editor reports the operator's toggle.
    internal bool AgentCommandsEnabled { get; set; } = true;

    // When the operator last enabled the sink; intents stored earlier expire.
    internal DateTimeOffset EnabledAt { get; set; } = DateTimeOffset.MinValue;

    // Runs inside the "executor", after the intent is recorded.
    internal Action<BrokkrUnityCommand>? OnExecute { get; set; }

    // Makes a receipt write throw, as a full disk or a lease timeout would.
    internal Func<BrokkrUnityCommandReceipt, bool>? FailReceiptWrite { get; set; }

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

    // Returns how many intents the drain answered.
    internal async Task<int> TickAsync()
    {
        var handled = 0;
        if (AgentCommandsEnabled)
        {
            await ledger.PullAsync();
            var drain = new BrokkrCommandDrain(
                ledger,
                policy,
                command =>
                {
                    Executed.Add(command);
                    OnExecute?.Invoke(command);
                    return new BrokkrUnityCommandReceipt
                    {
                        commandId = command.commandId,
                        status = StatusFor(command),
                        message = "probe",
                        observedAt = DateTime.UtcNow.ToString("O")
                    };
                },
                async receipt =>
                {
                    if (FailReceiptWrite?.Invoke(receipt) == true)
                        throw new IOException("receipt write failed");
                    await node.Database.PutAsync(BrokkrCommandLedger.ReceiptKey(receipt.commandId), receipt);
                    await node.FlushAsync(soft: true);
                });
            handled = await drain.DrainAsync(EnabledAt);
        }

        await node.Database.PutAsync(
            new CultRecordKey("unity/host/current"),
            new BrokkrHostSnapshot
            {
                observedAt = DateTime.UtcNow.ToString("O"),
                projectPath = "probe",
                agentCommandsEnabled = AgentCommandsEnabled,
                agentCommandsEnabledAt = AgentCommandsEnabled ? EnabledAt.ToString("O") : ""
            });
        await node.FlushAsync(soft: true);
        return handled;
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
