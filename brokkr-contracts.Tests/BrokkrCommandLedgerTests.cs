using GameCult.Brokkr;
using GameCult.Caching;

namespace Brokkr.Contracts.Tests;

public sealed class BrokkrCommandLedgerTests
{
    internal static async Task Answer(CultCache cache, string commandId)
    {
        await cache.AddAsync(
            new BrokkrUnityCommandReceipt { commandId = commandId, status = "accepted" },
            new CultRecordHandle<BrokkrUnityCommandReceipt>(BrokkrCommandLedger.ReceiptKey(commandId)));
        await cache.FlushAsync();
    }

    [Fact]
    public async Task ExternallyWrittenCommandIsPendingAfterPull()
    {
        using var project = new ScratchProject();
        using var editor = project.OpenCache();
        var ledger = new BrokkrCommandLedger(editor);
        Assert.False(ledger.TryNextPending(out _));

        await project.WriteCommandAsync("written-elsewhere");

        Assert.False(ledger.TryNextPending(out _), "an intent is invisible until the editor pulls the store");
        await ledger.PullAsync();
        Assert.True(ledger.TryNextPending(out var pending));
        Assert.Equal("written-elsewhere", pending.commandId);
    }

    [Fact]
    public async Task CommandWithReceiptIsNeverPendingAgain()
    {
        using var project = new ScratchProject();
        await project.WriteCommandAsync("once");
        using var editor = project.OpenCache();
        var ledger = new BrokkrCommandLedger(editor);
        Assert.True(ledger.TryNextPending(out _));

        await Answer(editor, "once");

        Assert.False(ledger.TryNextPending(out _));
        await ledger.PullAsync();
        Assert.False(ledger.TryNextPending(out _));
    }

    [Fact]
    public async Task RewrittenCommandIdIsNotReExecuted()
    {
        // Command ids are single-use: a receipt retires the id, and a later intent written under it is a caller
        // defect that the editor ignores. Callers that mean a new act mint a new id.
        using var project = new ScratchProject();
        await project.WriteCommandAsync("reused", "refreshAssets");
        using var editor = project.OpenCache();
        var ledger = new BrokkrCommandLedger(editor);
        Assert.True(ledger.TryNextPending(out _));
        await Answer(editor, "reused");

        await project.WriteCommandAsync("reused", "setEditorPaused");
        await ledger.PullAsync();

        Assert.False(ledger.TryNextPending(out _));
    }

    [Fact]
    public async Task FreshIdAfterAnAnsweredOneIsPending()
    {
        using var project = new ScratchProject();
        await project.WriteCommandAsync("first");
        using var editor = project.OpenCache();
        var ledger = new BrokkrCommandLedger(editor);
        await Answer(editor, "first");

        await project.WriteCommandAsync("second", "setEditorPaused");
        await ledger.PullAsync();

        Assert.True(ledger.TryNextPending(out var pending));
        Assert.Equal("second", pending.commandId);
    }

    [Fact]
    public async Task ReceiptWrittenByAnotherProcessRetiresTheCommand()
    {
        using var project = new ScratchProject();
        await project.WriteCommandAsync("answered-elsewhere");
        using var editor = project.OpenCache();
        var ledger = new BrokkrCommandLedger(editor);
        Assert.True(ledger.TryNextPending(out _));

        using (var other = project.OpenCache())
            await Answer(other, "answered-elsewhere");
        await ledger.PullAsync();

        Assert.False(ledger.TryNextPending(out _));
    }

    [Fact]
    public async Task PendingOrderIsArrivalOrder()
    {
        using var project = new ScratchProject();
        // Written b then a: stored-at order, not key order, decides.
        await project.WriteCommandAsync("b-first");
        await Task.Delay(20);
        await project.WriteCommandAsync("a-second");
        using var editor = project.OpenCache();
        var ledger = new BrokkrCommandLedger(editor);

        Assert.True(ledger.TryNextPending(out var first));
        Assert.Equal("b-first", first.commandId);
        await Answer(editor, "b-first");
        Assert.True(ledger.TryNextPending(out var second));
        Assert.Equal("a-second", second.commandId);
    }

    [Fact]
    public async Task CommandWithoutAnIdIsNeverPending()
    {
        using var project = new ScratchProject();
        await project.WriteCommandAsync("  ");
        using var editor = project.OpenCache();

        Assert.False(new BrokkrCommandLedger(editor).TryNextPending(out _));
    }

    [Fact]
    public async Task TwoLedgersOverOneStoreExecuteEachIdOnce()
    {
        // The Unity double drain, at the layer where the rule lives. Two editors take turns over one store; each
        // pulls before it looks and answers before it yields, so together they must execute each id exactly once.
        // The ledger cannot serialise simultaneous drains; the service being the only owner does that.
        using var project = new ScratchProject();
        var ids = Enumerable.Range(0, 6).Select(index => $"cmd-{index}").ToArray();
        foreach (var id in ids)
        {
            await project.WriteCommandAsync(id);
            await Task.Delay(5);
        }

        using var first = project.OpenCache();
        using var second = project.OpenCache();
        var turns = new[]
        {
            (Cache: first, Ledger: new BrokkrCommandLedger(first)),
            (Cache: second, Ledger: new BrokkrCommandLedger(second))
        };
        var executed = new List<string>();
        for (var turn = 0; turn < ids.Length * 2; turn++)
        {
            var (cache, ledger) = turns[turn % 2];
            await ledger.PullAsync();
            if (!ledger.TryNextPending(out var command)) continue;
            executed.Add(command.commandId);
            await Answer(cache, command.commandId);
        }

        Assert.Equal(ids.OrderBy(id => id), executed.OrderBy(id => id));
        using var audit = project.OpenCache();
        Assert.Equal(ids.Length, audit.AllStoredDocuments.Count(entry => entry.Document is BrokkrUnityCommandReceipt));
    }
}
