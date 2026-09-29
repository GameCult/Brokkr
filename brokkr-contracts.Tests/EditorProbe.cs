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
// execution, not Unity. It is also the drain's IBrokkrCommandStore, with knobs to make the store fail.
internal sealed class EditorProbe : IDisposable, IBrokkrCommandStore
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

    // The token the operator's enable left in EditorPrefs; null while the sink is off. A probe starts with the sink
    // enabled, as an editor whose operator enabled it earlier and whose store already carries the marker.
    internal string? SinkToken { get; private set; } = "probe-token";

    internal bool AgentCommandsEnabled => SinkToken != null;

    // Runs inside the "executor", after the intent is recorded.
    internal Action<BrokkrUnityCommand>? OnExecute { get; set; }

    // Makes a receipt put or a flush throw, as a full disk or a lease timeout would.
    internal Func<BrokkrUnityCommandReceipt, bool>? FailReceiptPut { get; set; }
    internal Func<bool>? FailFlush { get; set; }

    // Flushes the drain asked for; each is an fsync in the real store.
    internal int Flushes { get; private set; }

    private EditorProbe(CultMeshNode node)
    {
        this.node = node;
        ledger = new BrokkrCommandLedger(node.Cache);
    }

    // enabledInStore false is an editor whose EditorPrefs still hold a token, opening a store that never saw that
    // enable: a re-clone, or a copied .brokkr.
    internal static async Task<EditorProbe> StartAsync(string cachePath, bool enabledInStore = true)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(cachePath)!);
        var node = await CultMesh.CreateNodeAsync(cachePath, new CultMeshNodeOptions
        {
            StartServer = false,
            CacheOptions = new CultCacheOpenOptions { UseDirectoryStore = true },
            EnableDurableShardLogs = true,
            DatabaseOptions = new CultNetDatabaseOptions { RuntimeId = "brokkr-unity-editor" }
        });
        var probe = new EditorProbe(node);
        // A restart with the token persisted finds its marker; a first start is the operator's enable.
        if (enabledInStore && !probe.ledger.SinkAuthorized(probe.SinkToken))
            await NewDrain(probe).EnableAsync(probe.SinkToken!);
        return probe;
    }

    private static BrokkrCommandDrain NewDrain(EditorProbe probe) =>
        new(
            probe.ledger,
            probe.policy,
            command =>
            {
                probe.Executed.Add(command);
                probe.OnExecute?.Invoke(command);
                return new BrokkrUnityCommandReceipt
                {
                    commandId = command.commandId,
                    status = probe.StatusFor(command),
                    message = "probe",
                    observedAt = DateTime.UtcNow.ToString("O")
                };
            },
            probe);

    // The operator ticks the toggle off.
    internal void DisableSink() => SinkToken = null;

    // The operator ticks it on: a new token, every waiting intent expired, one flush. Returns how many expired.
    internal async Task<int> EnableSinkAsync()
    {
        await ledger.PullAsync();
        var token = Guid.NewGuid().ToString("N");
        var expired = await NewDrain(this).EnableAsync(token);
        SinkToken = token;
        return expired;
    }

    // Returns how many intents the drain answered (0 with the sink off).
    internal async Task<int> TickAsync()
    {
        await ledger.PullAsync();
        var handled = 0;
        if (SinkToken != null)
        {
            handled = await NewDrain(this).DrainAsync(SinkToken);
            if (handled == BrokkrCommandDrain.NotAuthorized)
            {
                SinkToken = null;
                handled = 0;
            }
        }

        await node.Database.PutAsync(
            new CultRecordKey("unity/host/current"),
            new BrokkrHostSnapshot
            {
                observedAt = DateTime.UtcNow.ToString("O"),
                projectPath = "probe",
                agentCommandsEnabled = AgentCommandsEnabled
            });
        await node.FlushAsync(soft: true);
        return handled;
    }

    public Task PutReceiptAsync(BrokkrUnityCommandReceipt receipt)
    {
        if (FailReceiptPut?.Invoke(receipt) == true)
            throw new IOException("receipt write failed");
        return node.Database.PutAsync(BrokkrCommandLedger.ReceiptKey(receipt.commandId), receipt);
    }

    public Task PutSinkEnabledAsync(BrokkrSinkEnabled marker) => node.Database.PutAsync(BrokkrCommandLedger.SinkKey, marker);

    public Task DeleteIntentAsync(string commandId) =>
        node.Database.DeleteAsync<BrokkrUnityCommand>(BrokkrCommandLedger.CommandKey(commandId));

    public Task DeleteReceiptAsync(string commandId) =>
        node.Database.DeleteAsync<BrokkrUnityCommandReceipt>(BrokkrCommandLedger.ReceiptKey(commandId));

    public Task FlushAsync()
    {
        if (FailFlush?.Invoke() == true)
            throw new IOException("flush failed");
        Flushes++;
        return node.FlushAsync(soft: true);
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

    // Many intents in one open and one flush, for the flood scenarios.
    internal async Task WriteCommandsAsync(IEnumerable<string> commandIds, string action = "refreshAssets")
    {
        using var writer = OpenCache();
        foreach (var commandId in commandIds)
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
