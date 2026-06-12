using System;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;

namespace GameCult.Brokkr.Editor
{
    internal static class EditorSceneManagerBridge
    {
        internal static event Action SceneDirtied;

        static EditorSceneManagerBridge()
        {
            EditorSceneManager.activeSceneChangedInEditMode += OnActiveSceneChanged;
            EditorSceneManager.sceneSaved += OnSceneSaved;
            EditorSceneManager.sceneOpened += OnSceneOpened;
            EditorSceneManager.sceneClosed += OnSceneClosed;
        }

        private static void OnActiveSceneChanged(Scene previous, Scene next)
        {
            SceneDirtied?.Invoke();
        }

        private static void OnSceneSaved(Scene scene)
        {
            SceneDirtied?.Invoke();
        }

        private static void OnSceneOpened(Scene scene, OpenSceneMode mode)
        {
            SceneDirtied?.Invoke();
        }

        private static void OnSceneClosed(Scene scene)
        {
            SceneDirtied?.Invoke();
        }
    }
}
