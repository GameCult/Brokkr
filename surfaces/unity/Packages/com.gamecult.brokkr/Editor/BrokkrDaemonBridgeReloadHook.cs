using UnityEditor.Callbacks;

namespace GameCult.Brokkr.Editor
{
    public static class BrokkrDaemonBridgeReloadHook
    {
        [DidReloadScripts]
        public static void StartAfterScriptsReload()
        {
            BrokkrEditorDaemonBridge.InitializeDaemonBridge();
        }
    }
}
