using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using GameCult.Caching;
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
        private CultMeshNode node;
        private IDisposable commandSubscription;

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

            node = await CultMesh.StartNodeAsync(cachePath, new CultMeshNodeOptions
            {
                EnableDurableShardLogs = true,
                DatabaseOptions = new CultNetDatabaseOptions
                {
                    RuntimeId = "brokkr-unity-editor"
                }
            });

            commandSubscription = node.Database
                .Watch<BrokkrUnityCommand>()
                .Subscribe(change =>
                {
                    if (change.Document != null)
                    {
                        commandQueue.Enqueue(change.Document);
                    }
                });
        }

        internal async Task PublishSnapshotAsync(BrokkrHostSnapshot snapshot)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey("unity/host/current"), snapshot);
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
        }

        internal async Task PublishQuestRouteAsync(BrokkrQuestRoute route)
        {
            RequireRunning();
            await node.Database.PutAsync(new CultRecordKey($"unity/quest-routes/{route.id}"), route);
            await node.FlushAsync(soft: true);
        }

        internal bool TryDequeueCommand(out BrokkrUnityCommand command)
        {
            if (commandQueue.Count > 0)
            {
                command = commandQueue.Dequeue();
                return true;
            }

            command = null;
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
            commandSubscription?.Dispose();
            commandSubscription = null;
            node?.Dispose();
            node = null;
        }
    }
}
