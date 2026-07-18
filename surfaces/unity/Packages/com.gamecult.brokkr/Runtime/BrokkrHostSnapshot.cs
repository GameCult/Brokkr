using System;
using GameCult.Caching;
using MessagePack;

namespace GameCult.Brokkr
{
    [CultDocument("brokkr.unity.host_snapshot", "brokkr.unity.host_snapshot.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrHostSnapshot
    {
        [Key(0)] public string schema = "gamecult.brokkr.tool_host_snapshot.v0";
        [Key(1)] public string providerId = "brokkr.unity_editor";
        [Key(2)] public string toolKind = "unity-editor";
        [Key(3)] public string projectPath = "";
        [Key(4)] public string observedAt = "";
        [Key(5)] public string unityVersion = "";
        [Key(6)] public string productName = "";
        [Key(7)] public string activeScenePath = "";
        [Key(8)] public int openSceneCount;
        [Key(9)] public string[] selectedObjectNames = Array.Empty<string>();
        [Key(10)] public int assetCount;
        [Key(11)] public string[] capabilities = Array.Empty<string>();
        [Key(12)] public BrokkrGameObjectSnapshot[] sceneObjects = Array.Empty<BrokkrGameObjectSnapshot>();
        [Key(13)] public BrokkrAssetSnapshot[] assets = Array.Empty<BrokkrAssetSnapshot>();
        [Key(14)] public bool isPlaying;
        [Key(15)] public bool isPaused;
        [Key(16)] public bool isCompiling;
        [Key(17)] public bool isUpdating;
    }

    [CultDocument("brokkr.unity.snapshot_receipt", "brokkr.unity.snapshot_receipt.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrSnapshotReceipt
    {
        [Key(0)] public string schema = "";
        [Key(1)] public string providerId = "";
        [Key(2)] public string toolKind = "";
        [Key(3)] public string acceptedAt = "";
        [Key(4)] public string status = "";
    }

    [CultDocument("brokkr.unity.prefab_mirror_snapshot", "brokkr.unity.prefab_mirror_snapshot.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrUnityPrefabMirrorSnapshot
    {
        [Key(0)] public string schema = "brokkr.unity.prefab_mirror_snapshot.v0";
        [Key(1)] public string snapshotId = "";
        [Key(2)] public string providerId = "brokkr.unity_editor";
        [Key(3)] public string sourceTool = "unity-editor";
        [Key(4)] public string prefabId = "";
        [Key(5)] public string prefabAssetPath = "";
        [Key(6)] public string prefabName = "";
        [Key(7)] public string blenderCollectionName = "";
        [Key(8)] public string observedAt = "";
        [Key(9)] public string contentHash = "";
        [Key(10)] public BrokkrUnityPrefabNodeSnapshot[] nodes = Array.Empty<BrokkrUnityPrefabNodeSnapshot>();
        [Key(11)] public BrokkrUnityPrefabAssetRequirement[] assets = Array.Empty<BrokkrUnityPrefabAssetRequirement>();
    }

    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrUnityPrefabNodeSnapshot
    {
        [Key(0)] public string nodeId = "";
        [Key(1)] public string parentNodeId = "";
        [Key(2)] public string name = "";
        [Key(3)] public string path = "";
        [Key(4)] public bool activeSelf;
        [Key(5)] public string tag = "";
        [Key(6)] public int layer;
        [Key(7)] public string localPosition = "";
        [Key(8)] public string localEulerAngles = "";
        [Key(9)] public string localScale = "";
        [Key(10)] public string meshAssetId = "";
        [Key(11)] public string[] materialAssetIds = Array.Empty<string>();
        [Key(12)] public BrokkrComponentSnapshot[] components = Array.Empty<BrokkrComponentSnapshot>();
    }

    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrUnityPrefabAssetRequirement
    {
        [Key(0)] public string assetId = "";
        [Key(1)] public string role = "";
        [Key(2)] public string unityAssetPath = "";
        [Key(3)] public string guid = "";
        [Key(4)] public string name = "";
        [Key(5)] public string typeName = "";
    }

    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrGameObjectSnapshot
    {
        [Key(0)] public string objectId = "";
        [Key(1)] public string name = "";
        [Key(2)] public string path = "";
        [Key(3)] public string scenePath = "";
        [Key(4)] public bool activeSelf;
        [Key(5)] public string tag = "";
        [Key(6)] public int layer;
        [Key(7)] public int childCount;
        [Key(8)] public string parentId = "";
        [Key(9)] public BrokkrComponentSnapshot[] components = Array.Empty<BrokkrComponentSnapshot>();
        [Key(10)] public string localPosition = "";
        [Key(11)] public string localEulerAngles = "";
        [Key(12)] public string localScale = "";
        [Key(13)] public string[] materialNames = Array.Empty<string>();
    }

    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrComponentSnapshot
    {
        [Key(0)] public string componentId = "";
        [Key(1)] public string typeName = "";
        [Key(2)] public string assemblyQualifiedName = "";
        [Key(3)] public bool enabled;
        [Key(4)] public BrokkrSerializedPropertySnapshot[] properties = Array.Empty<BrokkrSerializedPropertySnapshot>();
    }

    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrSerializedPropertySnapshot
    {
        [Key(0)] public string path = "";
        [Key(1)] public string displayName = "";
        [Key(2)] public string propertyType = "";
        [Key(3)] public string value = "";
        [Key(4)] public bool editable;
    }

    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrAssetSnapshot
    {
        [Key(0)] public string path = "";
        [Key(1)] public string guid = "";
        [Key(2)] public string typeName = "";
        [Key(3)] public bool isPrefab;
        [Key(4)] public bool isScriptableObject;
        [Key(5)] public string name = "";
    }

    [CultDocument("brokkr.unity.command_intent", "brokkr.unity.command_intent.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrUnityCommand
    {
        [Key(0)] public string schema = "gamecult.brokkr.unity_command.v0";
        [Key(1)] public string commandId = "";
        [Key(2)] public string action = "";
        [Key(3)] public string targetObjectId = "";
        [Key(4)] public string name = "";
        [Key(5)] public string componentType = "";
        [Key(6)] public string propertyPath = "";
        [Key(7)] public string value = "";
        [Key(8)] public string assetPath = "";
        [Key(9)] public string parentObjectId = "";
        [Key(10)] public string localPosition = "";
        [Key(11)] public string localEulerAngles = "";
        [Key(12)] public string localScale = "";
        [Key(13)] public string viewKind = "";
        [Key(14)] public string outputPath = "";
        [Key(15)] public int width;
        [Key(16)] public int height;
    }

    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrUnityCommandEnvelope
    {
        [Key(0)] public BrokkrUnityCommand command;
    }

    [CultDocument("brokkr.unity.command_receipt", "brokkr.unity.command_receipt.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrUnityCommandReceipt
    {
        [Key(0)] public string schema = "gamecult.brokkr.unity_command_receipt.v0";
        [Key(1)] public string commandId = "";
        [Key(2)] public string status = "";
        [Key(3)] public string message = "";
        [Key(4)] public string objectId = "";
        [Key(5)] public string observedAt = "";
    }
}
