using System.Diagnostics;
using GameCult.Brokkr;
using GameCult.Caching;

namespace Brokkr.Contracts.Tests;

// brokkr-command as a process, against the real directory store and the editor probe.
public sealed class BrokkrCommandCliTests
{
    private static readonly string CliDll = Path.Combine(AppContext.BaseDirectory, "Brokkr.Command.dll");

    private static async Task<(int Exit, string Out, string Error)> RunAsync(params string[] args)
    {
        var start = new ProcessStartInfo("dotnet")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        start.ArgumentList.Add(CliDll);
        foreach (var arg in args) start.ArgumentList.Add(arg);
        using var process = Process.Start(start)!;
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        return (process.ExitCode, await stdout, await stderr);
    }

    private static BrokkrUnityCommand[] StoredIntents(ScratchProject project)
    {
        using var audit = project.OpenCache();
        return audit.AllStoredDocuments.Select(entry => entry.Document).OfType<BrokkrUnityCommand>().ToArray();
    }

    [Fact]
    public async Task EveryIntentFieldReachesTheStore()
    {
        using var project = new ScratchProject();

        var (exit, output, _) = await RunAsync(
            "--unity-cache", project.StorePath, "--action", "setGameObjectTransform", "--command-id", "all-fields",
            "--wait-ms", "0",
            "--target-object-id", "obj-1", "--name", "Widget", "--component-type", "Light", "--property-path", "m_Range",
            "--value", "12", "--asset-path", "Assets/x.prefab", "--parent-object-id", "parent-1",
            "--local-position", "1,2,3", "--local-euler-angles", "4,5,6", "--local-scale", "7,8,9",
            "--view", "scene", "--output", "shot.png", "--width", "640", "--height", "480", "--requested-by", "tester");

        Assert.Equal(0, exit);
        Assert.Equal("all-fields", output.Trim());
        var intent = Assert.Single(StoredIntents(project));
        Assert.Equal(
            new[]
            {
                "all-fields", "setGameObjectTransform", "obj-1", "Widget", "Light", "m_Range", "12", "Assets/x.prefab",
                "parent-1", "1,2,3", "4,5,6", "7,8,9", "scene", "shot.png", "tester"
            },
            new[]
            {
                intent.commandId, intent.action, intent.targetObjectId, intent.name, intent.componentType,
                intent.propertyPath, intent.value, intent.assetPath, intent.parentObjectId, intent.localPosition,
                intent.localEulerAngles, intent.localScale, intent.viewKind, intent.outputPath, intent.requestedBy
            });
        Assert.Equal((640, 480), (intent.width, intent.height));
    }

