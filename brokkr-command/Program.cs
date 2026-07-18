using GameCult.Brokkr;
using GameCult.Caching;
using GameCult.Caching.MessagePack;

var options = Options.Parse(args);
using var cache = await CultCacheMessagePack.OpenAsync(options.CachePath, new CultCacheOpenOptions
{
    UseDirectoryStore = true
});
if (string.Equals(options.Action, "readHost", StringComparison.Ordinal))
{
    await cache.PullAllBackingStoresAsync();
    var hostKey = new CultRecordKey("unity/host/current");
    if (!cache.TryGet(hostKey, out BrokkrHostSnapshot? host) || host == null)
    {
        throw new InvalidOperationException($"Brokkr host snapshot '{hostKey.Value}' is unavailable.");
    }

    Console.WriteLine($"project: {host.projectPath}");
    Console.WriteLine($"observed: {host.observedAt}");
    Console.WriteLine($"scene: {host.activeScenePath}");
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
    return;
}

var command = new BrokkrUnityCommand
{
    commandId = options.CommandId,
    action = options.Action,
    value = options.Value,
    viewKind = options.ViewKind,
    outputPath = options.OutputPath,
    width = options.Width,
    height = options.Height
};
var commandKey = new CultRecordKey($"unity/commands/{command.commandId}");
await cache.AddAsync(command, new CultRecordHandle<BrokkrUnityCommand>(commandKey));
await cache.FlushAsync();

if (options.WaitMilliseconds <= 0)
{
    Console.WriteLine(command.commandId);
    return;
}

var receiptKey = new CultRecordKey($"unity/receipts/{command.commandId}");
var deadline = DateTimeOffset.UtcNow.AddMilliseconds(options.WaitMilliseconds);
while (DateTimeOffset.UtcNow < deadline)
{
    await Task.Delay(100);
    await cache.PullAllBackingStoresAsync();
    if (!cache.TryGet(receiptKey, out BrokkrUnityCommandReceipt? receipt) || receipt == null)
    {
        continue;
    }

    Console.WriteLine($"{receipt.status}: {receipt.message}");
    if (!string.IsNullOrWhiteSpace(receipt.objectId))
    {
        Console.WriteLine(receipt.objectId);
    }
    Environment.ExitCode = string.Equals(receipt.status, "accepted", StringComparison.Ordinal) ? 0 : 1;
    return;
}

throw new TimeoutException($"Timed out waiting for Brokkr receipt '{receiptKey.Value}'.");

internal sealed record Options(
    string CachePath,
    string Action,
    string Value,
    string ViewKind,
    string OutputPath,
    int Width,
    int Height,
    string CommandId,
    int WaitMilliseconds)
{
    internal static Options Parse(string[] args)
    {
        var values = new Dictionary<string, string>(StringComparer.Ordinal);
        for (var index = 0; index < args.Length; index += 2)
        {
            if (index + 1 >= args.Length || !args[index].StartsWith("--", StringComparison.Ordinal))
            {
                throw new ArgumentException("Arguments must be --name value pairs.");
            }
            values[args[index]] = args[index + 1];
        }

        string Required(string name) => values.TryGetValue(name, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value
            : throw new ArgumentException($"{name} is required.");
        string Optional(string name) => values.TryGetValue(name, out var value) ? value : "";
        int Integer(string name, int fallback) => values.TryGetValue(name, out var value)
            ? int.Parse(value, System.Globalization.CultureInfo.InvariantCulture)
            : fallback;

        return new Options(
            Path.GetFullPath(Required("--unity-cache")),
            Required("--action"),
            Optional("--value"),
            Optional("--view"),
            Optional("--output"),
            Integer("--width", 0),
            Integer("--height", 0),
            values.TryGetValue("--command-id", out var commandId) ? commandId : Guid.NewGuid().ToString("N"),
            Integer("--wait-ms", 10000));
    }
}
