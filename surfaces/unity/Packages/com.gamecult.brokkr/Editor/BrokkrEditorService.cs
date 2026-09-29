using System;
using System.IO;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    // The only owner of command execution in the editor. It owns the mirror, the pull cadence and the drain; the
    // window is a caller (it writes intents) and a display (it reads state from here). Nothing else calls
    // BrokkrCommandLedger.TryNextPending or BrokkrUnityCommandExecutor.Execute (both go through BrokkrCommandDrain).
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

        // The only writer of unity/host/current. It captures fresh every time, so the published flags always
        // describe the editor now; the window asks for a publish and never carries a snapshot of its own to the
        // store. Returns what it published, or null when the mirror is not running.
        internal static async Task<BrokkrHostSnapshot> PublishSnapshotAsync()
        {
            if (!MirrorInstance.IsRunning)
            {
                return null;
            }

            var snapshot = BrokkrUnitySnapshotBuilder.Capture();
            await MirrorInstance.PublishSnapshotAsync(snapshot);
            return snapshot;
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

            var enabledSince = BrokkrSettings.AgentCommandsEnabledSince;
            if (enabledSince == null || EditorApplication.timeSinceStartup < nextPullAt)
            {
                return;
            }

            nextPullAt = EditorApplication.timeSinceStartup + PullIntervalSeconds;
            try
            {
                MirrorInstance.PullExternalUpdatesAsync().GetAwaiter().GetResult();
                DrainCommands(enabledSince.Value);
            }
            catch (Exception error)
            {
                Debug.LogWarning($"Brokkr editor service tick failed: {error.Message}");
            }
        }

        // Every rule about whether and when an intent runs lives in BrokkrCommandDrain; this only supplies the
        // executor and the receipt writer.
        private static void DrainCommands(DateTimeOffset enabledSince)
        {
            var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            var drain = new BrokkrCommandDrain(
                MirrorInstance.Ledger,
                new BrokkrCommandPolicy(projectRoot, BrokkrSettings.AllowedAgentActions),
                BrokkrUnityCommandExecutor.Execute,
                MirrorInstance.PublishReceiptAsync);
            if (drain.DrainAsync(enabledSince).GetAwaiter().GetResult() > 0)
            {
                PublishSnapshotAsync().GetAwaiter().GetResult();
            }
        }
    }
}