    [Fact]
    public async Task EveryInvocationMintsAFreshId()
    {
        using var project = new ScratchProject();

        var first = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "0");
        var second = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "0");

        Assert.Equal(0, first.Exit);
        Assert.Equal(0, second.Exit);
        Assert.NotEqual(first.Out.Trim(), second.Out.Trim());
        Assert.Equal(2, StoredIntents(project).Length);
    }

    [Fact]
    public async Task ExitCodeIsTheReceiptsVerdict()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.StatusFor = command => command.action == "createGameObject" ? "failed" : "accepted";
        using var stop = new CancellationTokenSource();
        var loop = Task.Run(async () =>
        {
            while (!stop.IsCancellationRequested)
            {
                await editor.TickAsync();
                await Task.Delay(50);
            }
        });

        var accepted = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "20000");
        var failed = await RunAsync("--unity-cache", project.StorePath, "--action", "createGameObject", "--wait-ms", "20000");
        stop.Cancel();
        await loop;

        Assert.Equal(0, accepted.Exit);
        Assert.StartsWith("accepted:", accepted.Out);
        Assert.Equal(1, failed.Exit);
        Assert.StartsWith("failed:", failed.Out);
    }

    [Fact]
    public async Task NoEditorAnswerIsATimeoutAndLeavesOnlyTheIntent()
    {
        using var project = new ScratchProject();

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "600");

        Assert.Equal(2, result.Exit);
        Assert.Contains("Timed out", result.Error);
        using var audit = project.OpenCache();
        var documents = audit.AllStoredDocuments.ToArray();
        Assert.Single(documents);
        Assert.IsType<BrokkrUnityCommand>(documents[0].Document);
    }

    [Fact]
    public async Task UnknownOptionIsRefusedBeforeAnythingIsWritten()
    {
        using var project = new ScratchProject();

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--bogus", "1");

        Assert.Equal(2, result.Exit);
        Assert.Contains("Unknown option --bogus", result.Error);
        Assert.False(Directory.Exists(Path.GetDirectoryName(project.StorePath)));
    }

    [Fact]
    public async Task ReadHostReportsTheSinkOff()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.AgentCommandsEnabled = false;
        await editor.TickAsync();

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "readHost");

        Assert.Equal(0, result.Exit);
        Assert.Contains("agent-commands: off", result.Out);
    }

    [Fact]
    public async Task TimeoutSaysWhenTheEditorReportsTheSinkOff()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.AgentCommandsEnabled = false;
        await editor.TickAsync();
        editor.Dispose();

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "600");

        Assert.Equal(2, result.Exit);
        Assert.Contains("agent commands off", result.Error);
    }
    [Fact]
    public async Task ReadHostShowsWhetherTheSinkIsEnabled()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        await editor.TickAsync();

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "readHost");

        Assert.Equal(0, result.Exit);
        Assert.Contains("agent-commands: on", result.Out);
        Assert.Contains("project: probe", result.Out);
        Assert.Contains("state: playing=False paused=False compiling=False updating=False", result.Out);
    }

    [Theory]
    [InlineData("createGameObject")]
    [InlineData("attachComponent")]
    [InlineData("setGameObjectTransform")]
    [InlineData("setGameObjectActive")]
    [InlineData("setGameObjectParent")]
    [InlineData("setComponentProperty")]
    [InlineData("instantiatePrefab")]
    [InlineData("createPrefabVariant")]
    [InlineData("assignMaterial")]
    [InlineData("createScriptableObject")]
    [InlineData("refreshAssets")]
    [InlineData("setEditorPlayState")]
    [InlineData("setEditorPaused")]
    [InlineData("captureEditorView")]
    public async Task EveryActionNameReachesTheEditorOnceWithOneReceipt(string action)
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        using var stop = new CancellationTokenSource();
        var loop = Task.Run(async () =>
        {
            while (!stop.IsCancellationRequested)
            {
                await editor.TickAsync();
                await Task.Delay(50);
            }
        });

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", action, "--output", "probe.png", "--wait-ms", "20000");
        await Task.Delay(200);
        stop.Cancel();
        await loop;

        Assert.Equal(0, result.Exit);
        var executed = Assert.Single(editor.Executed);
        Assert.Equal(action, executed.action);
        using var audit = project.OpenCache();
        var receipt = Assert.Single(audit.AllStoredDocuments.Select(entry => entry.Document).OfType<BrokkrUnityCommandReceipt>());
        Assert.Equal(executed.commandId, receipt.commandId);
    }

    [Fact]
    public async Task ReusedCommandIdIsRefusedAndNothingIsWritten()
    {
        using var project = new ScratchProject();
        await project.WriteCommandAsync("used-once", "refreshAssets");
        using (var editor = project.OpenCache())
            await BrokkrCommandLedgerTests.Answer(editor, "used-once");

        var result = await RunAsync(
            "--unity-cache", project.StorePath, "--action", "setEditorPaused", "--command-id", "used-once", "--wait-ms", "2000");

        Assert.Equal(2, result.Exit);
        Assert.Contains("already has a receipt", result.Error);
        var intent = Assert.Single(StoredIntents(project));
        Assert.Equal("refreshAssets", intent.action);
    }

    [Theory]
    [InlineData("empty")]
    [InlineData("legacy")]
    public async Task UnreadableStoreExitsTwoWithAMessageThatNamesIt(string kind)
    {
        using var project = new ScratchProject();
        Directory.CreateDirectory(Path.GetDirectoryName(project.StorePath)!);
        // An empty file, or the single-file store the directory store replaced.
        File.WriteAllBytes(project.StorePath, kind == "empty" ? Array.Empty<byte>() : new byte[] { 0x93, 0x01, 0x02 });

        var write = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "0");
        var read = await RunAsync("--unity-cache", project.StorePath, "--action", "readHost");

        Assert.Equal(2, write.Exit);
        Assert.Contains("unreadable", write.Error);
        Assert.Contains(project.StorePath, write.Error);
        Assert.Equal(2, read.Exit);
        Assert.Contains("unreadable", read.Error);
    }

    [Fact]
    public async Task WaitContinuesPastTheAttemptMarkerToTheVerdict()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.OnExecute = _ => Thread.Sleep(1500);
        using var stop = new CancellationTokenSource();
        var loop = Task.Run(async () =>
        {
            while (!stop.IsCancellationRequested)
            {
                await editor.TickAsync();
                await Task.Delay(50);
            }
        });

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "20000");
        stop.Cancel();
        await loop;

        Assert.Equal(0, result.Exit);
        Assert.StartsWith("accepted:", result.Out);
    }

    [Fact]
    public async Task InterruptedIntentIsReportedAsANonAcceptanceNotAHang()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.OnExecute = _ => throw new InvalidOperationException("the editor died");
        using var stop = new CancellationTokenSource();
        var loop = Task.Run(async () =>
        {
            while (!stop.IsCancellationRequested)
            {
                try { await editor.TickAsync(); } catch (InvalidOperationException) { }
                await Task.Delay(50);
            }
        });

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "20000");
        stop.Cancel();
        await loop;

        Assert.Equal(1, result.Exit);
        Assert.StartsWith("interrupted:", result.Out);
        Assert.Single(editor.Executed);
    }

    [Fact]
    public async Task AnUnexpectedFailureExitsTwoInsteadOfAborting()
    {
        using var project = new ScratchProject();
        await project.WriteCommandAsync("seed");
        // The store opens cleanly and then cannot be committed to: a directory sits where the commit lock file goes.
        var records = project.StorePath + ".records";
        var lockFile = Path.Combine(records, ".commit.lock");
        File.Delete(lockFile);
        Directory.CreateDirectory(lockFile);

        var result = await RunAsync("--unity-cache", project.StorePath, "--action", "refreshAssets", "--wait-ms", "0");

        Assert.Equal(2, result.Exit);
        Assert.False(string.IsNullOrWhiteSpace(result.Error));
    }
}
