using UnityEditor;

namespace GameCult.Brokkr.Editor
{
    public sealed class BrokkrDaemonBridgePostprocessor : AssetPostprocessor
    {
        private static void OnPostprocessAllAssets(
            string[] importedAssets,
            string[] deletedAssets,
            string[] movedAssets,
            string[] movedFromAssetPaths)
        {
            BrokkrEditorDaemonBridge.InitializeDaemonBridge();
        }
    }
}
