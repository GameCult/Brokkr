using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using GameCult.Caching;
using GameCult.Caching.MessagePack;
using GameCult.Mesh;
using GameCult.Networking;
using R3;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    // The one open handle on the project's directory store. BrokkrEditorService owns the only instance; the window
    // publishes through it and never opens the store itself.
    internal sealed class BrokkrCultMeshMirror : IDisposable
    {
        private readonly Queue<BrokkrSyncReceipt> syncReceiptQueue = new();
        private CultMeshNode node;
        private IDisposable syncReceiptSubscription;

        internal bool IsRunning => node != null;
        internal string CachePath { get; private set; } = "";
        internal BrokkrCommandLedger Ledger { get; private set; }

        internal async Task StartAsync(string cachePath)
        {
            if (node != null)
            {
                return;
            }

            CachePath = cachePath;
            Directory.CreateDirectory(Path.GetDirectoryName(cachePath) ?? ".");

            // File transport: no listener, no endpoint. Other processes reach the editor through the store and are
            // seen on the next pull.
            node = await CultMesh.CreateNodeAsync(cachePath, new CultMeshNodeOptions
            {
                StartServer = false,
                CacheOptions = new CultCacheOpenOptions
                {
                    UseDirectoryStore = true
                },
                EnableDurableShardLogs = true,
                DatabaseOptions = new CultNetDatabaseOptions
                {
                    RuntimeId = "brokkr-unity-editor"
                }
            });
            Ledger = new BrokkrCommandLedger(node.Cache);

            syncReceiptSubscription = node.Database
                .Watch<BrokkrSyncReceipt>()
                .Subscribe(change =>
                {
                    if (change.Document != null)
                    {
                        syncReceiptQueue.Enqueue(change.Document);
                    }
                });
        }

        internal async Task PullExternalUpdatesAsync()
        {
            RequireRunning();
            await Ledger.PullAsync();
        }

        internal async Task PublishSnapshotAsync(BrokkrHostSnapshot snapshot)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey("unity/host/current"), snapshot);
            await node.FlushAsync(soft: true);
        }

        // The receipt is the only proof an intent ran, and it is keyed by the intent it answers.
        internal async Task PublishReceiptAsync(BrokkrUnityCommandReceipt receipt)
        {
            RequireRunning();
            if (string.IsNullOrWhiteSpace(receipt.commandId))
            {
                throw new ArgumentException("A receipt must name the command it answers.", nameof(receipt));
            }

            await node.Database.PutAsync(BrokkrCommandLedger.ReceiptKey(receipt.commandId), receipt);
            await node.FlushAsync(soft: true);
        }

        // Command ids are single-use: a caller with no id gets a fresh one, and reusing an answered id is a defect.
        internal async Task PublishCommandAsync(BrokkrUnityCommand command)
        {
            RequireRunning();
            if (string.IsNullOrWhiteSpace(command.commandId))
            {
                command.commandId = Guid.NewGuid().ToString("N");
            }

            await node.Database.PutAsync(BrokkrCommandLedger.CommandKey(command.commandId), command);
            await node.FlushAsync(soft: true);
        }

        internal async Task PublishQuestRouteAsync(BrokkrQuestRoute route)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey($"unity/quest-routes/{route.id}"), route);
            await node.FlushAsync(soft: true);
        }

        internal async Task PublishSyncSessionAsync(BrokkrSyncSession session)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey($"sync/sessions/{session.sessionId}"), session);
            await node.FlushAsync(soft: true);
        }

        internal async Task PublishSyncObjectBindingAsync(BrokkrSyncObjectBinding binding)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey($"sync/bindings/objects/{binding.bindingId}"), binding);
            await node.FlushAsync(soft: true);
        }

        internal async Task PublishSyncVarAsync(BrokkrSyncVar syncVar)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey($"sync/vars/{syncVar.syncVarId}"), syncVar);
            await node.FlushAsync(soft: true);
        }

        internal async Task PublishTimelineBindingAsync(BrokkrSyncTimelineBinding binding)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey($"sync/bindings/timelines/{binding.bindingId}"), binding);
            await node.FlushAsync(soft: true);
        }

        internal bool TryDequeueSyncReceipt(out BrokkrSyncReceipt receipt)
        {
            if (syncReceiptQueue.Count > 0)
            {
                receipt = syncReceiptQueue.Dequeue();
                return true;
            }

            receipt = null;
            return false;
        }

        internal static string DefaultCachePath()
        {
            var projectRoot = Application.dataPath.Replace("/Assets", "");
            return Path.Combine(projectRoot, ".brokkr", "unity-editor.ccmp");
        }

        private void RequireRunning()
        {
            if (node == null)
            {
                throw new InvalidOperationException("Brokkr CultMesh mirror is not running.");
            }
        }

        public void Dispose()
        {
            syncReceiptSubscription?.Dispose();
            syncReceiptSubscription = null;
            node?.Dispose();
            node = null;
            Ledger = null;
        }
    }
}
