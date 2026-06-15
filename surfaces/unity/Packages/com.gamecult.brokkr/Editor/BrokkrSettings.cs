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

        internal static string SyncSessionId
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.SyncSessionId", "default");
            set => EditorPrefs.SetString("GameCult.Brokkr.SyncSessionId", value);
        }

        internal static string SyncDisplayName
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.SyncDisplayName", "Brokkr Editor Sync");
            set => EditorPrefs.SetString("GameCult.Brokkr.SyncDisplayName", value);
        }

        internal static string BlenderObjectName
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.BlenderObjectName", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.BlenderObjectName", value);
        }

        internal static string BlenderCollectionName
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.BlenderCollectionName", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.BlenderCollectionName", value);
        }

        internal static string BlenderSceneName
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.BlenderSceneName", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.BlenderSceneName", value);
        }

        internal static string UnityTimelineObjectId
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.UnityTimelineObjectId", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.UnityTimelineObjectId", value);
        }

        internal static string UnityCinemachineObjectId
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.UnityCinemachineObjectId", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.UnityCinemachineObjectId", value);
        }

        internal static string BlenderActionName
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.BlenderActionName", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.BlenderActionName", value);
        }

        internal static string UnityCustomPropertyComponentType
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.UnityCustomPropertyComponentType", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.UnityCustomPropertyComponentType", value);
        }

        internal static string UnityCustomPropertyPath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.UnityCustomPropertyPath", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.UnityCustomPropertyPath", value);
        }

        internal static string BlenderCustomPropertyPath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.BlenderCustomPropertyPath", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.BlenderCustomPropertyPath", value);
        }

        internal static string UnityComponentPropertyComponentType
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.UnityComponentPropertyComponentType", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.UnityComponentPropertyComponentType", value);
        }

        internal static string UnityComponentPropertyPath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.UnityComponentPropertyPath", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.UnityComponentPropertyPath", value);
        }

        internal static string BlenderComponentPropertyPath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.BlenderComponentPropertyPath", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.BlenderComponentPropertyPath", value);
        }

        internal static string ScriptableObjectType
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.ScriptableObjectType", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.ScriptableObjectType", value);
        }

        internal static string ScriptableObjectName
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.ScriptableObjectName", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.ScriptableObjectName", value);
        }

        internal static string ScriptableObjectAssetPath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.ScriptableObjectAssetPath", "Assets/BrokkrAsset.asset");
            set => EditorPrefs.SetString("GameCult.Brokkr.ScriptableObjectAssetPath", value);
        }

        internal static string PrefabAssetPath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.PrefabAssetPath", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.PrefabAssetPath", value);
        }

        internal static string PrefabInstanceName
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.PrefabInstanceName", "");
            set => EditorPrefs.SetString("GameCult.Brokkr.PrefabInstanceName", value);
        }

        internal static string PrefabVariantPath
        {
            get => EditorPrefs.GetString("GameCult.Brokkr.PrefabVariantPath", "Assets/BrokkrPrefabVariant.prefab");
            set => EditorPrefs.SetString("GameCult.Brokkr.PrefabVariantPath", value);
        }
    }
}
