#nullable disable
using System;
using System.Threading.Tasks;

namespace GameCult.Brokkr
{
    // What the drain writes through. BrokkrCommandStore is the real one; the scenario harness wraps it to inject
    // failures. Writes only stage and FlushAsync makes them durable (an fsync), so anything that must land together
    // goes through one of the batch methods, each a single atomic commit.
    public interface IBrokkrCommandStore
    {
        Task PutReceiptAsync(BrokkrUnityCommandReceipt receipt);
        Task DeleteReceiptAsync(string commandId);
        // Every expiry receipt and the enable marker, or none of them. False when the store changed since the
        // caller's pull, and nothing was written.
        Task<bool> TryCommitEnableAsync(BrokkrUnityCommandReceipt[] expired, BrokkrSinkEnabled marker);
        // Each intent with its receipt, or none of them.
        Task DeleteAnsweredAsync(string[] commandIds);
        Task FlushAsync();
    }
    // The one decision path from a pending intent to a receipt. BrokkrEditorService supplies the executor and the
    // store; the scenario harness supplies fakes. Nothing else may run an intent.
    //
    // Whether an intent may run is decided by what the store holds, never by comparing clocks:
    //   * EnableAsync is the operator's act. It answers every intent already in the store with "expired" and writes
    //     a BrokkrSinkEnabled marker carrying a fresh token, all in one flush. The token also lives in the
    //     editor's own EditorPrefs, so a store this editor did not enable (a re-clone, a copied .brokkr) carries no
    //     matching marker and DrainAsync refuses to run anything from it.
    //   * Anything that arrives after the marker is fresh, whatever its writer's clock says.
    //
    // Every intent leaves exactly one of these receipts, and any receipt retires its id (BrokkrCommandLedger):
    //   expired      in the store when the operator enabled the sink; never runs
    //   denied       admission refused it
    //   attempted    written and flushed BEFORE execution; it stays only if the editor died or the final receipt
    //                could not be written, and the next drain rewrites it as interrupted
    //   interrupted  an attempt that did not finish; it is never run again automatically, the operator decides
    //   accepted / failed / ...  the executor's verdict
    // A marker that could not be written or flushed is withdrawn, so an intent that never started is normally
    // retried. If the store fails in a way that leaves the marker behind, the intent is reported as interrupted,
    // which errs safe.
    //
    // The token is not authentication. It stops a stale "enabled" in EditorPrefs from authorizing a store this
    // editor never enabled (a re-clone, a foreign copy). Anyone with write access to .brokkr can write intents, and
    // the Allowed Actions policy is what limits them; nothing here proves who wrote a document.
    public sealed class BrokkrCommandDrain
    {
        // The most intents one drain executes or denies. A flood cannot hold the editor's update loop.
        public const int MaxPerTick = 16;

        // Receipts are kept for the newest RetainedReceipts answers, and never for less than ReceiptFloor: a
        // receipt younger than that is not pruned whatever the count, so a caller waiting on it (at most
        // MaxCallerWait, which brokkr-command enforces) always reads it. Older receipts beyond the count are
        // deleted with their intents, at most MaxPrunedPerTick pairs per drain. The floor is measured on the
        // editor's own clock against receipts the editor stamped. Id reuse is refused only while the receipt exists.
        public const int RetainedReceipts = 1000;
        public const int MaxPrunedPerTick = 128;
        public static readonly TimeSpan ReceiptFloor = TimeSpan.FromMinutes(10);
        public static readonly TimeSpan MaxCallerWait = TimeSpan.FromMinutes(5);

        // Enable retries pull-and-recompute this many times before giving up on a store that will not hold still.
        public const int MaxEnableAttempts = 8;

        public const int NotAuthorized = -1;

        public const string AttemptedStatus = "attempted";
        public const string InterruptedStatus = "interrupted";
        public const string ExpiredStatus = "expired";

        private readonly BrokkrCommandLedger ledger;
        private readonly BrokkrCommandPolicy policy;
        private readonly Func<BrokkrUnityCommand, BrokkrUnityCommandReceipt> execute;
        private readonly IBrokkrCommandStore store;
        private readonly Func<DateTimeOffset> clock;

        public BrokkrCommandDrain(
            BrokkrCommandLedger ledger,
            BrokkrCommandPolicy policy,
            Func<BrokkrUnityCommand, BrokkrUnityCommandReceipt> execute,
            IBrokkrCommandStore store,
            Func<DateTimeOffset> clock = null)
        {
            this.clock = clock ?? (() => DateTimeOffset.UtcNow);
            this.ledger = ledger ?? throw new ArgumentNullException(nameof(ledger));
            this.policy = policy ?? throw new ArgumentNullException(nameof(policy));
            this.execute = execute ?? throw new ArgumentNullException(nameof(execute));
            this.store = store ?? throw new ArgumentNullException(nameof(store));
        }

