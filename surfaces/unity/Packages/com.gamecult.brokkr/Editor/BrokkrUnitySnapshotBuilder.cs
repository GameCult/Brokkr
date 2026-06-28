using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
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

        internal static BrokkrUnityPrefabMirrorSnapshot CapturePrefabMirror(
            string prefabAssetPath,
            string blenderCollectionName)
        {
            if (string.IsNullOrWhiteSpace(prefabAssetPath))
            {
                throw new InvalidOperationException("Enter a prefab asset path before mirroring to Blender.");
            }

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabAssetPath.Trim());
            if (prefab == null)
            {
                throw new InvalidOperationException($"Prefab was not found: {prefabAssetPath}");
            }

            var nodes = new List<BrokkrUnityPrefabNodeSnapshot>();
            var assets = new Dictionary<string, BrokkrUnityPrefabAssetRequirement>(StringComparer.Ordinal);
            CapturePrefabNode(prefab, "", prefab.name, nodes, assets);

            var observedAt = DateTime.UtcNow.ToString("O");
            var prefabId = AssetDatabase.AssetPathToGUID(prefabAssetPath);
            var snapshot = new BrokkrUnityPrefabMirrorSnapshot
            {
                prefabId = string.IsNullOrWhiteSpace(prefabId) ? prefab.name : prefabId,
                prefabAssetPath = prefabAssetPath.Trim(),
                prefabName = prefab.name,
                blenderCollectionName = string.IsNullOrWhiteSpace(blenderCollectionName)
                    ? prefab.name
                    : blenderCollectionName.Trim(),
                observedAt = observedAt,
                nodes = nodes.ToArray(),
                assets = assets.Values
                    .OrderBy(asset => asset.assetId, StringComparer.Ordinal)
                    .ToArray()
            };
            snapshot.contentHash = ComputePrefabMirrorHash(snapshot);
            snapshot.snapshotId = StableId("unity-prefab", snapshot.prefabId, snapshot.contentHash.Substring(0, 16));
            return snapshot;
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
                components = CaptureComponents(gameObject),
                localPosition = WriteVector3(gameObject.transform.localPosition),
                localEulerAngles = WriteVector3(gameObject.transform.localEulerAngles),
                localScale = WriteVector3(gameObject.transform.localScale),
                materialNames = CaptureMaterialNames(gameObject)
            });

            for (var childIndex = 0; childIndex < gameObject.transform.childCount; childIndex++)
            {
                var child = gameObject.transform.GetChild(childIndex).gameObject;
                CaptureGameObject(child, scene, $"{path}/{child.name}", objectId, objects);
            }
        }

        private static void CapturePrefabNode(
            GameObject gameObject,
            string parentNodeId,
            string path,
            ICollection<BrokkrUnityPrefabNodeSnapshot> nodes,
            IDictionary<string, BrokkrUnityPrefabAssetRequirement> assets)
        {
            var nodeId = StableId("node", path);
            var meshAssetId = CaptureMeshRequirement(gameObject, assets);
            var materialAssetIds = CaptureMaterialRequirements(gameObject, assets);
            nodes.Add(new BrokkrUnityPrefabNodeSnapshot
            {
                nodeId = nodeId,
                parentNodeId = parentNodeId,
                name = gameObject.name,
                path = path,
                activeSelf = gameObject.activeSelf,
                tag = gameObject.tag,
                layer = gameObject.layer,
                localPosition = WriteVector3(gameObject.transform.localPosition),
                localEulerAngles = WriteVector3(gameObject.transform.localEulerAngles),
                localScale = WriteVector3(gameObject.transform.localScale),
                meshAssetId = meshAssetId,
                materialAssetIds = materialAssetIds,
                components = CaptureComponents(gameObject)
            });

            for (var childIndex = 0; childIndex < gameObject.transform.childCount; childIndex++)
            {
                var child = gameObject.transform.GetChild(childIndex).gameObject;
                CapturePrefabNode(child, nodeId, $"{path}/{child.name}", nodes, assets);
            }
        }

        private static string CaptureMeshRequirement(
            GameObject gameObject,
            IDictionary<string, BrokkrUnityPrefabAssetRequirement> assets)
        {
            var mesh = gameObject.GetComponent<MeshFilter>()?.sharedMesh;
            if (mesh == null)
            {
                var skinned = gameObject.GetComponent<SkinnedMeshRenderer>();
                mesh = skinned != null ? skinned.sharedMesh : null;
            }

            return mesh == null ? "" : AddAssetRequirement(assets, "mesh", mesh);
        }

        private static string[] CaptureMaterialRequirements(
            GameObject gameObject,
            IDictionary<string, BrokkrUnityPrefabAssetRequirement> assets)
        {
            var renderer = gameObject.GetComponent<Renderer>();
            if (renderer == null)
            {
                return Array.Empty<string>();
            }

            var result = new List<string>();
            foreach (var material in renderer.sharedMaterials.Where(material => material != null))
            {
                var materialId = AddAssetRequirement(assets, "material", material);
                result.Add(materialId);
                CaptureTextureRequirements(material, assets);
            }

            return result.ToArray();
        }

        private static void CaptureTextureRequirements(
            Material material,
            IDictionary<string, BrokkrUnityPrefabAssetRequirement> assets)
        {
            var shader = material.shader;
            if (shader == null)
            {
                return;
            }

            var propertyCount = ShaderUtil.GetPropertyCount(shader);
            for (var index = 0; index < propertyCount; index++)
            {
                if (ShaderUtil.GetPropertyType(shader, index) != ShaderUtil.ShaderPropertyType.TexEnv)
                {
                    continue;
                }

                var propertyName = ShaderUtil.GetPropertyName(shader, index);
                var texture = material.GetTexture(propertyName);
                if (texture != null)
                {
                    AddAssetRequirement(assets, "texture", texture);
                }
            }
        }

        private static string AddAssetRequirement(
            IDictionary<string, BrokkrUnityPrefabAssetRequirement> assets,
            string role,
            UnityEngine.Object asset)
        {
            var path = AssetDatabase.GetAssetPath(asset);
            var guid = string.IsNullOrWhiteSpace(path) ? "" : AssetDatabase.AssetPathToGUID(path);
            var assetId = StableId(role, string.IsNullOrWhiteSpace(guid) ? asset.name : guid);
            if (!assets.ContainsKey(assetId))
            {
                assets[assetId] = new BrokkrUnityPrefabAssetRequirement
                {
                    assetId = assetId,
                    role = role,
                    unityAssetPath = path,
                    guid = guid,
                    name = asset.name,
                    typeName = asset.GetType().FullName
                };
            }

            return assetId;
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

        private static string[] CaptureMaterialNames(GameObject gameObject)
        {
            var renderer = gameObject.GetComponent<Renderer>();
            return renderer == null
                ? Array.Empty<string>()
                : renderer.sharedMaterials
                    .Where(material => material != null)
                    .Select(material => material.name)
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
                        isPrefab = path.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase),
                        isScriptableObject = type != null && typeof(ScriptableObject).IsAssignableFrom(type),
                        name = System.IO.Path.GetFileNameWithoutExtension(path)
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

        private static string WriteVector3(Vector3 value)
        {
            return string.Join(
                ",",
                value.x.ToString(CultureInfo.InvariantCulture),
                value.y.ToString(CultureInfo.InvariantCulture),
                value.z.ToString(CultureInfo.InvariantCulture));
        }

        private static string ComputePrefabMirrorHash(BrokkrUnityPrefabMirrorSnapshot snapshot)
        {
            var builder = new StringBuilder();
            builder.Append(snapshot.prefabId).Append('\u001F')
                .Append(snapshot.prefabAssetPath).Append('\u001F')
                .Append(snapshot.prefabName).Append('\u001F')
                .Append(snapshot.blenderCollectionName).Append('\u001F');
            foreach (var node in snapshot.nodes.OrderBy(node => node.nodeId, StringComparer.Ordinal))
            {
                builder.Append(node.nodeId).Append('\u001E')
                    .Append(node.parentNodeId).Append('\u001E')
                    .Append(node.path).Append('\u001E')
                    .Append(node.localPosition).Append('\u001E')
                    .Append(node.localEulerAngles).Append('\u001E')
                    .Append(node.localScale).Append('\u001E')
                    .Append(node.meshAssetId).Append('\u001E')
                    .Append(string.Join(",", node.materialAssetIds.OrderBy(value => value, StringComparer.Ordinal)))
                    .Append('\u001F');
            }

            foreach (var asset in snapshot.assets.OrderBy(asset => asset.assetId, StringComparer.Ordinal))
            {
                builder.Append(asset.assetId).Append('\u001E')
                    .Append(asset.role).Append('\u001E')
                    .Append(asset.unityAssetPath).Append('\u001E')
                    .Append(asset.guid).Append('\u001F');
            }

            using var sha256 = SHA256.Create();
            return string.Concat(sha256
                .ComputeHash(Encoding.UTF8.GetBytes(builder.ToString()))
                .Select(value => value.ToString("x2", CultureInfo.InvariantCulture)));
        }

        private static string StableId(params string[] parts)
        {
            return string.Join(":", parts.Select(part => (part ?? "")
                .Replace(" ", "_")
                .Replace("/", "_")
                .Replace("\\", "_")));
        }
    }
}
