using System;

namespace GameCult.Brokkr
{
    [Serializable]
    public sealed class BrokkrHostSnapshot
    {
        public string schema = "gamecult.brokkr.tool_host_snapshot.v0";
        public string providerId = "brokkr.unity_editor";
        public string toolKind = "unity-editor";
        public string projectPath = "";
        public string observedAt = "";
        public string unityVersion = "";
        public string productName = "";
        public string activeScenePath = "";
        public int openSceneCount;
        public string[] selectedObjectNames = Array.Empty<string>();
        public int assetCount;
        public string[] capabilities = Array.Empty<string>();
        public BrokkrGameObjectSnapshot[] sceneObjects = Array.Empty<BrokkrGameObjectSnapshot>();
        public BrokkrAssetSnapshot[] assets = Array.Empty<BrokkrAssetSnapshot>();
    }

    [Serializable]
    public sealed class BrokkrSnapshotReceipt
    {
        public string schema = "";
        public string providerId = "";
        public string toolKind = "";
        public string acceptedAt = "";
        public string status = "";
    }

    [Serializable]
    public sealed class BrokkrGameObjectSnapshot
    {
        public string objectId = "";
        public string name = "";
        public string path = "";
        public string scenePath = "";
        public bool activeSelf;
        public string tag = "";
        public int layer;
        public int childCount;
        public string parentId = "";
        public BrokkrComponentSnapshot[] components = Array.Empty<BrokkrComponentSnapshot>();
    }

    [Serializable]
    public sealed class BrokkrComponentSnapshot
    {
        public string componentId = "";
        public string typeName = "";
        public string assemblyQualifiedName = "";
        public bool enabled;
        public BrokkrSerializedPropertySnapshot[] properties = Array.Empty<BrokkrSerializedPropertySnapshot>();
    }

    [Serializable]
    public sealed class BrokkrSerializedPropertySnapshot
    {
        public string path = "";
        public string displayName = "";
        public string propertyType = "";
        public string value = "";
        public bool editable;
    }

    [Serializable]
    public sealed class BrokkrAssetSnapshot
    {
        public string path = "";
        public string guid = "";
        public string typeName = "";
        public bool isPrefab;
    }

    [Serializable]
    public sealed class BrokkrUnityCommand
    {
        public string schema = "gamecult.brokkr.unity_command.v0";
        public string commandId = "";
        public string action = "";
        public string targetObjectId = "";
        public string name = "";
        public string componentType = "";
        public string propertyPath = "";
        public string value = "";
        public string assetPath = "";
        public string parentObjectId = "";
    }

    [Serializable]
    public sealed class BrokkrUnityCommandEnvelope
    {
        public BrokkrUnityCommand command;
    }

    [Serializable]
    public sealed class BrokkrUnityCommandReceipt
    {
        public string schema = "gamecult.brokkr.unity_command_receipt.v0";
        public string commandId = "";
        public string status = "";
        public string message = "";
        public string objectId = "";
        public string observedAt = "";
    }
}
