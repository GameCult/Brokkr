using System;
using GameCult.Brokkr;
using UnityEditor;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    public sealed class BrokkrWindow : EditorWindow
    {
        private string brokerUri = BrokkrSettings.DefaultBrokerUri;
        private string cultMeshCachePath = "";
        private bool autoPublish;
        private bool autoPollCommands;
        private BrokkrHostSnapshot lastSnapshot;
        private string lastReceipt = "No snapshot published yet.";
        private MessageType lastMessageType = MessageType.Info;
        private double nextPollAt;
        private BrokkrCultMeshMirror mirror;

        [MenuItem("GameCult/Brokkr")]
        public static void Open()
        {
            GetWindow<BrokkrWindow>("Brokkr");
        }

        private void OnEnable()
        {
            brokerUri = BrokkrSettings.BrokerUri;
            cultMeshCachePath = BrokkrSettings.CultMeshCachePath;
            autoPublish = BrokkrSettings.AutoPublish;
            autoPollCommands = BrokkrSettings.AutoPollCommands;
            Selection.selectionChanged += Repaint;
            EditorSceneManagerBridge.SceneDirtied += OnEditorSignal;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
            EditorApplication.update += OnEditorUpdate;
        }

        private void OnDisable()
        {
            Selection.selectionChanged -= Repaint;
            EditorSceneManagerBridge.SceneDirtied -= OnEditorSignal;
            EditorApplication.playModeStateChanged -= OnPlayModeChanged;
            EditorApplication.update -= OnEditorUpdate;
            mirror?.Dispose();
            mirror = null;
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Provider", BrokkrSettings.ProviderId);
            EditorGUILayout.LabelField("Tool Kind", BrokkrSettings.ToolKind);
            brokerUri = EditorGUILayout.TextField("Broker URI", brokerUri);
            cultMeshCachePath = EditorGUILayout.TextField("CultMesh Cache", cultMeshCachePath);
            autoPublish = EditorGUILayout.Toggle("Auto Publish", autoPublish);
            autoPollCommands = EditorGUILayout.Toggle("Auto Poll Commands", autoPollCommands);

            if (GUILayout.Button("Save Settings"))
            {
                BrokkrSettings.BrokerUri = brokerUri;
                BrokkrSettings.CultMeshCachePath = cultMeshCachePath;
                BrokkrSettings.AutoPublish = autoPublish;
                BrokkrSettings.AutoPollCommands = autoPollCommands;
                SetStatus("Settings saved.", MessageType.Info);
            }

            EditorGUILayout.Space();
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Start CultMesh Mirror"))
                {
                    StartMirror();
                }

                if (GUILayout.Button("Publish Mirror"))
                {
                    PublishSnapshot();
                }
            }

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Capture Snapshot"))
                {
                    CaptureSnapshot();
                }

                if (GUILayout.Button("Poll Mirror Command"))
                {
                    PollAndExecuteCommand(false);
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.HelpBox(lastReceipt, lastMessageType);

            if (lastSnapshot != null)
            {
                EditorGUILayout.LabelField("Observed At", lastSnapshot.observedAt);
                EditorGUILayout.LabelField("Project", lastSnapshot.productName);
                EditorGUILayout.LabelField("Path", lastSnapshot.projectPath);
                EditorGUILayout.LabelField("Active Scene", lastSnapshot.activeScenePath);
                EditorGUILayout.LabelField("Open Scenes", lastSnapshot.openSceneCount.ToString());
                EditorGUILayout.LabelField("Assets", lastSnapshot.assetCount.ToString());
                EditorGUILayout.LabelField("Scene Objects", lastSnapshot.sceneObjects.Length.ToString());
                EditorGUILayout.LabelField("Selection", string.Join(", ", lastSnapshot.selectedObjectNames));
            }
        }

        private void CaptureSnapshot()
        {
            lastSnapshot = BrokkrUnitySnapshotBuilder.Capture();
            SetStatus("Captured Unity editor host snapshot.", MessageType.Info);
        }

        private void PublishSnapshot()
        {
            try
            {
                if (lastSnapshot == null)
                {
                    lastSnapshot = BrokkrUnitySnapshotBuilder.Capture();
                }

                RequireMirror();
                mirror.PublishSnapshotAsync(lastSnapshot).GetAwaiter().GetResult();
                SetStatus($"Mirrored Unity snapshot: {lastSnapshot.observedAt}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private async void StartMirror()
        {
            try
            {
                mirror ??= new BrokkrCultMeshMirror();
                await mirror.StartAsync(cultMeshCachePath);
                SetStatus($"CultMesh mirror running: {mirror.CachePath}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PollAndExecuteCommand(bool quiet)
        {
            try
            {
                RequireMirror();
                if (!mirror.TryDequeueCommand(out var command) || string.IsNullOrEmpty(command.commandId))
                {
                    if (!quiet)
                    {
                        SetStatus("No queued CultMesh Unity command.", MessageType.Info);
                    }

                    return;
                }

                var receipt = BrokkrUnityCommandExecutor.Execute(command);
                mirror.PublishReceiptAsync(receipt).GetAwaiter().GetResult();
                lastSnapshot = BrokkrUnitySnapshotBuilder.Capture();
                mirror.PublishSnapshotAsync(lastSnapshot).GetAwaiter().GetResult();
                SetStatus($"Command {receipt.status}: {receipt.commandId} {receipt.message}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void OnEditorSignal()
        {
            if (autoPublish)
            {
                CaptureSnapshot();
                PublishSnapshot();
            }
            else
            {
                Repaint();
            }
        }

        private void OnPlayModeChanged(PlayModeStateChange _)
        {
            OnEditorSignal();
        }

        private void OnEditorUpdate()
        {
            if (!autoPollCommands || EditorApplication.timeSinceStartup < nextPollAt)
            {
                return;
            }

            nextPollAt = EditorApplication.timeSinceStartup + 1.0;
            PollAndExecuteCommand(true);
        }

        private void RequireMirror()
        {
            if (mirror == null || !mirror.IsRunning)
            {
                throw new InvalidOperationException("Start the Brokkr CultMesh mirror first.");
            }
        }

        private void SetStatus(string message, MessageType messageType)
        {
            lastReceipt = message;
            lastMessageType = messageType;
            Repaint();
        }
    }
}
