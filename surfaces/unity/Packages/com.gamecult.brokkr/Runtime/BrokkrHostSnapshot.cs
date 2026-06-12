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
    }
}

