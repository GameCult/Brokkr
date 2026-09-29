using GameCult.Brokkr;
using GameCult.Caching;

namespace Brokkr.Contracts.Tests;

// The Imagination probe, kept: many writers, one editor, the real store. Scaled to run in seconds; the probe
// measured 24 commands at a 1000 ms tick and 90 at a 20 ms tick, three writers at a time, with no loss.
public sealed class EditorScenarioTests
{
    [Theory]
    [InlineData(24, 200)]
    [InlineData(90, 20)]
    public async Task ManyWritersOneEditorExecuteEveryIntentOnceAndAnswerEachId(int commands, int tickMilliseconds)
    {
        using var project = new ScratchProject();
        using var editor = await EditorProbe.StartAsync(project.StorePath);
        var ids = Enumerable.Range(0, commands).Select(index => $"scenario-{index}").ToArray();

        using var stop = new CancellationTokenSource();
        var editorLoop = Task.Run(async () =>
        {
            while (!stop.IsCancellationRequested)
            {
                await editor.TickAsync();
                await Task.Delay(tickMilliseconds);
            }
        });

        foreach (var wave in ids.Chunk(3))
            await Task.WhenAll(wave.Select(id => project.WriteCommandAsync(id)));

        var deadline = DateTime.UtcNow.AddSeconds(60);
        while (DateTime.UtcNow < deadline && editor.Executed.Count < commands)
            await Task.Delay(50);
        // One more tick after the last receipt, so a duplicate execution would have had its chance.
        await Task.Delay(tickMilliseconds * 3);
        stop.Cancel();
        await editorLoop;

        Assert.Equal(commands, editor.Executed.Count);
        Assert.Equal(ids.OrderBy(id => id), editor.Executed.Select(command => command.commandId).OrderBy(id => id));
        using var audit = project.OpenCache();
        var receipts = audit.AllStoredDocuments.Select(entry => entry.Document).OfType<BrokkrUnityCommandReceipt>().ToArray();
        Assert.Equal(ids.OrderBy(id => id), receipts.Select(receipt => receipt.commandId).OrderBy(id => id));
    }
}
