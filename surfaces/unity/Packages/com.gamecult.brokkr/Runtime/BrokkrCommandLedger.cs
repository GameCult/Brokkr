#nullable disable
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using GameCult.Caching;

namespace GameCult.Brokkr
{
    // Decides which Unity command intents still await execution. A command id is single-use: any receipt that
    // answers an id retires it for good, whatever is later written under that id. The ledger holds no state of its
    // own; the answer is derived from the cache on every call, so there is no second copy that could drift.
    public sealed class BrokkrCommandLedger
    {
        public const string CommandKeyPrefix = "unity/commands/";
        public const string ReceiptKeyPrefix = "unity/receipts/";

        private readonly CultCache cache;

        public BrokkrCommandLedger(CultCache cache)
        {
            this.cache = cache ?? throw new ArgumentNullException(nameof(cache));
        }

        public static CultRecordKey CommandKey(string commandId) => new CultRecordKey(CommandKeyPrefix + commandId);

        public static CultRecordKey ReceiptKey(string commandId) => new CultRecordKey(ReceiptKeyPrefix + commandId);

        public static readonly CultRecordKey SinkKey = new CultRecordKey("unity/sink/enabled");

        // Loads writes that other processes have landed in the backing store.
        public Task PullAsync() => cache.PullAllBackingStoresAsync();

        // The oldest unanswered intent by stored-at. Exact ties keep the cache's own order (schema, then key): the sort is stable.
        public bool TryNextPending(out BrokkrUnityCommand command)
        {
            var next = Pending(1);
            command = next.Length > 0 ? next[0] : null;
            return command != null;
        }

        // Up to max unanswered intents, oldest first, from one pass over the store. Stored-at only orders them; no
        // decision anywhere compares it with a clock.
        public BrokkrUnityCommand[] Pending(int max)
        {
            var stored = cache.AllStoredDocuments.ToArray();
            var answered = new HashSet<string>(
                stored.Select(entry => entry.Document).OfType<BrokkrUnityCommandReceipt>()
                    .Select(receipt => receipt.commandId)
                    .Where(id => !string.IsNullOrWhiteSpace(id)),
                StringComparer.Ordinal);

            return stored
                .Where(entry => entry.Document is BrokkrUnityCommand)
                .OrderBy(entry => entry.StoredAt, StringComparer.Ordinal)
                .Select(entry => (BrokkrUnityCommand)entry.Document)
                .Where(candidate => !string.IsNullOrWhiteSpace(candidate.commandId) && !answered.Contains(candidate.commandId))
                .Take(max)
                .ToArray();
        }

        // True when the store holds the enable marker for this token (see BrokkrCommandDrain).
        public bool SinkAuthorized(string token) =>
            !string.IsNullOrWhiteSpace(token)
            && cache.TryGet(SinkKey, out BrokkrSinkEnabled marker)
            && marker != null
            && string.Equals(marker.token, token, StringComparison.Ordinal);

        // Receipts that say an intent was started and never finished (see BrokkrCommandDrain).
        public BrokkrUnityCommandReceipt[] AttemptedReceipts() =>
            cache.AllStoredDocuments
                .Select(entry => entry.Document)
                .OfType<BrokkrUnityCommandReceipt>()
                .Where(receipt => string.Equals(receipt.status, BrokkrCommandDrain.AttemptedStatus, StringComparison.Ordinal)
                                  && !string.IsNullOrWhiteSpace(receipt.commandId))
                .ToArray();

        // The ids of the oldest answered intents beyond the newest keep receipts, at most max. Receipts are ordered by
        // their own stored-at, all minted by the editor, so one clock orders them. An attempt in flight is never listed.
        public string[] Prunable(int keep, int max)
        {
            var receipts = cache.AllStoredDocuments
                .Where(entry => entry.Document is BrokkrUnityCommandReceipt receipt
                                && !string.IsNullOrWhiteSpace(receipt.commandId)
                                && !string.Equals(receipt.status, BrokkrCommandDrain.AttemptedStatus, StringComparison.Ordinal))
                .OrderBy(entry => entry.StoredAt, StringComparer.Ordinal)
                .Select(entry => ((BrokkrUnityCommandReceipt)entry.Document).commandId)
                .ToArray();
            var excess = receipts.Length - keep;
            return excess <= 0 ? Array.Empty<string>() : receipts.Take(Math.Min(excess, max)).ToArray();
        }
    }
}
