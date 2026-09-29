#nullable disable
using System;
using System.Threading.Tasks;
using GameCult.Caching;

namespace GameCult.Brokkr
{
    // The drain's real store: every write the editor makes to the command lane is one CultCache commit, so what the
    // scenario harness runs is the code the editor ships. A commit costs one record write per record and no more;
    // durability is FlushAsync, which batches share.
    public sealed class BrokkrCommandStore : IBrokkrCommandStore
    {
        private readonly CultCache cache;

        public BrokkrCommandStore(CultCache cache)
        {
            this.cache = cache ?? throw new ArgumentNullException(nameof(cache));
        }

        public Task PutReceiptAsync(BrokkrUnityCommandReceipt receipt)
        {
            if (string.IsNullOrWhiteSpace(receipt.commandId))
            {
                throw new ArgumentException("A receipt must name the command it answers.", nameof(receipt));
            }

            return Commit(batch => batch.Upsert(
                receipt, new CultRecordHandle<BrokkrUnityCommandReceipt>(BrokkrCommandLedger.ReceiptKey(receipt.commandId))));
        }

        public Task DeleteReceiptAsync(string commandId) =>
            Commit(batch => batch.Remove(BrokkrCommandLedger.ReceiptKey(commandId)));

        // Conditional on the store being exactly what this cache has observed (CultCacheBatch.ExpectUnchanged): an
        // intent that landed since the caller's pull makes the commit refuse, and false comes back so the caller
        // pulls and recomputes. Flush first; a store with staged writes cannot take a conditional commit.
        public Task<bool> TryCommitEnableAsync(BrokkrUnityCommandReceipt[] expired, BrokkrSinkEnabled marker)
        {
            var committed = cache.Commit(batch =>
            {
                foreach (var receipt in expired)
                {
                    batch.Upsert(receipt, new CultRecordHandle<BrokkrUnityCommandReceipt>(BrokkrCommandLedger.ReceiptKey(receipt.commandId)));
                }

                batch.Upsert(marker, new CultRecordHandle<BrokkrSinkEnabled>(BrokkrCommandLedger.SinkKey));
                batch.ExpectUnchanged();
            });
            return Task.FromResult(committed);
        }

        public Task DeleteAnsweredAsync(string[] commandIds) => Commit(batch =>
        {
            foreach (var commandId in commandIds)
            {
                batch.Remove(BrokkrCommandLedger.CommandKey(commandId));
                batch.Remove(BrokkrCommandLedger.ReceiptKey(commandId));
            }
        });

        public Task FlushAsync() => cache.FlushAsync();

        private Task Commit(Action<CultCacheBatch> stage) =>
            cache.Commit(stage) ? Task.CompletedTask : throw new InvalidOperationException("The store refused the commit.");
    }
}
