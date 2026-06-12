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
        private BrokkrHostSnapshot lastSnapshot;
        private string lastReceipt = "No snapshot published yet.";
        private MessageType lastMessageType = MessageType.Info;

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
            Selection.selectionChanged += Repaint;
            EditorSceneManagerBridge.SceneDirtied += OnEditorSignal;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
        }

        private void OnDisable()
        {
            Selection.selectionChanged -= Repaint;
            EditorSceneManagerBridge.SceneDirtied -= OnEditorSignal;
            EditorApplication.playModeStateChanged -= OnPlayModeChanged;
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Provider", BrokkrSettings.ProviderId);
            EditorGUILayout.LabelField("Tool Kind", BrokkrSettings.ToolKind);
            brokerUri = EditorGUILayout.TextField("Broker URI", brokerUri);
            httpEndpoint = EditorGUILayout.TextField("HTTP Endpoint", httpEndpoint);
            autoPublish = EditorGUILayout.Toggle("Auto Publish", autoPublish);

            if (GUILayout.Button("Save Settings"))
            {
                BrokkrSettings.BrokerUri = brokerUri;
                BrokkrSettings.HttpEndpoint = httpEndpoint;
                BrokkrSettings.AutoPublish = autoPublish;
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

            if (GUILayout.Button("Ping Brokkr"))
            {
                PingBroker();
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

        private void SetStatus(string message, MessageType messageType)
        {
            lastReceipt = message;
            lastMessageType = messageType;
            Repaint();
        }
    }
}
