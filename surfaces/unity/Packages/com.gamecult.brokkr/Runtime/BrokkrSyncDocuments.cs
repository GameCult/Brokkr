using System;
using GameCult.Caching;
using MessagePack;

namespace GameCult.Brokkr
{
    [CultDocument("brokkr.sync.session", "brokkr.sync.session.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrSyncSession
    {
        [Key(0)] public string schema = "brokkr.sync.session.v0";
        [Key(1)] public string sessionId = "";
        [Key(2)] public string displayName = "";
        [Key(3)] public string owner = "brokkr.creative_tool_broker";
        [Key(4)] public string unityProviderId = "brokkr.unity_editor";
        [Key(5)] public string blenderProviderId = "brokkr.blender_editor";
        [Key(6)] public string mode = "manual";
        [Key(7)] public bool enabled;
        [Key(8)] public string createdAt = "";
        [Key(9)] public string updatedAt = "";
    }

    [CultDocument("brokkr.sync.object_binding", "brokkr.sync.object_binding.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrSyncObjectBinding
    {
        [Key(0)] public string schema = "brokkr.sync.object_binding.v0";
        [Key(1)] public string bindingId = "";
        [Key(2)] public string sessionId = "";
        [Key(3)] public string displayName = "";
        [Key(4)] public string unityObjectId = "";
        [Key(5)] public string unityPath = "";
        [Key(6)] public string blenderObjectName = "";
        [Key(7)] public string blenderCollectionName = "";
        [Key(8)] public bool enabled;
        [Key(9)] public string authority = "unity-to-blender";
        [Key(10)] public string updatedAt = "";
    }

    [CultDocument("brokkr.sync.var", "brokkr.sync.var.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrSyncVar
    {
        [Key(0)] public string schema = "brokkr.sync.var.v0";
        [Key(1)] public string syncVarId = "";
        [Key(2)] public string sessionId = "";
        [Key(3)] public string bindingId = "";
        [Key(4)] public string displayName = "";
        [Key(5)] public string kind = "";
        [Key(6)] public string unityPropertyPath = "";
        [Key(7)] public string blenderPropertyPath = "";
        [Key(8)] public string authority = "unity-to-blender";
        [Key(9)] public bool enabled;
        [Key(10)] public string interpolation = "step";
        [Key(11)] public string updatedAt = "";
    }

    [CultDocument("brokkr.sync.timeline_binding", "brokkr.sync.timeline_binding.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrSyncTimelineBinding
    {
        [Key(0)] public string schema = "brokkr.sync.timeline_binding.v0";
        [Key(1)] public string bindingId = "";
        [Key(2)] public string sessionId = "";
        [Key(3)] public string displayName = "";
        [Key(4)] public string unityTimelineObjectId = "";
        [Key(5)] public string unityCinemachineObjectId = "";
        [Key(6)] public string blenderSceneName = "";
        [Key(7)] public string blenderActionName = "";
        [Key(8)] public string clockAuthority = "blender";
        [Key(9)] public float frameRate = 24.0f;
        [Key(10)] public bool syncFrame;
        [Key(11)] public bool syncCamera;
        [Key(12)] public bool enabled;
        [Key(13)] public string updatedAt = "";
    }

    [CultDocument("brokkr.sync.receipt", "brokkr.sync.receipt.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrSyncReceipt
    {
        [Key(0)] public string schema = "brokkr.sync.receipt.v0";
        [Key(1)] public string receiptId = "";
        [Key(2)] public string sessionId = "";
        [Key(3)] public string status = "";
        [Key(4)] public string message = "";
        [Key(5)] public string observedAt = "";
    }
}
