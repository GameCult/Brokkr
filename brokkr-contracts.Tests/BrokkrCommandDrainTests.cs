using System.Diagnostics;
using GameCult.Brokkr;
using GameCult.Caching;
using Xunit.Abstractions;

namespace Brokkr.Contracts.Tests;

// The rules BrokkrCommandDrain owns, through the same drain the editor service runs, over a real directory store.
public sealed class BrokkrCommandDrainTests
{
    // The budgets the flood scenario holds the editor to. Yggdrasil's containers run several jobs at once, so they
    // are generous. A tick must not grow with the flood; the enable is one commit whose cost is the store writing
    // each expiry receipt (about 3 ms apiece on Yggdrasil), paid once, on the operator's click.
    private static readonly TimeSpan EnableBudget = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan TickBudget = TimeSpan.FromSeconds(3);

    private readonly ITestOutputHelper output;

    public BrokkrCommandDrainTests(ITestOutputHelper output) => this.output = output;

    private static BrokkrUnityCommandReceipt[] Receipts(ScratchProject project)
    {
        using var audit = project.OpenCache();
        return audit.AllStoredDocuments.Select(entry => entry.Document).OfType<BrokkrUnityCommandReceipt>().ToArray();
    }

    private static string StatusOf(ScratchProject project, string commandId) =>
        Receipts(project).Single(receipt => receipt.commandId == commandId).status;

    [Fact]
    public async Task IntentAlreadyInTheStoreWhenTheSinkIsEnabledExpiresAndNeverRuns()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.DisableSink();
        await project.WriteCommandAsync("written-while-off");
        await editor.TickAsync();
        Assert.Empty(editor.Executed);

        Assert.Equal(1, await editor.EnableSinkAsync());
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
        await project.WriteCommandAsync("ran-while-on");
        await editor.TickAsync();

        editor.DisableSink();
        await project.WriteCommandAsync("waited-while-off");
        await editor.EnableSinkAsync();
        await editor.TickAsync();

