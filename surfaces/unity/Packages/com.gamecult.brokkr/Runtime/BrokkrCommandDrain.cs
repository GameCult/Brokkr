#nullable disable
using System;
using System.Globalization;
using System.Threading.Tasks;

namespace GameCult.Brokkr
{
    // The one decision path from a pending intent to a receipt. BrokkrEditorService supplies the executor and the
    // receipt writer; the scenario harness supplies fakes. Nothing else may run an intent.
    //
    // Every intent leaves exactly one of these receipts, and any receipt retires its id (BrokkrCommandLedger):
    //   expired      stored before the sink was last enabled; the operator never saw it, so it never runs
    //   denied       admission refused it
    //   attempted    written and flushed BEFORE execution; it stays only if the editor died or the final receipt
    //                could not be written, and the next drain rewrites it as interrupted
    //   interrupted  an attempt that did not finish; it is never run again automatically, the operator decides
    //   accepted / failed / ...  the executor's verdict
    // A receipt write that fails therefore cannot make an intent run twice: at worst the marker is the answer.
    public sealed class BrokkrCommandDrain
    {
        // The most intents one drain handles, receipts of every kind included. A flood cannot hold the editor's
        // update loop; the remainder waits for the next tick.
        public const int MaxPerTick = 16;

        public const string AttemptedStatus = "attempted";
        public const string InterruptedStatus = "interrupted";
        public const string ExpiredStatus = "expired";

        private readonly BrokkrCommandLedger ledger;
        private readonly BrokkrCommandPolicy policy;
        private readonly Func<BrokkrUnityCommand, BrokkrUnityCommandReceipt> execute;
        private readonly Func<BrokkrUnityCommandReceipt, Task> publishReceipt;

        public BrokkrCommandDrain(
            BrokkrCommandLedger ledger,
            BrokkrCommandPolicy policy,
            Func<BrokkrUnityCommand, BrokkrUnityCommandReceipt> execute,
            Func<BrokkrUnityCommandReceipt, Task> publishReceipt)
        {
            this.ledger = ledger ?? throw new ArgumentNullException(nameof(ledger));
            this.policy = policy ?? throw new ArgumentNullException(nameof(policy));
            this.execute = execute ?? throw new ArgumentNullException(nameof(execute));
            this.publishReceipt = publishReceipt ?? throw new ArgumentNullException(nameof(publishReceipt));
        }

        // sinkEnabledAt is when the operator last turned the sink on. Returns how many intents it answered.
        public async Task<int> DrainAsync(DateTimeOffset sinkEnabledAt)
        {
            // Nothing is in flight at the start of a drain (execution is synchronous inside it), so an attempted
            // receipt found here belongs to a run that never finished.
            foreach (var attempt in ledger.AttemptedReceipts())
            {
                await publishReceipt(Receipt(attempt.commandId, attempt.requestedBy, InterruptedStatus,
                    "The editor stopped, or could not record the result, after starting this intent. It was not run "
                    + "again. Check the project, then send a new intent if it should run."));
            }

            var handled = 0;
            while (handled < MaxPerTick && ledger.TryNextPending(out var command, out var storedAt))
            {
                handled++;
                if (!DateTimeOffset.TryParse(storedAt, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var stored)
                    || stored < sinkEnabledAt)
                {
                    await publishReceipt(Receipt(command, ExpiredStatus,
                        "This intent was stored before the command sink was last enabled, so the operator never saw "
                        + "it. It was not run."));
                    continue;
                }

                var admission = policy.Decide(command);
                if (!admission.Allowed)
                {
                    var denied = admission.DeniedReceipt(command);
                    denied.requestedBy = command.requestedBy;
                    await publishReceipt(denied);
                    continue;
                }

                // Durable before any effect: a crash after this line leaves the marker, never a second run.
                await publishReceipt(Receipt(command, AttemptedStatus, "Started; no result recorded yet."));
                var receipt = execute(command);
                receipt.commandId = command.commandId;
                receipt.requestedBy = command.requestedBy;
                await publishReceipt(receipt);
            }

            return handled;
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
