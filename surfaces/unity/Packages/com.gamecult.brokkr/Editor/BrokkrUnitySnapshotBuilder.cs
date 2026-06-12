using System;
using System.Linq;
using GameCult.Brokkr;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    internal static class BrokkrUnitySnapshotBuilder
    {
        private static readonly string[] Capabilities =
        {
            "host.status.read",
            "scene.tree.read",
            "selection.read",
            "asset.catalog.read",
            "command.palette.read",
            "command.execute",
            "receipt.read"
        };

        internal static BrokkrHostSnapshot Capture()
        {
            return new BrokkrHostSnapshot
            {
                projectPath = Application.dataPath.Replace("/Assets", ""),
                observedAt = DateTime.UtcNow.ToString("O"),
                unityVersion = Application.unityVersion,
                productName = Application.productName,
                activeScenePath = EditorSceneManager.GetActiveScene().path,
                openSceneCount = EditorSceneManager.sceneCount,
                selectedObjectNames = Selection.objects
                    .Where(item => item != null)
                    .Select(item => item.name)
                    .ToArray(),
                assetCount = AssetDatabase.GetAllAssetPaths().Length,
                capabilities = Capabilities
            };
        }
    }
}
