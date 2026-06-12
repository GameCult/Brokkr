using System;
using GameCult.Brokkr;
using UnityEditor;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    public sealed class BrokkrWindow : EditorWindow
    {
        private string brokerUri = BrokkrSettings.DefaultBrokerUri;
        private string httpEndpoint = BrokkrSettings.DefaultHttpEndpoint;
        private bool autoPublish;
        private bool autoPollCommands;
        private BrokkrHostSnapshot lastSnapshot;
        private string lastReceipt = "No snapshot published yet.";
        private MessageType lastMessageType = MessageType.Info;
        private double nextPollAt;

        [MenuItem("GameCult/Brokkr")]
        public static void Open()
        {
            GetWindow<BrokkrWindow>("Brokkr");
        }

        private void OnEnable()
        {
            brokerUri = BrokkrSettings.BrokerUri;
            httpEndpoint = BrokkrSettings.HttpEndpoint;
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
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Provider", BrokkrSettings.ProviderId);
            EditorGUILayout.LabelField("Tool Kind", BrokkrSettings.ToolKind);
            brokerUri = EditorGUILayout.TextField("Broker URI", brokerUri);
            httpEndpoint = EditorGUILayout.TextField("HTTP Endpoint", httpEndpoint);
            autoPublish = EditorGUILayout.Toggle("Auto Publish", autoPublish);
            autoPollCommands = EditorGUILayout.Toggle("Auto Poll Commands", autoPollCommands);

            if (GUILayout.Button("Save Settings"))
            {
                BrokkrSettings.BrokerUri = brokerUri;
                BrokkrSettings.HttpEndpoint = httpEndpoint;
                BrokkrSettings.AutoPublish = autoPublish;
                BrokkrSettings.AutoPollCommands = autoPollCommands;
                SetStatus("Settings saved.", MessageType.Info);
            }

            EditorGUILayout.Space();
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Capture Snapshot"))
                {
                    CaptureSnapshot();
                }

                if (GUILayout.Button("Publish Snapshot"))
                {
                    PublishSnapshot();
                }
            }

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Ping Brokkr"))
                {
                    PingBroker();
                }

                if (GUILayout.Button("Poll Command"))
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

                var receipt = BrokkrBrokerClient.PublishUnitySnapshot(httpEndpoint, lastSnapshot);
                SetStatus($"Snapshot {receipt.status}: {receipt.acceptedAt}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PingBroker()
        {
            try
            {
                var health = BrokkrBrokerClient.GetHealth(httpEndpoint);
                SetStatus(health, MessageType.Info);
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
                var command = BrokkrBrokerClient.GetNextUnityCommand(httpEndpoint);
                if (command == null || string.IsNullOrEmpty(command.commandId))
                {
                    if (!quiet)
                    {
                        SetStatus("No queued Unity command.", MessageType.Info);
                    }

                    return;
                }

                var receipt = BrokkrUnityCommandExecutor.Execute(command);
                BrokkrBrokerClient.PublishUnityCommandReceipt(httpEndpoint, receipt);
                lastSnapshot = BrokkrUnitySnapshotBuilder.Capture();
                BrokkrBrokerClient.PublishUnitySnapshot(httpEndpoint, lastSnapshot);
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

        private void SetStatus(string message, MessageType messageType)
        {
            lastReceipt = message;
            lastMessageType = messageType;
            Repaint();
        }
    }
}
