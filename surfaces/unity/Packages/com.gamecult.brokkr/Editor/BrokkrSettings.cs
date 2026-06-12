using UnityEditor;

namespace GameCult.Brokkr.Editor
{
    internal static class BrokkrSettings
    {
        internal const string ProviderId = "brokkr.unity_editor";
        internal const string ToolKind = "unity-editor";
        internal const string DefaultBrokerUri = "cultmesh://brokkr";

        internal static string BrokerUri
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.BrokerUri", DefaultBrokerUri);
            set => EditorPrefs.SetString("GameCult.Brokkr.BrokerUri", value);
        }
    }
}

