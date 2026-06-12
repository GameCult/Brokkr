using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using GameCult.Brokkr;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace GameCult.Brokkr.Editor
{
    internal static class BrokkrUnitySnapshotBuilder
    {
        private const int MaxSerializedPropertiesPerComponent = 160;

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
                capabilities = Capabilities,
                sceneObjects = CaptureSceneObjects(),
                assets = CaptureAssets()
            };
        }

        private static BrokkrGameObjectSnapshot[] CaptureSceneObjects()
        {
            var objects = new List<BrokkrGameObjectSnapshot>();

            for (var sceneIndex = 0; sceneIndex < EditorSceneManager.sceneCount; sceneIndex++)
            {
                var scene = EditorSceneManager.GetSceneAt(sceneIndex);
                if (!scene.isLoaded)
                {
                    continue;
                }

                foreach (var root in scene.GetRootGameObjects())
                {
                    CaptureGameObject(root, scene, root.name, "", objects);
                }
            }

            return objects.ToArray();
        }

        private static void CaptureGameObject(
            GameObject gameObject,
            Scene scene,
            string path,
            string parentId,
            ICollection<BrokkrGameObjectSnapshot> objects)
        {
            var objectId = GetObjectId(gameObject);
            objects.Add(new BrokkrGameObjectSnapshot
            {
                objectId = objectId,
                name = gameObject.name,
                path = path,
                scenePath = scene.path,
                activeSelf = gameObject.activeSelf,
                tag = gameObject.tag,
                layer = gameObject.layer,
                childCount = gameObject.transform.childCount,
                parentId = parentId,
                components = CaptureComponents(gameObject)
            });

            for (var childIndex = 0; childIndex < gameObject.transform.childCount; childIndex++)
            {
                var child = gameObject.transform.GetChild(childIndex).gameObject;
                CaptureGameObject(child, scene, $"{path}/{child.name}", objectId, objects);
            }
        }

        private static BrokkrComponentSnapshot[] CaptureComponents(GameObject gameObject)
        {
            return gameObject.GetComponents<Component>()
                .Where(component => component != null)
                .Select(component => new BrokkrComponentSnapshot
                {
                    componentId = GetObjectId(component),
                    typeName = component.GetType().FullName,
                    assemblyQualifiedName = component.GetType().AssemblyQualifiedName,
                    enabled = ReadEnabled(component),
                    properties = CaptureProperties(component)
                })
                .ToArray();
        }

        private static BrokkrSerializedPropertySnapshot[] CaptureProperties(UnityEngine.Object target)
        {
            var properties = new List<BrokkrSerializedPropertySnapshot>();
            using var serializedObject = new SerializedObject(target);
            var iterator = serializedObject.GetIterator();
            var enterChildren = true;

            while (iterator.NextVisible(enterChildren))
            {
                enterChildren = false;
                if (iterator.propertyPath == "m_Script")
                {
                    continue;
                }

                properties.Add(new BrokkrSerializedPropertySnapshot
                {
                    path = iterator.propertyPath,
                    displayName = iterator.displayName,
                    propertyType = iterator.propertyType.ToString(),
                    value = ReadPropertyValue(iterator),
                    editable = iterator.editable && !iterator.isArray
                });

                if (properties.Count >= MaxSerializedPropertiesPerComponent)
                {
                    break;
                }
            }

            return properties.ToArray();
        }

        private static BrokkrAssetSnapshot[] CaptureAssets()
        {
            return AssetDatabase.GetAllAssetPaths()
                .Where(path => path.StartsWith("Assets/", StringComparison.Ordinal))
                .Select(path =>
                {
                    var type = AssetDatabase.GetMainAssetTypeAtPath(path);
                    return new BrokkrAssetSnapshot
                    {
                        path = path,
                        guid = AssetDatabase.AssetPathToGUID(path),
                        typeName = type?.FullName ?? "",
                        isPrefab = path.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase)
                    };
                })
                .ToArray();
        }

        internal static string GetObjectId(UnityEngine.Object target)
        {
            return GlobalObjectId.GetGlobalObjectIdSlow(target).ToString();
        }

        internal static UnityEngine.Object ResolveObjectId(string objectId)
        {
            if (string.IsNullOrWhiteSpace(objectId))
            {
                return null;
            }

            return GlobalObjectId.TryParse(objectId, out var globalObjectId)
                ? GlobalObjectId.GlobalObjectIdentifierToObjectSlow(globalObjectId)
                : null;
        }

        internal static Type ResolveType(string typeName)
        {
            if (string.IsNullOrWhiteSpace(typeName))
            {
                return null;
            }

            var direct = Type.GetType(typeName);
            if (direct != null)
            {
                return direct;
            }

            return AppDomain.CurrentDomain.GetAssemblies()
                .Select(assembly => assembly.GetType(typeName))
                .FirstOrDefault(type => type != null);
        }

        private static bool ReadEnabled(Component component)
        {
            return component switch
            {
                Behaviour behaviour => behaviour.enabled,
                Renderer renderer => renderer.enabled,
                Collider collider => collider.enabled,
                _ => true
            };
        }

        private static string ReadPropertyValue(SerializedProperty property)
        {
            return property.propertyType switch
            {
                SerializedPropertyType.Integer => property.intValue.ToString(CultureInfo.InvariantCulture),
                SerializedPropertyType.Boolean => property.boolValue ? "true" : "false",
                SerializedPropertyType.Float => property.floatValue.ToString(CultureInfo.InvariantCulture),
                SerializedPropertyType.String => property.stringValue,
                SerializedPropertyType.Color => property.colorValue.ToString(),
                SerializedPropertyType.ObjectReference => property.objectReferenceValue != null
                    ? GetObjectId(property.objectReferenceValue)
                    : "",
                SerializedPropertyType.LayerMask => property.intValue.ToString(CultureInfo.InvariantCulture),
                SerializedPropertyType.Enum => property.enumDisplayNames.Length > property.enumValueIndex
                    ? property.enumDisplayNames[property.enumValueIndex]
                    : property.enumValueIndex.ToString(CultureInfo.InvariantCulture),
                SerializedPropertyType.Vector2 => property.vector2Value.ToString(),
                SerializedPropertyType.Vector3 => property.vector3Value.ToString(),
                SerializedPropertyType.Vector4 => property.vector4Value.ToString(),
                SerializedPropertyType.Rect => property.rectValue.ToString(),
                SerializedPropertyType.Bounds => property.boundsValue.ToString(),
                SerializedPropertyType.Quaternion => property.quaternionValue.eulerAngles.ToString(),
                _ => ""
            };
        }
    }
}