        Assert.Equal(new[] { "ran-while-on" }, editor.Executed.Select(command => command.commandId));
        Assert.Equal("expired", StatusOf(project, "waited-while-off"));
    }

    [Fact]
    public async Task IntentsWrittenWhileTheEditorWasDownRunOnRestart()
    {
        // The token survives a restart and so does the marker: what arrives after the enable is fresh.
        using var project = new ScratchProject();
        using (var first = await EditorProbe.StartAsync(project.StorePath))
            await first.TickAsync();
        await project.WriteCommandAsync("written-while-down");

        using var restarted = await EditorProbe.StartAsync(project.StorePath);
        await restarted.TickAsync();

        Assert.Equal(new[] { "written-while-down" }, restarted.Executed.Select(command => command.commandId));
    }

    [Theory]
    [InlineData("never-enabled-here")]
    [InlineData("enabled-by-someone-else")]
    public async Task StoreThisEditorDidNotEnableRunsNothing(string kind)
    {
        // A re-clone at the same path keeps the old EditorPrefs token; the new clone's store has no marker for it,
        // or carries a marker minted elsewhere. Neither is authority.
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath, enabledInStore: kind != "never-enabled-here");
        if (kind == "enabled-by-someone-else")
        {
            using var other = project.OpenCache();
            await other.AddAsync(
                new BrokkrSinkEnabled { token = "another-editors-token" },
                new CultRecordHandle<BrokkrSinkEnabled>(BrokkrCommandLedger.SinkKey));
            await other.FlushAsync();
        }

        await project.WriteCommandAsync("from-the-new-clone");
        await editor.TickAsync();
        await editor.TickAsync();

        Assert.Empty(editor.Executed);
        Assert.False(editor.AgentCommandsEnabled, "the editor drops the stale token");
        Assert.Empty(Receipts(project));
        // The operator's enable is what makes it this editor's store, and it expires what is already there.
        Assert.Equal(1, await editor.EnableSinkAsync());
        await editor.TickAsync();
        Assert.Empty(editor.Executed);
        Assert.Equal("expired", StatusOf(project, "from-the-new-clone"));
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
        var firstRun = await EditorProbe.StartAsync(project.StorePath);
        await project.WriteCommandAsync("crashy");
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
    public async Task FailingFinalReceiptPutNeverRerunsTheIntent()
    {
        // A receipt write that throws every second must not turn createGameObject into one object per second.
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.FailReceiptPut = receipt => receipt.status == "accepted";
        await project.WriteCommandAsync("unlucky");

        await Assert.ThrowsAsync<IOException>(editor.TickAsync);
        for (var tick = 0; tick < 5; tick++)
        {
            try { await editor.TickAsync(); } catch (IOException) { }
        }

        Assert.Single(editor.Executed);
        editor.FailReceiptPut = null;
        await editor.TickAsync();
        Assert.Single(editor.Executed);
        Assert.Equal("interrupted", StatusOf(project, "unlucky"));
    }

    [Fact]
    public async Task FailingFinalFlushNeverRerunsTheIntentEvenAfterARestart()
    {
        using var project = new ScratchProject();
        var editor = await EditorProbe.StartAsync(project.StorePath);
        await project.WriteCommandAsync("unlucky");
        var flushes = 0;
        editor.FailFlush = () => ++flushes == 2; // the marker's flush lands, the verdict's does not
        await Assert.ThrowsAsync<IOException>(editor.TickAsync);
        Assert.Single(editor.Executed);
        editor.Dispose(); // the editor dies here, before anything else could flush the verdict

        using var restarted = await EditorProbe.StartAsync(project.StorePath);
        for (var tick = 0; tick < 3; tick++)
            await restarted.TickAsync();

        Assert.Empty(restarted.Executed);
        Assert.Equal("interrupted", StatusOf(project, "unlucky"));
    }

    [Theory]
    [InlineData("put")]
    [InlineData("flush")]
    public async Task IntentWhoseMarkerCouldNotBeWrittenNeverStartedAndIsRetried(string failing)
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        await project.WriteCommandAsync("unmarked");
        if (failing == "put")
            editor.FailReceiptPut = receipt => receipt.status == "attempted";
        else
            editor.FailFlush = () => true;

        await Assert.ThrowsAsync<IOException>(editor.TickAsync);

        Assert.Empty(editor.Executed);
        editor.FailReceiptPut = null;
        editor.FailFlush = null;
        await editor.TickAsync();
        await editor.TickAsync();
        Assert.Single(editor.Executed);
        Assert.Equal("accepted", StatusOf(project, "unmarked"));
        Assert.DoesNotContain(Receipts(project), receipt => receipt.status == "interrupted");
    }

    [Fact]
    public async Task OneTickExecutesAtMostTheBoundAndTheRestWaits()
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        var total = BrokkrCommandDrain.MaxPerTick * 2 + 3;
        await project.WriteCommandsAsync(Enumerable.Range(0, total).Select(index => $"flood-{index}"));

        var first = await editor.TickAsync();

        Assert.Equal(BrokkrCommandDrain.MaxPerTick, first);
        Assert.Equal(BrokkrCommandDrain.MaxPerTick, editor.Executed.Count);
        while (await editor.TickAsync() > 0) { }
        Assert.Equal(total, editor.Executed.Count);
        Assert.Equal(total, editor.Executed.Select(command => command.commandId).Distinct().Count());
    }

    [Fact]
    public async Task AStaleFloodExpiresInOneFlushAndTheFreshIntentRunsInTheFirstTick()
    {
        const int stale = 2000;
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        editor.DisableSink();
        await project.WriteCommandsAsync(Enumerable.Range(0, stale).Select(index => $"stale-{index}"));

        var flushesBefore = editor.Flushes;
        var clock = Stopwatch.StartNew();
        var expired = await editor.EnableSinkAsync();
        var enableTime = clock.Elapsed;
        output.WriteLine($"enable: {expired} expired in {enableTime.TotalMilliseconds:F0} ms, {editor.Flushes - flushesBefore} flush(es)");
        Assert.Equal(stale, expired);
        Assert.Equal(1, editor.Flushes - flushesBefore);
        Assert.True(enableTime < EnableBudget, $"enable took {enableTime}");

        await project.WriteCommandAsync("fresh");
        var slowest = TimeSpan.Zero;
        var ticks = 0;
        do
        {
            clock.Restart();
            await editor.TickAsync();
            slowest = clock.Elapsed > slowest ? clock.Elapsed : slowest;
            output.WriteLine($"tick {++ticks}: {clock.Elapsed.TotalMilliseconds:F0} ms, receipts kept {Receipts(project).Length}");
            if (ticks == 1)
                Assert.Equal(new[] { "fresh" }, editor.Executed.Select(command => command.commandId));
        }
        while (Receipts(project).Length > BrokkrCommandDrain.RetainedReceipts && ticks < 40);

        Assert.True(slowest < TickBudget, $"slowest tick took {slowest}");
        Assert.Equal(new[] { "fresh" }, editor.Executed.Select(command => command.commandId));
        Assert.Equal("accepted", StatusOf(project, "fresh"));
        // Receipts are bounded, and an intent goes with its receipt: nothing is left to run again.
        using var audit = project.OpenCache();
        var documents = audit.AllStoredDocuments.Select(entry => entry.Document).ToArray();
        Assert.Equal(BrokkrCommandDrain.RetainedReceipts, documents.OfType<BrokkrUnityCommandReceipt>().Count());
        Assert.Equal(BrokkrCommandDrain.RetainedReceipts, documents.OfType<BrokkrUnityCommand>().Count());
        Assert.False(new BrokkrCommandLedger(audit).TryNextPending(out _));
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
