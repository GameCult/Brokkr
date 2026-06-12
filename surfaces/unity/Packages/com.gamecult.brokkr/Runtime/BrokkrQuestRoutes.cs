using System;
using GameCult.Caching;
using MessagePack;

namespace GameCult.Brokkr
{
    [CultDocument("brokkr.unity.quest_route", "brokkr.unity.quest_route.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrQuestRoute
    {
        [Key(0)] public string id = "";
        [Key(1)] public string owner = "";
        [Key(2)] public string source = "";
        [Key(3)] public string sink = "";
        [Key(4)] public string schema = "";
        [Key(5)] public string transport = "";
        [Key(6)] public string direction = "";
        [Key(7)] public string[] notes = Array.Empty<string>();
    }

    [CultDocument("brokkr.unity.warped_video_frame", "brokkr.unity.warped_video_frame.v0")]
    [MessagePackObject]
    [Serializable]
    public sealed class BrokkrUnityWarpedVideoFrame
    {
        [Key(0)] public string schema = "brokkr.unity.warped_video_frame.v0";
        [Key(1)] public string frameId = "";
        [Key(2)] public string sourceId = "brokkr.unity_editor:playmode-warped-frame";
        [Key(3)] public string targetStreamId = "";
        [Key(4)] public long presentedAtNs;
        [Key(5)] public int width;
        [Key(6)] public int height;
        [Key(7)] public string pixelFormat = "";
        [Key(8)] public string colorSpace = "";
        [Key(9)] public string warpProfileId = "";
        [Key(10)] public string payloadTransport = "";
        [Key(11)] public string payloadHandle = "";
    }
}
