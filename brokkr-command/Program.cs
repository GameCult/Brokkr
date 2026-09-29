// brokkr-command: a caller. It writes one Unity command intent into the project's directory store and reads the
// receipt the editor service answers with. It never writes receipts, host snapshots or the agent-commands flag,
// and it never opens the store as a single file: the editor owns execution and its own state.
using System.Globalization;
using GameCult.Brokkr;
using GameCult.Caching;
using GameCult.Caching.MessagePack;

// Exit codes: 0 the receipt was accepted (or readHost / an unwaited write succeeded); 1 the receipt says the editor
// did not accept it (failed, denied, expired, interrupted); 2 anything else: bad usage, a timeout, an unreadable store.
try
{
    return await Cli.RunAsync(args);
}
catch (Exception error) when (error is ArgumentException or TimeoutException or InvalidOperationException)
{
    Console.Error.WriteLine(error.Message);
    return 2;
}
catch (Exception error)
{
    Console.Error.WriteLine($"brokkr-command failed: {error.GetType().Name}: {error.Message}");
    return 2;
}

internal static class Cli
{
    // Every writable field of brokkr.unity.command_intent.v0 except the schema tag, the id and the action, which
    // have their own options.
    private static readonly Dictionary<string, Action<BrokkrUnityCommand, string>> Fields =
        new(StringComparer.Ordinal)
        {
            ["--target-object-id"] = (command, value) => command.targetObjectId = value,
            ["--name"] = (command, value) => command.name = value,
            ["--component-type"] = (command, value) => command.componentType = value,
            ["--property-path"] = (command, value) => command.propertyPath = value,
            ["--value"] = (command, value) => command.value = value,
            ["--asset-path"] = (command, value) => command.assetPath = value,
            ["--parent-object-id"] = (command, value) => command.parentObjectId = value,
            ["--local-position"] = (command, value) => command.localPosition = value,
            ["--local-euler-angles"] = (command, value) => command.localEulerAngles = value,
            ["--local-scale"] = (command, value) => command.localScale = value,
            ["--view"] = (command, value) => command.viewKind = value,
            ["--output"] = (command, value) => command.outputPath = value,
            ["--width"] = (command, value) => command.width = Integer("--width", value),
            ["--height"] = (command, value) => command.height = Integer("--height", value),
            ["--requested-by"] = (command, value) => command.requestedBy = value
        };

    internal static async Task<int> RunAsync(string[] args)
    {
        var options = Parse(args);
        var cachePath = Path.GetFullPath(Required(options, "--unity-cache"));
        var action = Required(options, "--action");
        var readHost = string.Equals(action, "readHost", StringComparison.Ordinal);

        using var cache = await OpenAsync(cachePath, readHost);
        return readHost ? await ReadHostAsync(cache) : await WriteIntentAsync(cache, action, options);
    }

    // An empty file, a legacy single-file store or a damaged shard fails inside CultCache with whatever exception the
    // decoder throws; the caller gets one message that names the path.
    private static async Task<CultCache> OpenAsync(string cachePath, bool readOnly)
    {
        try
        {
            return await CultCacheMessagePack.OpenAsync(cachePath, new CultCacheOpenOptions
            {
                UseDirectoryStore = true,
                ReadOnly = readOnly
            });
        }
        catch (Exception error) when (error is not ArgumentException)
        {
            throw new InvalidOperationException(
                $"Brokkr store '{cachePath}' cannot be opened ({error.GetType().Name}: {error.Message}). An empty or legacy single-file store, or one another process holds, fails here; it must be a directory store.",
                error);
        }
    }

    private static async Task<int> ReadHostAsync(CultCache cache)
    {
        await cache.PullAllBackingStoresAsync();
        var host = ReadHostSnapshot(cache)
                   ?? throw new InvalidOperationException("Brokkr host snapshot 'unity/host/current' is unavailable.");
        Console.WriteLine($"project: {host.projectPath}");
        Console.WriteLine($"observed: {host.observedAt}");
        Console.WriteLine($"scene: {host.activeScenePath}");
        Console.WriteLine($"agent-commands: {(host.agentCommandsEnabled ? "on" : "off")}");
        Console.WriteLine($"state: playing={host.isPlaying} paused={host.isPaused} compiling={host.isCompiling} updating={host.isUpdating}");
        Console.WriteLine($"objects: {host.sceneObjects.Length}");
        foreach (var sceneObject in host.sceneObjects.OrderBy(item => item.path, StringComparer.Ordinal))
        {
            var components = string.Join(", ", sceneObject.components.Select(component => component.typeName));
            Console.WriteLine($"- {sceneObject.path} active={sceneObject.activeSelf} layer={sceneObject.layer} components=[{components}]");
            foreach (var component in sceneObject.components)
            foreach (var property in component.properties.Where(property =>
                         !property.path.StartsWith("m_", StringComparison.Ordinal) &&
                         !string.IsNullOrWhiteSpace(property.value)))
                Console.WriteLine($"  {component.typeName}.{property.path}={property.value}");
        }

        return 0;
    }

