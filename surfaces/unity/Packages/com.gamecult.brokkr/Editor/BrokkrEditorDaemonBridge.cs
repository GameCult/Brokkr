using System;
using UnityEditor;

namespace GameCult.Brokkr.Editor
{
    [InitializeOnLoad]
    public static class BrokkrEditorDaemonBridge
    {
        private static string AutoStartKey => $"GameCult.Brokkr.AutoStartMirror.{UnityEngine.Application.dataPath}";
        private static readonly BrokkrCultMeshMirror Mirror = new();
        private static double nextPollAt;
        private static bool startQueued;
        private static bool starting;

        static BrokkrEditorDaemonBridge()
        {
            Register();
        }

        [InitializeOnLoadMethod]
        public static void InitializeDaemonBridge()
        {
            Register();
            EditorApplication.delayCall += EnsureStarted;
        }

        private static void Register()
        {
            EditorApplication.update -= OnEditorUpdate;
            EditorApplication.update += OnEditorUpdate;
        }

        private static bool AutoStart
        {
            get => EditorPrefs.GetBool(AutoStartKey, true);
            set => EditorPrefs.SetBool(AutoStartKey, value);
        }

        [MenuItem("GameCult/Brokkr/Start Daemon Bridge")]
        public static void StartDaemonBridge()
        {
            AutoStart = true;
            EnsureStarted();
        }

        [MenuItem("GameCult/Brokkr/Stop Daemon Bridge")]
        public static void StopDaemonBridge()
        {
            AutoStart = false;
            Mirror.Dispose();
        }

        private static async void EnsureStarted()
        {
            if (!AutoStart || starting || Mirror.IsRunning)
            {
                return;
            }

            starting = true;
            try
            {
                BrokkrSettings.AutoPollCommands = true;
                UnityEngine.Debug.Log($"Brokkr daemon bridge starting at {BrokkrSettings.CultMeshCachePath}");
                await Mirror.StartAsync(BrokkrSettings.CultMeshCachePath);
                await PublishSnapshot();
                UnityEngine.Debug.Log($"Brokkr daemon bridge started at {Mirror.CachePath}");
            }
            catch (Exception error)
            {
                UnityEngine.Debug.LogWarning($"Brokkr daemon bridge failed to start: {error.Message}");
            }
            finally
            {
                starting = false;
            }
        }

        private static void OnEditorUpdate()
        {
            if (!AutoStart)
            {
                return;
            }

            if (!Mirror.IsRunning)
            {
                if (!startQueued)
                {
                    startQueued = true;
                    EditorApplication.delayCall += () =>
                    {
                        startQueued = false;
                        EnsureStarted();
                    };
                }

                return;
            }

            if (EditorApplication.timeSinceStartup < nextPollAt)
            {
                return;
            }

            nextPollAt = EditorApplication.timeSinceStartup + 1.0;
            Mirror.PullExternalUpdatesAsync().GetAwaiter().GetResult();
            DrainCommands();
            DrainSyncReceipts();
        }

        private static void DrainCommands()
        {
            while (Mirror.TryDequeueCommand(out var command) && command != null)
            {
                if (string.IsNullOrWhiteSpace(command.commandId))
                {
                    continue;
                }

                var receipt = BrokkrUnityCommandExecutor.Execute(command);
                Mirror.PublishReceiptAsync(receipt).GetAwaiter().GetResult();
                PublishSnapshot().GetAwaiter().GetResult();
            }
        }

        private static void DrainSyncReceipts()
        {
            while (Mirror.TryDequeueSyncReceipt(out _))
            {
            }
        }

        private static async System.Threading.Tasks.Task PublishSnapshot()
        {
            if (!Mirror.IsRunning)
            {
                return;
            }

            await Mirror.PublishSnapshotAsync(BrokkrUnitySnapshotBuilder.Capture());
        }
    }
}
