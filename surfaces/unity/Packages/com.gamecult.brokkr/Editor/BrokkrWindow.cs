using UnityEditor;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    public sealed class BrokkrWindow : EditorWindow
    {
        private string brokerUri = BrokkrSettings.DefaultBrokerUri;

        [MenuItem("GameCult/Brokkr")]
        public static void Open()
        {
            GetWindow<BrokkrWindow>("Brokkr");
        }

        private void OnEnable()
        {
            brokerUri = BrokkrSettings.BrokerUri;
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Provider", BrokkrSettings.ProviderId);
            EditorGUILayout.LabelField("Tool Kind", BrokkrSettings.ToolKind);
            brokerUri = EditorGUILayout.TextField("Broker URI", brokerUri);

            if (GUILayout.Button("Save Settings"))
            {
                BrokkrSettings.BrokerUri = brokerUri;
            }

            EditorGUILayout.Space();
            EditorGUILayout.HelpBox(
                "Scaffold only: this adapter should publish Unity editor observations to Brokkr and execute admitted broker commands with receipts.",
                MessageType.Info);
        }
    }
}

