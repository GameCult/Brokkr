using System;
using System.Globalization;
using System.Linq;
using GameCult.Brokkr;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    internal static class BrokkrUnityCommandExecutor
    {
        internal static BrokkrUnityCommandReceipt Execute(BrokkrUnityCommand command)
        {
            try
            {
                return command.action switch
                {
                    "createGameObject" => CreateGameObject(command),
                    "attachComponent" => AttachComponent(command),
                    "setGameObjectTransform" => SetGameObjectTransform(command),
                    "setComponentProperty" => SetComponentProperty(command),
                    "instantiatePrefab" => InstantiatePrefab(command),
                    "createPrefabVariant" => CreatePrefabVariant(command),
                    _ => Failed(command, $"Unsupported Unity command action: {command.action}")
                };
            }
            catch (Exception error)
            {
                return Failed(command, error.Message);
            }
        }

        private static BrokkrUnityCommandReceipt CreateGameObject(BrokkrUnityCommand command)
        {
            var gameObject = new GameObject(string.IsNullOrWhiteSpace(command.name)
                ? "Brokkr GameObject"
                : command.name);
            Undo.RegisterCreatedObjectUndo(gameObject, "Brokkr Create GameObject");
            AttachParent(gameObject, command.parentObjectId);
            EditorSceneManager.MarkSceneDirty(gameObject.scene);
            return Accepted(command, "GameObject created.", BrokkrUnitySnapshotBuilder.GetObjectId(gameObject));
        }

        private static BrokkrUnityCommandReceipt AttachComponent(BrokkrUnityCommand command)
        {
            var gameObject = ResolveGameObject(command.targetObjectId);
            if (gameObject == null)
            {
                return Failed(command, "Target GameObject was not found.");
            }

            var type = BrokkrUnitySnapshotBuilder.ResolveType(command.componentType);
            if (type == null || !typeof(Component).IsAssignableFrom(type))
            {
                return Failed(command, $"Component type is not available: {command.componentType}");
            }

            var component = Undo.AddComponent(gameObject, type);
            EditorSceneManager.MarkSceneDirty(gameObject.scene);
            return Accepted(command, "Component attached.", BrokkrUnitySnapshotBuilder.GetObjectId(component));
        }

        private static BrokkrUnityCommandReceipt SetComponentProperty(BrokkrUnityCommand command)
        {
            var target = ResolveSerializedTarget(command);
            if (target == null)
            {
                return Failed(command, "Target object was not found.");
            }

            using var serializedObject = new SerializedObject(target);
            var property = serializedObject.FindProperty(command.propertyPath);
            if (property == null)
            {
                return Failed(command, $"Serialized property was not found: {command.propertyPath}");
            }

            if (!TryWriteProperty(property, command.value, out var message))
            {
                return Failed(command, message);
            }

            serializedObject.ApplyModifiedProperties();
            EditorUtility.SetDirty(target);
            if (target is Component component)
            {
                EditorSceneManager.MarkSceneDirty(component.gameObject.scene);
            }
            else if (target is GameObject gameObject)
            {
                EditorSceneManager.MarkSceneDirty(gameObject.scene);
            }

            return Accepted(command, "Serialized property updated.", command.targetObjectId);
        }

        private static BrokkrUnityCommandReceipt SetGameObjectTransform(BrokkrUnityCommand command)
        {
            var gameObject = ResolveGameObject(command.targetObjectId);
            if (gameObject == null)
            {
                return Failed(command, "Target GameObject was not found.");
            }

            Undo.RecordObject(gameObject.transform, "Brokkr Set GameObject Transform");
            if (!string.IsNullOrWhiteSpace(command.localPosition))
            {
                if (!TryParseVector3(command.localPosition, out var localPosition))
                {
                    return Failed(command, $"Expected localPosition as x,y,z: {command.localPosition}");
                }

                gameObject.transform.localPosition = localPosition;
            }

            if (!string.IsNullOrWhiteSpace(command.localEulerAngles))
            {
                if (!TryParseVector3(command.localEulerAngles, out var localEulerAngles))
                {
                    return Failed(command, $"Expected localEulerAngles as x,y,z: {command.localEulerAngles}");
                }

                gameObject.transform.localEulerAngles = localEulerAngles;
            }

            if (!string.IsNullOrWhiteSpace(command.localScale))
            {
                if (!TryParseVector3(command.localScale, out var localScale))
                {
                    return Failed(command, $"Expected localScale as x,y,z: {command.localScale}");
                }

                gameObject.transform.localScale = localScale;
            }

            EditorSceneManager.MarkSceneDirty(gameObject.scene);
            return Accepted(command, "GameObject transform updated.", command.targetObjectId);
        }

        private static BrokkrUnityCommandReceipt InstantiatePrefab(BrokkrUnityCommand command)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(command.assetPath);
            if (prefab == null)
            {
                return Failed(command, $"Prefab was not found: {command.assetPath}");
            }

            var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            if (!string.IsNullOrWhiteSpace(command.name))
            {
                instance.name = command.name;
            }

            Undo.RegisterCreatedObjectUndo(instance, "Brokkr Instantiate Prefab");
            AttachParent(instance, command.parentObjectId);
            EditorSceneManager.MarkSceneDirty(instance.scene);
            return Accepted(command, "Prefab instantiated.", BrokkrUnitySnapshotBuilder.GetObjectId(instance));
        }

        private static BrokkrUnityCommandReceipt CreatePrefabVariant(BrokkrUnityCommand command)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(command.assetPath);
            if (prefab == null)
            {
                return Failed(command, $"Prefab was not found: {command.assetPath}");
            }

            var variantPath = command.value;
            if (string.IsNullOrWhiteSpace(variantPath))
            {
                var baseName = string.IsNullOrWhiteSpace(command.name) ? $"{prefab.name}Variant" : command.name;
                variantPath = $"Assets/{baseName}.prefab";
            }

            var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            PrefabUtility.SaveAsPrefabAsset(instance, variantPath);
            UnityEngine.Object.DestroyImmediate(instance);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            return Accepted(command, $"Prefab variant saved: {variantPath}", variantPath);
        }

        private static GameObject ResolveGameObject(string objectId)
        {
            var target = BrokkrUnitySnapshotBuilder.ResolveObjectId(objectId);
            return target switch
            {
                GameObject gameObject => gameObject,
                Component component => component.gameObject,
                _ => null
            };
        }

        private static UnityEngine.Object ResolveSerializedTarget(BrokkrUnityCommand command)
        {
            var target = BrokkrUnitySnapshotBuilder.ResolveObjectId(command.targetObjectId);
            if (target == null || string.IsNullOrWhiteSpace(command.componentType))
            {
                return target;
            }

            if (target is Component component && TypeMatches(component.GetType(), command.componentType))
            {
                return component;
            }

            var gameObject = target switch
            {
                GameObject direct => direct,
                Component owner => owner.gameObject,
                _ => null
            };
            if (gameObject == null)
            {
                return null;
            }

            var requestedType = BrokkrUnitySnapshotBuilder.ResolveType(command.componentType);
            if (requestedType != null && typeof(Component).IsAssignableFrom(requestedType))
            {
                var typedComponent = gameObject.GetComponent(requestedType);
                if (typedComponent != null)
                {
                    return typedComponent;
                }
            }

            return gameObject
                .GetComponents<Component>()
                .FirstOrDefault(candidate => candidate != null && TypeMatches(candidate.GetType(), command.componentType));
        }

        private static bool TypeMatches(Type type, string requestedType)
        {
            return string.Equals(type.FullName, requestedType, StringComparison.Ordinal)
                || string.Equals(type.Name, requestedType, StringComparison.Ordinal)
                || string.Equals(type.AssemblyQualifiedName, requestedType, StringComparison.Ordinal);
        }

        private static void AttachParent(GameObject gameObject, string parentObjectId)
        {
            var parent = ResolveGameObject(parentObjectId);
            if (parent != null)
            {
                gameObject.transform.SetParent(parent.transform);
            }
        }

        private static bool TryWriteProperty(SerializedProperty property, string value, out string message)
        {
            message = "";
            switch (property.propertyType)
            {
                case SerializedPropertyType.Integer:
                case SerializedPropertyType.LayerMask:
                    if (!int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var intValue))
                    {
                        message = $"Expected integer value for {property.propertyPath}.";
                        return false;
                    }

                    property.intValue = intValue;
                    return true;
                case SerializedPropertyType.Boolean:
                    if (!bool.TryParse(value, out var boolValue))
                    {
                        message = $"Expected boolean value for {property.propertyPath}.";
                        return false;
                    }

                    property.boolValue = boolValue;
                    return true;
                case SerializedPropertyType.Float:
                    if (!float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var floatValue))
                    {
                        message = $"Expected float value for {property.propertyPath}.";
                        return false;
                    }

                    property.floatValue = floatValue;
                    return true;
                case SerializedPropertyType.String:
                    property.stringValue = value;
                    return true;
                case SerializedPropertyType.Enum:
                    var index = Array.IndexOf(property.enumDisplayNames, value);
                    if (index < 0 && int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsedIndex))
                    {
                        index = parsedIndex;
                    }

                    if (index < 0 || index >= property.enumDisplayNames.Length)
                    {
                        message = $"Expected enum display name or index for {property.propertyPath}.";
                        return false;
                    }

                    property.enumValueIndex = index;
                    return true;
                default:
                    message = $"Property type is not writable yet: {property.propertyType}.";
                    return false;
            }
        }

        private static bool TryParseVector3(string value, out Vector3 vector)
        {
            vector = default;
            var parts = value.Split(',');
            if (parts.Length != 3)
            {
                return false;
            }

            if (!float.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var x) ||
                !float.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var y) ||
                !float.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out var z))
            {
                return false;
            }

            vector = new Vector3(x, y, z);
            return true;
        }

        private static BrokkrUnityCommandReceipt Accepted(BrokkrUnityCommand command, string message, string objectId)
        {
            return Receipt(command, "accepted", message, objectId);
        }

        private static BrokkrUnityCommandReceipt Failed(BrokkrUnityCommand command, string message)
        {
            return Receipt(command, "failed", message, "");
        }

        private static BrokkrUnityCommandReceipt Receipt(
            BrokkrUnityCommand command,
            string status,
            string message,
            string objectId)
        {
            return new BrokkrUnityCommandReceipt
            {
                commandId = command.commandId,
                status = status,
                message = message,
                objectId = objectId,
                observedAt = DateTime.UtcNow.ToString("O")
            };
        }
    }
}
