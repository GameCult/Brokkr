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

        // The operator's toggle. Enabling expires every intent already in the store and writes the enable marker in
        // one flush (BrokkrCommandDrain.EnableAsync); only then does the editor remember the token, so a failure
        // leaves the sink off.
        internal static async Task SetAgentCommandsEnabledAsync(bool enabled)
        {
            if (enabled)
            {
                await StartAsync();
                if (!MirrorInstance.IsRunning)
                {
                    throw new InvalidOperationException("The Brokkr mirror did not start; the sink stays off.");
                }

                await MirrorInstance.PullExternalUpdatesAsync();
                var token = Guid.NewGuid().ToString("N");
                var expired = await NewDrain().EnableAsync(token);
                BrokkrSettings.EnableAgentCommands(token);
                Debug.Log($"Brokkr command sink enabled; {expired} waiting intent(s) expired unrun.");
            }
            else
            {
                BrokkrSettings.DisableAgentCommands();
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

            var token = BrokkrSettings.AgentCommandsToken;
            if (token.Length == 0 || EditorApplication.timeSinceStartup < nextPullAt)
            {
                return;
            }

            nextPullAt = EditorApplication.timeSinceStartup + PullIntervalSeconds;
            try
            {
                MirrorInstance.PullExternalUpdatesAsync().GetAwaiter().GetResult();
                var handled = NewDrain().DrainAsync(token).GetAwaiter().GetResult();
                if (handled == BrokkrCommandDrain.NotAuthorized)
                {
                    // The store in front of us was not enabled by this editor (re-clone, copied .brokkr, replaced
                    // store). The stale token authorizes nothing: drop it and make the operator enable again.
                    BrokkrSettings.DisableAgentCommands();
                    Debug.LogWarning("Brokkr command sink turned off: this project's store carries no enable marker "
                                     + "from this editor. Enable Agent Commands again to run intents from it.");
                    PublishSnapshotAsync().GetAwaiter().GetResult();
                }
                else if (handled > 0)
                {
                    PublishSnapshotAsync().GetAwaiter().GetResult();
                }
            }
            catch (Exception error)
            {
                Debug.LogWarning($"Brokkr editor service tick failed: {error.Message}");
            }
        }

        // Every rule about whether and when an intent runs lives in BrokkrCommandDrain; this only supplies the
        // executor and the store.
        private static BrokkrCommandDrain NewDrain()
        {
            var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return new BrokkrCommandDrain(
                MirrorInstance.Ledger,
                new BrokkrCommandPolicy(projectRoot, BrokkrSettings.AllowedAgentActions),
                BrokkrUnityCommandExecutor.Execute,
                MirrorInstance);
        }
    }
}