    private static async Task<int> WriteIntentAsync(CultCache cache, string action, Dictionary<string, string> options)
    {
        // A command id is single-use, so every invocation is a new act with a new id. --command-id exists for callers
        // that need to name their own; one that already has a receipt is refused, because that receipt answered an
        // earlier act and would be reported as the answer to this one.
        var named = options.TryGetValue("--command-id", out var commandId) && !string.IsNullOrWhiteSpace(commandId);
        if (named)
        {
            await cache.PullAllBackingStoresAsync();
            if (cache.TryGet(BrokkrCommandLedger.ReceiptKey(commandId!), out BrokkrUnityCommandReceipt? existing) && existing != null)
                throw new ArgumentException(
                    $"Command id '{commandId}' already has a receipt ({existing.status}). Command ids are single-use; omit --command-id to get a fresh one.");
        }

        var command = new BrokkrUnityCommand
        {
            commandId = named ? commandId! : Guid.NewGuid().ToString("N"),
            action = action
        };
        foreach (var (name, value) in options)
            if (Fields.TryGetValue(name, out var assign))
                assign(command, value);

        await cache.AddAsync(command, new CultRecordHandle<BrokkrUnityCommand>(BrokkrCommandLedger.CommandKey(command.commandId)));
        await cache.FlushAsync();

        var waitMilliseconds = options.TryGetValue("--wait-ms", out var wait) ? Integer("--wait-ms", wait) : 10000;
        if (waitMilliseconds <= 0)
        {
            Console.WriteLine(command.commandId);
            return 0;
        }

        var receiptKey = BrokkrCommandLedger.ReceiptKey(command.commandId);
        var deadline = DateTimeOffset.UtcNow.AddMilliseconds(waitMilliseconds);
        var started = false;
        while (DateTimeOffset.UtcNow < deadline)
        {
            await Task.Delay(100);
            await cache.PullAllBackingStoresAsync();
            if (!cache.TryGet(receiptKey, out BrokkrUnityCommandReceipt? receipt) || receipt == null)
                continue;

            // Attempted is the editor's marker that it has started; the verdict is still to come.
            if (string.Equals(receipt.status, BrokkrCommandDrain.AttemptedStatus, StringComparison.Ordinal))
            {
                started = true;
                continue;
            }

            Console.WriteLine($"{receipt.status}: {receipt.message}");
            if (!string.IsNullOrWhiteSpace(receipt.objectId))
                Console.WriteLine(receipt.objectId);
            // The exit code is the receipt's verdict, never the write's success.
            return string.Equals(receipt.status, "accepted", StringComparison.Ordinal) ? 0 : 1;
        }

        var host = ReadHostSnapshot(cache);
        var why = host is { agentCommandsEnabled: false }
            ? " The editor reports agent commands off; the operator enables them in the Brokkr window."
            : "";
        if (started)
            why = " The editor started this intent and has not recorded a result; it will not run it again.";
        throw new TimeoutException(
            $"Timed out waiting for Brokkr receipt '{receiptKey.Value}'; the intent stays written.{why}");
    }

    private static BrokkrHostSnapshot? ReadHostSnapshot(CultCache cache) =>
        cache.TryGet(new CultRecordKey("unity/host/current"), out BrokkrHostSnapshot? host) ? host : null;

    private static Dictionary<string, string> Parse(string[] args)
    {
        var values = new Dictionary<string, string>(StringComparer.Ordinal);
        for (var index = 0; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length || !args[index].StartsWith("--", StringComparison.Ordinal))
                throw new ArgumentException("Arguments must be --name value pairs.");
            var name = args[index];
            if (name is not ("--unity-cache" or "--action" or "--command-id" or "--wait-ms") && !Fields.ContainsKey(name))
                throw new ArgumentException($"Unknown option {name}.");
            values[name] = args[index + 1];
        }

        return values;
    }

    private static string Required(Dictionary<string, string> options, string name) =>
        options.TryGetValue(name, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value
            : throw new ArgumentException($"{name} is required.");

    private static int Integer(string name, string value) =>
        int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : throw new ArgumentException($"{name} must be an integer.");
}
