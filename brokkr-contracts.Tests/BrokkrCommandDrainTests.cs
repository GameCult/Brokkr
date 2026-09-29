using GameCult.Brokkr;
using GameCult.Caching;

namespace Brokkr.Contracts.Tests;

// The rules BrokkrCommandDrain owns, through the same drain the editor service runs, over a real directory store.
public sealed class BrokkrCommandDrainTests
{
    private static BrokkrUnityCommandReceipt[] Receipts(ScratchProject project)
    {
        using var audit = project.OpenCache();
        return audit.AllStoredDocuments.Select(entry => entry.Document).OfType<BrokkrUnityCommandReceipt>().ToArray();
    }

    private static string StatusOf(ScratchProject project, string commandId) =>
        Receipts(project).Single(receipt => receipt.commandId == commandId).status;

    [Fact]
    public async Task IntentStoredBeforeTheSinkWasEnabledExpiresAndNeverRuns()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.AgentCommandsEnabled = false;
        await project.WriteCommandAsync("written-while-off");
        await editor.TickAsync();
        Assert.Empty(editor.Executed);

        await Task.Delay(30);
        editor.EnabledAt = DateTimeOffset.UtcNow;
        editor.AgentCommandsEnabled = true;
        await Task.Delay(30);
        await project.WriteCommandAsync("written-after-enable");
        await editor.TickAsync();
        await editor.TickAsync();

        Assert.Equal(new[] { "written-after-enable" }, editor.Executed.Select(command => command.commandId));
        Assert.Equal("expired", StatusOf(project, "written-while-off"));
        Assert.Equal("accepted", StatusOf(project, "written-after-enable"));
    }

    [Fact]
    public async Task ReEnablingExpiresWhatWaitedThroughTheOffPeriod()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.EnabledAt = DateTimeOffset.UtcNow;
        await Task.Delay(30);
        await project.WriteCommandAsync("ran-while-on");
        await editor.TickAsync();

        editor.AgentCommandsEnabled = false;
        await Task.Delay(30);
        await project.WriteCommandAsync("waited-while-off");
        await Task.Delay(30);
        editor.EnabledAt = DateTimeOffset.UtcNow;
        editor.AgentCommandsEnabled = true;
        await editor.TickAsync();

        Assert.Equal(new[] { "ran-while-on" }, editor.Executed.Select(command => command.commandId));
        Assert.Equal("expired", StatusOf(project, "waited-while-off"));
    }

    [Fact]
    public async Task AttemptReceiptIsDurableBeforeTheExecutorRuns()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        string? seenByAnotherProcess = null;
        editor.OnExecute = command => seenByAnotherProcess = Receipts(project)
            .SingleOrDefault(receipt => receipt.commandId == command.commandId)?.status;
        await project.WriteCommandAsync("marked");

        await editor.TickAsync();

        Assert.Equal("attempted", seenByAnotherProcess);
        Assert.Equal("accepted", StatusOf(project, "marked"));
    }

    [Fact]
    public async Task CrashDuringExecutionNeverRerunsTheIntentAndReportsItInterrupted()
    {
        using var project = new ScratchProject();
        await project.WriteCommandAsync("crashy");
        var firstRun = await EditorProbe.StartAsync(project.StorePath);
        firstRun.OnExecute = _ => throw new InvalidOperationException("the editor died");
        await Assert.ThrowsAsync<InvalidOperationException>(firstRun.TickAsync);
        firstRun.Dispose();
        await project.WriteCommandAsync("bystander");

        using var restarted = await EditorProbe.StartAsync(project.StorePath);
        for (var tick = 0; tick < 5; tick++)
            await restarted.TickAsync();

        Assert.Equal(new[] { "bystander" }, restarted.Executed.Select(command => command.commandId));
        Assert.Equal("interrupted", StatusOf(project, "crashy"));
    }

    [Fact]
    public async Task FailingFinalReceiptWriteNeverRerunsTheIntent()
    {
        // A receipt write that throws every second must not turn createGameObject into one object per second.
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.FailReceiptWrite = receipt => receipt.status == "accepted";
        await project.WriteCommandAsync("unlucky");

        await Assert.ThrowsAsync<IOException>(editor.TickAsync);
        for (var tick = 0; tick < 5; tick++)
        {
            try { await editor.TickAsync(); } catch (IOException) { }
        }

        Assert.Single(editor.Executed);
        editor.FailReceiptWrite = null;
        await editor.TickAsync();
        Assert.Single(editor.Executed);
        Assert.Equal("interrupted", StatusOf(project, "unlucky"));
    }

    [Fact]
    public async Task FailingAttemptWriteExecutesNothing()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.FailReceiptWrite = receipt => receipt.status == "attempted";
        await project.WriteCommandAsync("unmarked");

        await Assert.ThrowsAsync<IOException>(editor.TickAsync);

        Assert.Empty(editor.Executed);
    }

    [Fact]
    public async Task OneTickHandlesAtMostTheBoundAndTheRestWaits()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        var total = BrokkrCommandDrain.MaxPerTick * 2 + 3;
        for (var index = 0; index < total; index++)
            await project.WriteCommandAsync($"flood-{index}");

        var first = await editor.TickAsync();

        Assert.Equal(BrokkrCommandDrain.MaxPerTick, first);
        Assert.Equal(BrokkrCommandDrain.MaxPerTick, editor.Executed.Count);
        while (await editor.TickAsync() > 0) { }
        Assert.Equal(total, editor.Executed.Count);
        Assert.Equal(total, editor.Executed.Select(command => command.commandId).Distinct().Count());
    }

    [Fact]
    public async Task ExpiredIntentsCountTowardTheBoundToo()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        for (var index = 0; index < BrokkrCommandDrain.MaxPerTick + 4; index++)
            await project.WriteCommandAsync($"stale-{index}");
        await Task.Delay(30);
        editor.EnabledAt = DateTimeOffset.UtcNow;

        Assert.Equal(BrokkrCommandDrain.MaxPerTick, await editor.TickAsync());
        Assert.Equal(4, await editor.TickAsync());
        Assert.Empty(editor.Executed);
    }

    [Fact]
    public async Task DisallowedActionIsDeniedAndNeverExecuted()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        await project.WriteCommandAsync("nope", "saveScene");

        await editor.TickAsync();

        Assert.Empty(editor.Executed);
        Assert.Equal("denied", StatusOf(project, "nope"));
    }
}
