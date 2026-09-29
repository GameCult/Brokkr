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

        // Loads writes that other processes have landed in the backing store.
        public Task PullAsync() => cache.PullAllBackingStoresAsync();

        // The oldest unanswered intent: stored-at order, then key order.
        public bool TryNextPending(out BrokkrUnityCommand command)
        {
            var stored = cache.AllStoredDocuments.ToArray();
            var answered = new HashSet<string>(
                stored.Select(entry => entry.Document).OfType<BrokkrUnityCommandReceipt>()
                    .Select(receipt => receipt.commandId)
                    .Where(id => !string.IsNullOrWhiteSpace(id)),
                StringComparer.Ordinal);

            command = stored
                .Where(entry => entry.Document is BrokkrUnityCommand)
                .OrderBy(entry => entry.StoredAt, StringComparer.Ordinal)
                .ThenBy(entry => entry.Key.Value, StringComparer.Ordinal)
                .Select(entry => (BrokkrUnityCommand)entry.Document)
                .FirstOrDefault(candidate => !string.IsNullOrWhiteSpace(candidate.commandId)
                                             && !answered.Contains(candidate.commandId));
            return command != null;
        }
    }
}
