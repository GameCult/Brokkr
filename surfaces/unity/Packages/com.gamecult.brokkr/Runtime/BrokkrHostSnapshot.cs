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
