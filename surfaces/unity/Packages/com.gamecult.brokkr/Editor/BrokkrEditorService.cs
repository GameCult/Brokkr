using System;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    // The only owner of command execution in the editor. It owns the mirror, the pull cadence and the drain; the
    // window is a caller (it writes intents) and a display (it reads state from here). Nothing else calls
    // BrokkrCommandLedger.TryNextPending or BrokkrUnityCommandExecutor.Execute.
    //
    // The command sink is off until the operator enables it for this project (BrokkrSettings.AgentCommandsEnabled).
    // Loading the package opens no store and executes nothing.
    [InitializeOnLoad]
    internal static class BrokkrEditorService
    {
        private const double PullIntervalSeconds = 1.0;

        private static readonly BrokkrCultMeshMirror MirrorInstance = new BrokkrCultMeshMirror();
        private static double nextPullAt;
        private static bool starting;

        static BrokkrEditorService()
        {
            // [InitializeOnLoad] runs again after every domain reload, so this is the only registration.
            EditorApplication.update += Tick;
            AssemblyReloadEvents.beforeAssemblyReload += MirrorInstance.Dispose;
            EditorApplication.quitting += MirrorInstance.Dispose;
            if (BrokkrSettings.AgentCommandsEnabled)
            {
                EditorApplication.delayCall += () => _ = StartAsync();
            }
        }

        internal static BrokkrCultMeshMirror Mirror => MirrorInstance;

        // The newest sync receipt seen; display only.
        internal static BrokkrSyncReceipt LastSyncReceipt { get; private set; }

        internal static async Task StartAsync()
        {
            if (starting || MirrorInstance.IsRunning)
            {
                return;
            }

            starting = true;
            try
            {
                await MirrorInstance.StartAsync(BrokkrSettings.CultMeshCachePath);
                await PublishSnapshotAsync();
            }
            catch (Exception error)
            {
                Debug.LogWarning($"Brokkr editor service failed to start: {error.Message}");
            }
            finally
            {
                starting = false;
            }
        }

        internal static async Task SetAgentCommandsEnabledAsync(bool enabled)
        {
            BrokkrSettings.AgentCommandsEnabled = enabled;
            if (enabled)
            {
                await StartAsync();
            }

            // The snapshot carries the flag, so a caller can see why nothing executes.
            await PublishSnapshotAsync();
        }

        internal static async Task PublishSnapshotAsync()
        {
            if (MirrorInstance.IsRunning)
            {
                await MirrorInstance.PublishSnapshotAsync(BrokkrUnitySnapshotBuilder.Capture());
            }
        }

        private static void Tick()
        {
            if (!MirrorInstance.IsRunning)
            {
                return;
            }

            while (MirrorInstance.TryDequeueSyncReceipt(out var syncReceipt))
            {
                LastSyncReceipt = syncReceipt;
            }

            if (!BrokkrSettings.AgentCommandsEnabled || EditorApplication.timeSinceStartup < nextPullAt)
            {
                return;
            }

            nextPullAt = EditorApplication.timeSinceStartup + PullIntervalSeconds;
            try
            {
                MirrorInstance.PullExternalUpdatesAsync().GetAwaiter().GetResult();
                DrainCommands();
            }
            catch (Exception error)
            {
                Debug.LogWarning($"Brokkr editor service tick failed: {error.Message}");
            }
        }

        private static void DrainCommands()
        {
            var drained = false;
            while (MirrorInstance.Ledger.TryNextPending(out var command))
            {
                var receipt = BrokkrUnityCommandExecutor.Execute(command);
                // The receipt answers exactly the id it ran, or the ledger would offer the intent again.
                receipt.commandId = command.commandId;
                MirrorInstance.PublishReceiptAsync(receipt).GetAwaiter().GetResult();
                drained = true;
            }

            if (drained)
            {
                PublishSnapshotAsync().GetAwaiter().GetResult();
            }
        }
    }
}
