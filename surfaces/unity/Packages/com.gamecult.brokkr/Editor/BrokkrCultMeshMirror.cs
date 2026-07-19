using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using GameCult.Caching;
using GameCult.Caching.MessagePack;
using GameCult.Mesh;
using GameCult.Networking;
using R3;
using UnityEditor;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    internal sealed class BrokkrCultMeshMirror : IDisposable
    {
        private readonly Queue<BrokkrUnityCommand> commandQueue = new();
        private readonly Queue<BrokkrSyncReceipt> syncReceiptQueue = new();
        private readonly HashSet<string> queuedCommandIds = new(StringComparer.Ordinal);
        private readonly HashSet<string> completedCommandIds = new(StringComparer.Ordinal);
        private CultMeshNode node;
        private IDisposable commandSubscription;
        private IDisposable syncReceiptSubscription;

        internal bool IsRunning => node != null;
        internal string CachePath { get; private set; } = "";

        internal async Task StartAsync(string cachePath)
        {
            if (node != null)
            {
                return;
            }

            CachePath = cachePath;
            Directory.CreateDirectory(Path.GetDirectoryName(cachePath) ?? ".");

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

            commandQueue.Clear();
            queuedCommandIds.Clear();
            completedCommandIds.Clear();
            RefreshCommandState();

            commandSubscription = node.Database
                .Watch<BrokkrUnityCommand>()
                .Subscribe(change =>
                {
                    if (change.Document != null)
                        TryQueueCommand(change.Document);
                });
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

        internal async Task PublishSnapshotAsync(BrokkrHostSnapshot snapshot)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey("unity/host/current"), snapshot);
            await node.FlushAsync(soft: true);
        }

        internal async Task PullExternalUpdatesAsync()
        {
            RequireRunning();
            await node.Cache.PullAllBackingStoresAsync();
            RefreshCommandState();
        }

        internal async Task PublishPrefabMirrorSnapshotAsync(BrokkrUnityPrefabMirrorSnapshot snapshot)
        {
            RequireRunning();
            var key = string.IsNullOrWhiteSpace(snapshot.snapshotId)
                ? $"prefabs/unity-mirrors/{Guid.NewGuid():N}"
                : $"prefabs/unity-mirrors/{snapshot.snapshotId}";
            await node.Database.PutAsync(new CultRecordKey(key), snapshot);
            await node.FlushAsync(soft: true);
        }

        internal async Task PublishReceiptAsync(BrokkrUnityCommandReceipt receipt)
        {
            RequireRunning();
            var key = string.IsNullOrWhiteSpace(receipt.commandId)
                ? $"unity/receipts/{Guid.NewGuid():N}"
                : $"unity/receipts/{receipt.commandId}";
            await node.Database.PutAsync(new CultRecordKey(key), receipt);
            await node.FlushAsync(soft: true);
            if (!string.IsNullOrWhiteSpace(receipt.commandId))
            {
                completedCommandIds.Add(receipt.commandId);
                queuedCommandIds.Remove(receipt.commandId);
            }
        }

        internal async Task PublishCommandAsync(BrokkrUnityCommand command)
        {
            RequireRunning();
            var commandId = string.IsNullOrWhiteSpace(command.commandId)
                ? Guid.NewGuid().ToString("N")
                : command.commandId;
            command.commandId = commandId;
            await node.Database.PutAsync(new CultRecordKey($"unity/commands/{commandId}"), command);
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

        internal bool TryDequeueCommand(out BrokkrUnityCommand command)
        {
            while (commandQueue.Count > 0)
            {
                var candidate = commandQueue.Dequeue();
                queuedCommandIds.Remove(candidate.commandId);
                if (HasReceipt(candidate.commandId))
                {
                    continue;
                }

                command = candidate;
                return true;
            }

            command = null;
            return false;
        }

        private void RefreshCommandState()
        {
            var documents = node.Database.Cache.AllStoredDocuments.ToArray();
            foreach (var receipt in documents
                         .Select(stored => stored.Document)
                         .OfType<BrokkrUnityCommandReceipt>())
            {
                if (!string.IsNullOrWhiteSpace(receipt.commandId))
                    completedCommandIds.Add(receipt.commandId);
            }

            foreach (var command in documents
                         .Where(stored => stored.Document is BrokkrUnityCommand)
                         .OrderBy(stored => stored.StoredAt, StringComparer.Ordinal)
                         .ThenBy(stored => stored.Key.Value, StringComparer.Ordinal)
                         .Select(stored => (BrokkrUnityCommand)stored.Document))
                TryQueueCommand(command);
        }

        private void TryQueueCommand(BrokkrUnityCommand command)
        {
            if (string.IsNullOrWhiteSpace(command.commandId) ||
                HasReceipt(command.commandId) ||
                !queuedCommandIds.Add(command.commandId))
                return;
            commandQueue.Enqueue(command);
        }

        private bool HasReceipt(string commandId)
        {
            if (node == null || string.IsNullOrWhiteSpace(commandId))
            {
                return false;
            }

            return completedCommandIds.Contains(commandId);
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

        internal BrokkrSyncPolicyView SnapshotSyncPolicy()
        {
            RequireRunning();
            var documents = node.Database.Cache.AllStoredDocuments
                .Select(stored => stored.Document)
                .ToArray();
            return new BrokkrSyncPolicyView
            {
                objectBindings = documents
                    .OfType<BrokkrSyncObjectBinding>()
                    .OrderBy(binding => binding.displayName, StringComparer.Ordinal)
                    .ToArray(),
                timelineBindings = documents
                    .OfType<BrokkrSyncTimelineBinding>()
                    .OrderBy(binding => binding.displayName, StringComparer.Ordinal)
                    .ToArray(),
                syncVars = documents
                    .OfType<BrokkrSyncVar>()
                    .OrderBy(syncVar => syncVar.bindingId, StringComparer.Ordinal)
                    .ThenBy(syncVar => syncVar.displayName, StringComparer.Ordinal)
                    .ToArray()
            };
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
            commandSubscription?.Dispose();
            commandSubscription = null;
            syncReceiptSubscription?.Dispose();
            syncReceiptSubscription = null;
            node?.Dispose();
            node = null;
        }
    }

    internal sealed class BrokkrSyncPolicyView
    {
        internal BrokkrSyncObjectBinding[] objectBindings = Array.Empty<BrokkrSyncObjectBinding>();
        internal BrokkrSyncTimelineBinding[] timelineBindings = Array.Empty<BrokkrSyncTimelineBinding>();
        internal BrokkrSyncVar[] syncVars = Array.Empty<BrokkrSyncVar>();
    }
}