        // The operator turned the sink on. Returns how many waiting intents it expired. The caller keeps the token
        // and passes it to every DrainAsync; nothing runs before this returns.
        //
        // The commit is conditional on the store being what this editor just observed, so an intent that lands
        // between the pull and the commit makes it refuse; the loop then pulls again and the newcomer is expired
        // with the rest. If writers never let it settle, it throws and the sink stays off.
        public async Task<int> EnableAsync(string token)
        {
            if (string.IsNullOrWhiteSpace(token))
            {
                throw new ArgumentException("A sink token is required.", nameof(token));
            }

            for (var attempt = 0; attempt < MaxEnableAttempts; attempt++)
            {
                // Our own staged writes first (a conditional commit refuses a dirty store), then everyone else's.
                await store.FlushAsync();
                await ledger.PullAsync();
                var waiting = ledger.Pending(int.MaxValue);
                var expired = new BrokkrUnityCommandReceipt[waiting.Length];
                for (var index = 0; index < waiting.Length; index++)
                {
                    expired[index] = Receipt(waiting[index], ExpiredStatus,
                        "This intent was already in the store when the operator enabled the command sink, so the "
                        + "operator never saw it. It was not run.");
                }

                var marker = new BrokkrSinkEnabled { token = token, enabledAt = DateTime.UtcNow.ToString("O") };
                if (await store.TryCommitEnableAsync(expired, marker))
                {
                    await store.FlushAsync();
                    return waiting.Length;
                }
            }

            throw new InvalidOperationException(
                $"The command store kept changing under the enable ({MaxEnableAttempts} attempts): something is writing "
                + "intents continuously. Stop it and enable again; the sink stays off.");
        }
        // Returns how many intents it answered, or NotAuthorized when this store holds no enable marker for the
        // token: the caller must treat the sink as off until the operator enables it again.
        public async Task<int> DrainAsync(string token)
        {
            if (!ledger.SinkAuthorized(token))
            {
                return NotAuthorized;
            }

            // Nothing is in flight at the start of a drain (execution is synchronous inside it), so an attempted
            // receipt found here belongs to a run that never finished.
            var interrupted = ledger.AttemptedReceipts();
            foreach (var attempt in interrupted)
            {
                await store.PutReceiptAsync(Receipt(attempt.commandId, attempt.requestedBy, InterruptedStatus,
                    "The editor stopped, or could not record the result, after starting this intent. It was not run "
                    + "again. Check the project, then send a new intent if it should run."));
            }

            if (interrupted.Length > 0)
            {
                await store.FlushAsync();
            }

            var handled = 0;
            foreach (var command in ledger.Pending(MaxPerTick))
            {
                handled++;
                var admission = policy.Decide(command);
                if (!admission.Allowed)
                {
                    var denied = admission.DeniedReceipt(command);
                    denied.requestedBy = command.requestedBy;
                    await store.PutReceiptAsync(denied);
                    await store.FlushAsync();
                    continue;
                }

                // Durable before any effect: a crash after this line leaves the marker, never a second run.
                await MarkAttemptedAsync(command);
                var receipt = execute(command);
                receipt.commandId = command.commandId;
                receipt.requestedBy = command.requestedBy;
                await store.PutReceiptAsync(receipt);
                await store.FlushAsync();
            }

            // One commit takes each intent with its receipt: an intent without its receipt would run again.
            var pruned = ledger.Prunable(RetainedReceipts, MaxPrunedPerTick, clock() - ReceiptFloor);
            if (pruned.Length > 0)
            {
                await store.DeleteAnsweredAsync(pruned);
                await store.FlushAsync();
            }

            return handled;
        }

        private async Task MarkAttemptedAsync(BrokkrUnityCommand command)
        {
            try
            {
                await store.PutReceiptAsync(Receipt(command, AttemptedStatus, "Started; no result recorded yet."));
                await store.FlushAsync();
            }
            catch
            {
                // Nothing has run. Withdraw the marker so this reads as never started and is retried; if the store
                // will not even do that, the leftover marker is reported as interrupted, which errs safe.
                try { await store.DeleteReceiptAsync(command.commandId); } catch { }
                throw;
            }
        }

        private static BrokkrUnityCommandReceipt Receipt(BrokkrUnityCommand command, string status, string message) =>
            Receipt(command.commandId, command.requestedBy, status, message);

        private static BrokkrUnityCommandReceipt Receipt(string commandId, string requestedBy, string status, string message) =>
            new BrokkrUnityCommandReceipt
            {
                commandId = commandId,
                requestedBy = requestedBy,
                status = status,
                message = message,
                observedAt = DateTime.UtcNow.ToString("O")
            };
    }
}
