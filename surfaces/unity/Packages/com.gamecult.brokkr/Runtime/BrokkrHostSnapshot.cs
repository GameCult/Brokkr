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
}
