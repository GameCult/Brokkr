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

        internal static bool AutoPublish
        {
            get => EditorPrefs.GetBool("GameCult.Brokkr.AutoPublish", false);
            set => EditorPrefs.SetBool("GameCult.Brokkr.AutoPublish", value);
        }

        internal static bool AutoPollCommands
        {
            get => EditorPrefs.GetBool("GameCult.Brokkr.AutoPollCommands", false);
            set => EditorPrefs.SetBool("GameCult.Brokkr.AutoPollCommands", value);
        }

        internal static string CultMeshCachePath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.CultMeshCachePath", BrokkrCultMeshMirror.DefaultCachePath());
            set => EditorPrefs.SetString("GameCult.Brokkr.CultMeshCachePath", value);
        }
    }
}
