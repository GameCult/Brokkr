using System;
using GameCult.Brokkr;
using UnityEditor;
using UnityEngine;

namespace GameCult.Brokkr.Editor
{
    public sealed class BrokkrWindow : EditorWindow
    {
        private string brokerUri = BrokkrSettings.DefaultBrokerUri;
        private string cultMeshCachePath = "";
        private bool autoPublish;
        private bool autoPollCommands;
        private BrokkrHostSnapshot lastSnapshot;
        private BrokkrSyncReceipt lastSyncReceipt;
        private string lastReceipt = "No snapshot published yet.";
        private MessageType lastMessageType = MessageType.Info;
        private double nextPollAt;
        private BrokkrCultMeshMirror mirror;
        private string syncSessionId = "default";
        private string syncDisplayName = "Brokkr Editor Sync";
        private string blenderObjectName = "";
        private string blenderCollectionName = "";
        private bool syncObjectEnabled = true;
        private bool syncTransform = true;
        private bool syncParent = true;
        private bool syncActiveState = true;
        private bool syncMaterial;
        private bool syncCustomProperty;
        private bool syncComponentProperty;
        private bool syncTimelineFrame = true;
        private bool syncCinemachineCamera = true;
        private float syncTimelineFrameRate = 24.0f;
        private string unityTimelineObjectId = "";
        private string unityCinemachineObjectId = "";
        private string blenderSceneName = "";
        private string blenderActionName = "";
        private string unityCustomPropertyComponentType = "";
        private string unityCustomPropertyPath = "";
        private string blenderCustomPropertyPath = "";
        private string unityComponentPropertyComponentType = "";
        private string unityComponentPropertyPath = "";
        private string blenderComponentPropertyPath = "";
        private string scriptableObjectType = "";
        private string scriptableObjectName = "";
        private string scriptableObjectAssetPath = "Assets/BrokkrAsset.asset";
        private string prefabAssetPath = "";
        private string prefabInstanceName = "";
        private string prefabVariantPath = "Assets/BrokkrPrefabVariant.prefab";
        private string adHocSyncVarBindingId = "";
        private string adHocSyncVarKind = "custom-property";
        private string adHocSyncVarDisplayName = "Custom Property";
        private string adHocSyncVarUnityPath = "";
        private string adHocSyncVarBlenderPath = "";
        private string adHocSyncVarAuthority = "blender-to-unity";
        private string adHocSyncVarInterpolation = "step";
        private bool adHocSyncVarEnabled = true;

        [MenuItem("GameCult/Brokkr")]
        public static void Open()
        {
            GetWindow<BrokkrWindow>("Brokkr");
        }

        private void OnEnable()
        {
            brokerUri = BrokkrSettings.BrokerUri;
            cultMeshCachePath = BrokkrSettings.CultMeshCachePath;
            autoPublish = BrokkrSettings.AutoPublish;
            autoPollCommands = BrokkrSettings.AutoPollCommands;
            syncSessionId = BrokkrSettings.SyncSessionId;
            syncDisplayName = BrokkrSettings.SyncDisplayName;
            blenderObjectName = BrokkrSettings.BlenderObjectName;
            blenderCollectionName = BrokkrSettings.BlenderCollectionName;
            unityTimelineObjectId = BrokkrSettings.UnityTimelineObjectId;
            unityCinemachineObjectId = BrokkrSettings.UnityCinemachineObjectId;
            blenderSceneName = BrokkrSettings.BlenderSceneName;
            blenderActionName = BrokkrSettings.BlenderActionName;
            unityCustomPropertyComponentType = BrokkrSettings.UnityCustomPropertyComponentType;
            unityCustomPropertyPath = BrokkrSettings.UnityCustomPropertyPath;
            blenderCustomPropertyPath = BrokkrSettings.BlenderCustomPropertyPath;
            unityComponentPropertyComponentType = BrokkrSettings.UnityComponentPropertyComponentType;
            unityComponentPropertyPath = BrokkrSettings.UnityComponentPropertyPath;
            blenderComponentPropertyPath = BrokkrSettings.BlenderComponentPropertyPath;
            scriptableObjectType = BrokkrSettings.ScriptableObjectType;
            scriptableObjectName = BrokkrSettings.ScriptableObjectName;
            scriptableObjectAssetPath = BrokkrSettings.ScriptableObjectAssetPath;
            prefabAssetPath = BrokkrSettings.PrefabAssetPath;
            prefabInstanceName = BrokkrSettings.PrefabInstanceName;
            prefabVariantPath = BrokkrSettings.PrefabVariantPath;
            adHocSyncVarBindingId = BrokkrSettings.AdHocSyncVarBindingId;
            adHocSyncVarKind = BrokkrSettings.AdHocSyncVarKind;
            adHocSyncVarDisplayName = BrokkrSettings.AdHocSyncVarDisplayName;
            adHocSyncVarUnityPath = BrokkrSettings.AdHocSyncVarUnityPath;
            adHocSyncVarBlenderPath = BrokkrSettings.AdHocSyncVarBlenderPath;
            adHocSyncVarAuthority = BrokkrSettings.AdHocSyncVarAuthority;
            adHocSyncVarInterpolation = BrokkrSettings.AdHocSyncVarInterpolation;
            adHocSyncVarEnabled = BrokkrSettings.AdHocSyncVarEnabled;
            Selection.selectionChanged += Repaint;
            EditorSceneManagerBridge.SceneDirtied += OnEditorSignal;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
            EditorApplication.update += OnEditorUpdate;
        }

        private void OnDisable()
        {
            Selection.selectionChanged -= Repaint;
            EditorSceneManagerBridge.SceneDirtied -= OnEditorSignal;
            EditorApplication.playModeStateChanged -= OnPlayModeChanged;
            EditorApplication.update -= OnEditorUpdate;
            mirror?.Dispose();
            mirror = null;
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Provider", BrokkrSettings.ProviderId);
            EditorGUILayout.LabelField("Tool Kind", BrokkrSettings.ToolKind);
            brokerUri = EditorGUILayout.TextField("Broker URI", brokerUri);
            cultMeshCachePath = EditorGUILayout.TextField("CultMesh Cache", cultMeshCachePath);
            autoPublish = EditorGUILayout.Toggle("Auto Publish", autoPublish);
            autoPollCommands = EditorGUILayout.Toggle("Auto Poll Commands", autoPollCommands);

            if (GUILayout.Button("Save Settings"))
            {
                BrokkrSettings.BrokerUri = brokerUri;
                BrokkrSettings.CultMeshCachePath = cultMeshCachePath;
                BrokkrSettings.AutoPublish = autoPublish;
                BrokkrSettings.AutoPollCommands = autoPollCommands;
                BrokkrSettings.SyncSessionId = syncSessionId;
                BrokkrSettings.SyncDisplayName = syncDisplayName;
                BrokkrSettings.BlenderObjectName = blenderObjectName;
                BrokkrSettings.BlenderCollectionName = blenderCollectionName;
                BrokkrSettings.UnityTimelineObjectId = unityTimelineObjectId;
                BrokkrSettings.UnityCinemachineObjectId = unityCinemachineObjectId;
                BrokkrSettings.BlenderSceneName = blenderSceneName;
                BrokkrSettings.BlenderActionName = blenderActionName;
                BrokkrSettings.UnityCustomPropertyComponentType = unityCustomPropertyComponentType;
                BrokkrSettings.UnityCustomPropertyPath = unityCustomPropertyPath;
                BrokkrSettings.BlenderCustomPropertyPath = blenderCustomPropertyPath;
                BrokkrSettings.UnityComponentPropertyComponentType = unityComponentPropertyComponentType;
                BrokkrSettings.UnityComponentPropertyPath = unityComponentPropertyPath;
                BrokkrSettings.BlenderComponentPropertyPath = blenderComponentPropertyPath;
                BrokkrSettings.ScriptableObjectType = scriptableObjectType;
                BrokkrSettings.ScriptableObjectName = scriptableObjectName;
                BrokkrSettings.ScriptableObjectAssetPath = scriptableObjectAssetPath;
                BrokkrSettings.PrefabAssetPath = prefabAssetPath;
                BrokkrSettings.PrefabInstanceName = prefabInstanceName;
                BrokkrSettings.PrefabVariantPath = prefabVariantPath;
                BrokkrSettings.AdHocSyncVarBindingId = adHocSyncVarBindingId;
                BrokkrSettings.AdHocSyncVarKind = adHocSyncVarKind;
                BrokkrSettings.AdHocSyncVarDisplayName = adHocSyncVarDisplayName;
                BrokkrSettings.AdHocSyncVarUnityPath = adHocSyncVarUnityPath;
                BrokkrSettings.AdHocSyncVarBlenderPath = adHocSyncVarBlenderPath;
                BrokkrSettings.AdHocSyncVarAuthority = adHocSyncVarAuthority;
                BrokkrSettings.AdHocSyncVarInterpolation = adHocSyncVarInterpolation;
                BrokkrSettings.AdHocSyncVarEnabled = adHocSyncVarEnabled;
                SetStatus("Settings saved.", MessageType.Info);
            }

            EditorGUILayout.Space();
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Start CultMesh Mirror"))
                {
                    StartMirror();
                }

                if (GUILayout.Button("Publish Mirror"))
                {
                    PublishSnapshot();
                }
            }

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Capture Snapshot"))
                {
                    CaptureSnapshot();
                }

                if (GUILayout.Button("Poll Mirror Command"))
                {
                    PollAndExecuteCommand(false);
                }

                if (GUILayout.Button("Poll Sync Receipt"))
                {
                    PollSyncReceipts(false);
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.HelpBox(lastReceipt, lastMessageType);
            if (lastSyncReceipt != null)
            {
                EditorGUILayout.LabelField("Last Sync Pass", $"{lastSyncReceipt.status} {lastSyncReceipt.observedAt}");
                EditorGUILayout.LabelField("Sync Session", lastSyncReceipt.sessionId);
                EditorGUILayout.HelpBox(lastSyncReceipt.message, MessageType.Info);
            }

            if (lastSnapshot != null)
            {
                EditorGUILayout.LabelField("Observed At", lastSnapshot.observedAt);
                EditorGUILayout.LabelField("Project", lastSnapshot.productName);
                EditorGUILayout.LabelField("Path", lastSnapshot.projectPath);
                EditorGUILayout.LabelField("Active Scene", lastSnapshot.activeScenePath);
                EditorGUILayout.LabelField("Open Scenes", lastSnapshot.openSceneCount.ToString());
                EditorGUILayout.LabelField("Assets", lastSnapshot.assetCount.ToString());
                EditorGUILayout.LabelField("Scene Objects", lastSnapshot.sceneObjects.Length.ToString());
                EditorGUILayout.LabelField("Selection", string.Join(", ", lastSnapshot.selectedObjectNames));
            }

            DrawAssetCommandSection();
            DrawSyncSection();
        }

        private void DrawAssetCommandSection()
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Unity Assets", EditorStyles.boldLabel);
            scriptableObjectType = EditorGUILayout.TextField("ScriptableObject Type", scriptableObjectType);
            scriptableObjectName = EditorGUILayout.TextField("Asset Name", scriptableObjectName);
            scriptableObjectAssetPath = EditorGUILayout.TextField("Asset Path", scriptableObjectAssetPath);

            if (GUILayout.Button("Create ScriptableObject Asset"))
            {
                PublishCreateScriptableObjectCommand();
            }

            EditorGUILayout.Space();
            prefabAssetPath = EditorGUILayout.TextField("Prefab Asset Path", prefabAssetPath);
            prefabInstanceName = EditorGUILayout.TextField("Instance Name", prefabInstanceName);
            prefabVariantPath = EditorGUILayout.TextField("Variant Path", prefabVariantPath);

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Instantiate Prefab"))
                {
                    PublishInstantiatePrefabCommand();
                }

                if (GUILayout.Button("Create Prefab Variant"))
                {
                    PublishCreatePrefabVariantCommand();
                }
            }
        }

        private void DrawSyncSection()
        {
            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Brokkr Sync", EditorStyles.boldLabel);
            syncSessionId = EditorGUILayout.TextField("Session Id", syncSessionId);
            syncDisplayName = EditorGUILayout.TextField("Display Name", syncDisplayName);
            blenderObjectName = EditorGUILayout.TextField("Blender Object", blenderObjectName);
            blenderCollectionName = EditorGUILayout.TextField("Blender Collection", blenderCollectionName);
            syncObjectEnabled = EditorGUILayout.Toggle("Enable Object Binding", syncObjectEnabled);
            syncTransform = EditorGUILayout.Toggle("Sync Transform", syncTransform);
            syncParent = EditorGUILayout.Toggle("Sync Parent", syncParent);
            syncActiveState = EditorGUILayout.Toggle("Sync Active State", syncActiveState);
            syncMaterial = EditorGUILayout.Toggle("Sync Material", syncMaterial);
            syncCustomProperty = EditorGUILayout.Toggle("Sync Custom Property", syncCustomProperty);
            using (new EditorGUI.DisabledScope(!syncCustomProperty))
            {
                unityCustomPropertyComponentType = EditorGUILayout.TextField("Unity Component Type", unityCustomPropertyComponentType);
                unityCustomPropertyPath = EditorGUILayout.TextField("Unity Property Path", unityCustomPropertyPath);
                blenderCustomPropertyPath = EditorGUILayout.TextField("Blender Custom Property", blenderCustomPropertyPath);
            }
            syncComponentProperty = EditorGUILayout.Toggle("Sync Component Property", syncComponentProperty);
            using (new EditorGUI.DisabledScope(!syncComponentProperty))
            {
                unityComponentPropertyComponentType = EditorGUILayout.TextField("Source Component Type", unityComponentPropertyComponentType);
                unityComponentPropertyPath = EditorGUILayout.TextField("Source Property Path", unityComponentPropertyPath);
                blenderComponentPropertyPath = EditorGUILayout.TextField("Blender Custom Property", blenderComponentPropertyPath);
            }

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Use Selected Object Name"))
                {
                    var selected = Selection.activeGameObject;
                    if (selected != null)
                    {
                        blenderObjectName = selected.name;
                    }
                }

                if (GUILayout.Button("Publish Object Sync"))
                {
                    PublishSelectedObjectSync();
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Timeline / Cinemachine", EditorStyles.boldLabel);
            unityTimelineObjectId = EditorGUILayout.TextField("Unity Timeline Object", unityTimelineObjectId);
            unityCinemachineObjectId = EditorGUILayout.TextField("Unity Cinemachine Object", unityCinemachineObjectId);
            blenderSceneName = EditorGUILayout.TextField("Blender Scene", blenderSceneName);
            blenderActionName = EditorGUILayout.TextField("Blender Action", blenderActionName);
            syncTimelineFrameRate = EditorGUILayout.FloatField("Frame Rate", syncTimelineFrameRate);
            syncTimelineFrame = EditorGUILayout.Toggle("Sync Timeline Frame", syncTimelineFrame);
            syncCinemachineCamera = EditorGUILayout.Toggle("Sync Cinemachine Camera", syncCinemachineCamera);

            if (GUILayout.Button("Publish Timeline Sync"))
            {
                PublishTimelineSync();
            }

            if (GUILayout.Button("Use Selected For Timeline/Cinemachine"))
            {
                var selected = Selection.activeGameObject;
                if (selected != null)
                {
                    var selectedId = BrokkrUnitySnapshotBuilder.GetObjectId(selected);
                    unityTimelineObjectId = selectedId;
                    unityCinemachineObjectId = selectedId;
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Ad Hoc Sync Var", EditorStyles.boldLabel);
            adHocSyncVarBindingId = EditorGUILayout.TextField("Binding Id", adHocSyncVarBindingId);
            adHocSyncVarKind = EditorGUILayout.TextField("Kind", adHocSyncVarKind);
            adHocSyncVarDisplayName = EditorGUILayout.TextField("Display Name", adHocSyncVarDisplayName);
            adHocSyncVarUnityPath = EditorGUILayout.TextField("Unity Path", adHocSyncVarUnityPath);
            adHocSyncVarBlenderPath = EditorGUILayout.TextField("Blender Path", adHocSyncVarBlenderPath);
            adHocSyncVarAuthority = EditorGUILayout.TextField("Authority", adHocSyncVarAuthority);
            adHocSyncVarInterpolation = EditorGUILayout.TextField("Interpolation", adHocSyncVarInterpolation);
            adHocSyncVarEnabled = EditorGUILayout.Toggle("Enabled", adHocSyncVarEnabled);

            if (GUILayout.Button("Publish Sync Var"))
            {
                PublishAdHocSyncVar();
            }
        }

        private void CaptureSnapshot()
        {
            lastSnapshot = BrokkrUnitySnapshotBuilder.Capture();
            SetStatus("Captured Unity editor host snapshot.", MessageType.Info);
        }

        private void PublishSnapshot()
        {
            try
            {
                if (lastSnapshot == null)
                {
                    lastSnapshot = BrokkrUnitySnapshotBuilder.Capture();
                }

                RequireMirror();
                mirror.PublishSnapshotAsync(lastSnapshot).GetAwaiter().GetResult();
                SetStatus($"Mirrored Unity snapshot: {lastSnapshot.observedAt}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private async void StartMirror()
        {
            try
            {
                mirror ??= new BrokkrCultMeshMirror();
                await mirror.StartAsync(cultMeshCachePath);
                SetStatus($"CultMesh mirror running: {mirror.CachePath}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PollAndExecuteCommand(bool quiet)
        {
            try
            {
                RequireMirror();
                if (!mirror.TryDequeueCommand(out var command) || string.IsNullOrEmpty(command.commandId))
                {
                    if (!quiet)
                    {
                        SetStatus("No queued CultMesh Unity command.", MessageType.Info);
                    }

                    return;
                }

                var receipt = BrokkrUnityCommandExecutor.Execute(command);
                mirror.PublishReceiptAsync(receipt).GetAwaiter().GetResult();
                lastSnapshot = BrokkrUnitySnapshotBuilder.Capture();
                mirror.PublishSnapshotAsync(lastSnapshot).GetAwaiter().GetResult();
                SetStatus($"Command {receipt.status}: {receipt.commandId} {receipt.message}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PollSyncReceipts(bool quiet)
        {
            try
            {
                RequireMirror();
                var sawReceipt = false;
                while (mirror.TryDequeueSyncReceipt(out var receipt) && receipt != null)
                {
                    lastSyncReceipt = receipt;
                    sawReceipt = true;
                }

                if (sawReceipt)
                {
                    Repaint();
                    return;
                }

                if (!quiet)
                {
                    SetStatus("No queued Brokkr sync receipt.", MessageType.Info);
                }
            }
            catch (Exception error)
            {
                if (!quiet)
                {
                    SetStatus(error.Message, MessageType.Error);
                }
            }
        }

        private void PublishCreateScriptableObjectCommand()
        {
            try
            {
                RequireMirror();
                if (string.IsNullOrWhiteSpace(scriptableObjectType))
                {
                    throw new InvalidOperationException("Enter a ScriptableObject type before creating an asset.");
                }

                var command = new BrokkrUnityCommand
                {
                    commandId = StableId("unity-command", "scriptable-object", Guid.NewGuid().ToString("N")),
                    action = "createScriptableObject",
                    componentType = scriptableObjectType.Trim(),
                    name = scriptableObjectName.Trim(),
                    assetPath = string.IsNullOrWhiteSpace(scriptableObjectAssetPath)
                        ? "Assets/BrokkrAsset.asset"
                        : scriptableObjectAssetPath.Trim()
                };
                PublishCommandAndPoll(command);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PublishInstantiatePrefabCommand()
        {
            try
            {
                RequireMirror();
                if (string.IsNullOrWhiteSpace(prefabAssetPath))
                {
                    throw new InvalidOperationException("Enter a prefab asset path before instantiating.");
                }

                var selected = Selection.activeGameObject;
                var command = new BrokkrUnityCommand
                {
                    commandId = StableId("unity-command", "instantiate-prefab", Guid.NewGuid().ToString("N")),
                    action = "instantiatePrefab",
                    assetPath = prefabAssetPath.Trim(),
                    name = prefabInstanceName.Trim(),
                    parentObjectId = selected != null ? BrokkrUnitySnapshotBuilder.GetObjectId(selected) : ""
                };
                PublishCommandAndPoll(command);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PublishCreatePrefabVariantCommand()
        {
            try
            {
                RequireMirror();
                if (string.IsNullOrWhiteSpace(prefabAssetPath))
                {
                    throw new InvalidOperationException("Enter a prefab asset path before creating a variant.");
                }

                var command = new BrokkrUnityCommand
                {
                    commandId = StableId("unity-command", "prefab-variant", Guid.NewGuid().ToString("N")),
                    action = "createPrefabVariant",
                    assetPath = prefabAssetPath.Trim(),
                    name = prefabInstanceName.Trim(),
                    value = string.IsNullOrWhiteSpace(prefabVariantPath)
                        ? "Assets/BrokkrPrefabVariant.prefab"
                        : prefabVariantPath.Trim()
                };
                PublishCommandAndPoll(command);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PublishCommandAndPoll(BrokkrUnityCommand command)
        {
            mirror.PublishCommandAsync(command).GetAwaiter().GetResult();
            PollAndExecuteCommand(true);
        }

        private void PublishSelectedObjectSync()
        {
            try
            {
                RequireMirror();
                var selected = Selection.activeGameObject;
                if (selected == null)
                {
                    throw new InvalidOperationException("Select a Unity GameObject before publishing object sync.");
                }

                var now = DateTime.UtcNow.ToString("O");
                var sessionId = NormalizedSyncSessionId();
                var session = BuildSyncSession(now);
                var bindingId = StableId("object", sessionId, BrokkrUnitySnapshotBuilder.GetObjectId(selected));
                var binding = new BrokkrSyncObjectBinding
                {
                    bindingId = bindingId,
                    sessionId = sessionId,
                    displayName = selected.name,
                    unityObjectId = BrokkrUnitySnapshotBuilder.GetObjectId(selected),
                    unityPath = BuildTransformPath(selected.transform),
                    blenderObjectName = string.IsNullOrWhiteSpace(blenderObjectName) ? selected.name : blenderObjectName,
                    blenderCollectionName = blenderCollectionName,
                    enabled = syncObjectEnabled,
                    authority = "unity-to-blender",
                    updatedAt = now
                };

                mirror.PublishSyncSessionAsync(session).GetAwaiter().GetResult();
                mirror.PublishSyncObjectBindingAsync(binding).GetAwaiter().GetResult();
                PublishSyncVar(bindingId, "transform", "Transform", "m_LocalPosition,m_LocalRotation,m_LocalScale", "location,rotationEuler,scale", syncTransform, "linear", now);
                PublishSyncVar(bindingId, "parent", "Parent", "parentId", "parentName", syncParent, "step", now);
                PublishSyncVar(bindingId, "active-state", "Active State", "m_IsActive", "visible", syncActiveState, "step", now);
                PublishSyncVar(bindingId, "material", "Material", "Renderer.m_Materials", "materials", syncMaterial, "step", now);
                if (syncCustomProperty)
                {
                    var unityPath = BuildUnityCustomPropertyPath();
                    var blenderPath = string.IsNullOrWhiteSpace(blenderCustomPropertyPath)
                        ? "customProperties.value"
                        : NormalizeBlenderCustomPropertyPath(blenderCustomPropertyPath);
                    PublishSyncVar(bindingId, "custom-property", "Custom Property", unityPath, blenderPath, true, "step", now);
                }
                if (syncComponentProperty)
                {
                    var unityPath = BuildUnityComponentPropertyPath();
                    var blenderPath = string.IsNullOrWhiteSpace(blenderComponentPropertyPath)
                        ? "customProperties.value"
                        : NormalizeBlenderCustomPropertyPath(blenderComponentPropertyPath);
                    PublishSyncVar(bindingId, "component-property", "Component Property", unityPath, blenderPath, true, "step", now);
                }
                SetStatus($"Published Brokkr object sync binding: {binding.displayName}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PublishTimelineSync()
        {
            try
            {
                RequireMirror();
                var now = DateTime.UtcNow.ToString("O");
                var selected = Selection.activeGameObject;
                var selectedId = selected != null ? BrokkrUnitySnapshotBuilder.GetObjectId(selected) : "";
                var sessionId = NormalizedSyncSessionId();
                var session = BuildSyncSession(now);
                var timelineObjectId = string.IsNullOrWhiteSpace(unityTimelineObjectId) ? selectedId : unityTimelineObjectId;
                var cinemachineObjectId = string.IsNullOrWhiteSpace(unityCinemachineObjectId) ? selectedId : unityCinemachineObjectId;
                var bindingId = StableId("timeline", sessionId, timelineObjectId, blenderSceneName, blenderActionName);
                var binding = new BrokkrSyncTimelineBinding
                {
                    bindingId = bindingId,
                    sessionId = sessionId,
                    displayName = string.IsNullOrWhiteSpace(blenderActionName) ? "Timeline Sync" : blenderActionName,
                    unityTimelineObjectId = timelineObjectId,
                    unityCinemachineObjectId = cinemachineObjectId,
                    blenderSceneName = blenderSceneName,
                    blenderActionName = blenderActionName,
                    clockAuthority = "blender",
                    frameRate = syncTimelineFrameRate,
                    syncFrame = syncTimelineFrame,
                    syncCamera = syncCinemachineCamera,
                    enabled = syncTimelineFrame || syncCinemachineCamera,
                    updatedAt = now
                };

                mirror.PublishSyncSessionAsync(session).GetAwaiter().GetResult();
                mirror.PublishTimelineBindingAsync(binding).GetAwaiter().GetResult();
                PublishSyncVar(bindingId, "timeline-frame", "Timeline Frame", "Timeline.time", "scene.frame_current", syncTimelineFrame, "linear", now);
                PublishSyncVar(bindingId, "cinemachine-virtual-camera", "Cinemachine Camera", "CinemachineVirtualCamera", "camera", syncCinemachineCamera, "linear", now);
                SetStatus($"Published Brokkr timeline sync binding: {binding.displayName}", MessageType.Info);
            }
            catch (Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private void PublishAdHocSyncVar()
        {
            try
            {
                RequireMirror();
                var now = System.DateTimeOffset.UtcNow.ToString("O");
                var bindingId = string.IsNullOrWhiteSpace(adHocSyncVarBindingId)
                    ? StableId("adhoc-binding", NormalizedSyncSessionId(), adHocSyncVarKind, adHocSyncVarUnityPath, adHocSyncVarBlenderPath)
                    : adHocSyncVarBindingId.Trim();
                var session = BuildSyncSession(now);

                mirror.PublishSyncSessionAsync(session).GetAwaiter().GetResult();
                PublishSyncVar(
                    bindingId,
                    string.IsNullOrWhiteSpace(adHocSyncVarKind) ? "custom-property" : adHocSyncVarKind.Trim(),
                    string.IsNullOrWhiteSpace(adHocSyncVarDisplayName) ? "Custom Property" : adHocSyncVarDisplayName.Trim(),
                    adHocSyncVarUnityPath.Trim(),
                    adHocSyncVarBlenderPath.Trim(),
                    adHocSyncVarEnabled,
                    string.IsNullOrWhiteSpace(adHocSyncVarInterpolation) ? "step" : adHocSyncVarInterpolation.Trim(),
                    now,
                    string.IsNullOrWhiteSpace(adHocSyncVarAuthority) ? "blender-to-unity" : adHocSyncVarAuthority.Trim());
                SetStatus($"Published Brokkr sync var: {adHocSyncVarDisplayName}", MessageType.Info);
            }
            catch (System.Exception error)
            {
                SetStatus(error.Message, MessageType.Error);
            }
        }

        private BrokkrSyncSession BuildSyncSession(string observedAt)
        {
            return new BrokkrSyncSession
            {
                sessionId = NormalizedSyncSessionId(),
                displayName = string.IsNullOrWhiteSpace(syncDisplayName) ? "Brokkr Editor Sync" : syncDisplayName,
                mode = "manual",
                enabled = true,
                createdAt = observedAt,
                updatedAt = observedAt
            };
        }

        private void PublishSyncVar(
            string bindingId,
            string kind,
            string displayName,
            string unityPropertyPath,
            string blenderPropertyPath,
            bool enabled,
            string interpolation,
            string updatedAt,
            string authority = "")
        {
            var resolvedAuthority = string.IsNullOrWhiteSpace(authority)
                ? DefaultAuthorityForKind(kind)
                : authority;
            var syncVar = new BrokkrSyncVar
            {
                syncVarId = StableId("var", NormalizedSyncSessionId(), bindingId, kind),
                sessionId = NormalizedSyncSessionId(),
                bindingId = bindingId,
                displayName = displayName,
                kind = kind,
                unityPropertyPath = unityPropertyPath,
                blenderPropertyPath = blenderPropertyPath,
                authority = resolvedAuthority,
                enabled = enabled,
                interpolation = interpolation,
                updatedAt = updatedAt
            };
            mirror.PublishSyncVarAsync(syncVar).GetAwaiter().GetResult();
        }

        private static string DefaultAuthorityForKind(string kind)
        {
            return kind.StartsWith("timeline", StringComparison.Ordinal) || kind == "custom-property"
                ? "blender-to-unity"
                : "unity-to-blender";
        }

        private static string BuildTransformPath(Transform transform)
        {
            var path = transform.name;
            while (transform.parent != null)
            {
                transform = transform.parent;
                path = $"{transform.name}/{path}";
            }

            return path;
        }

        private string BuildUnityCustomPropertyPath()
        {
            var propertyPath = string.IsNullOrWhiteSpace(unityCustomPropertyPath)
                ? "value"
                : unityCustomPropertyPath.Trim();
            return string.IsNullOrWhiteSpace(unityCustomPropertyComponentType)
                ? propertyPath
                : $"{unityCustomPropertyComponentType.Trim()}::{propertyPath}";
        }

        private string BuildUnityComponentPropertyPath()
        {
            var propertyPath = string.IsNullOrWhiteSpace(unityComponentPropertyPath)
                ? "m_Enabled"
                : unityComponentPropertyPath.Trim();
            return string.IsNullOrWhiteSpace(unityComponentPropertyComponentType)
                ? propertyPath
                : $"{unityComponentPropertyComponentType.Trim()}::{propertyPath}";
        }

        private static string NormalizeBlenderCustomPropertyPath(string path)
        {
            var trimmed = path.Trim();
            return trimmed.StartsWith("customProperties.", StringComparison.Ordinal)
                ? trimmed
                : $"customProperties.{trimmed}";
        }

        private static string StableId(params string[] parts)
        {
            return string.Join(":", parts).Replace(" ", "_").Replace("/", "_").Replace("\\", "_");
        }

        private string NormalizedSyncSessionId()
        {
            return string.IsNullOrWhiteSpace(syncSessionId) ? "default" : syncSessionId;
        }

        private void OnEditorSignal()
        {
            if (autoPublish)
            {
                CaptureSnapshot();
                PublishSnapshot();
            }
            else
            {
                Repaint();
            }
        }

        private void OnPlayModeChanged(PlayModeStateChange _)
        {
            OnEditorSignal();
        }

        private void OnEditorUpdate()
        {
            if (mirror != null && mirror.IsRunning)
            {
                PollSyncReceipts(true);
            }

            if (!autoPollCommands || EditorApplication.timeSinceStartup < nextPollAt)
            {
                return;
            }

            nextPollAt = EditorApplication.timeSinceStartup + 1.0;
            PollAndExecuteCommand(true);
        }

        private void RequireMirror()
        {
            if (mirror == null || !mirror.IsRunning)
            {
                throw new InvalidOperationException("Start the Brokkr CultMesh mirror first.");
            }
        }

        private void SetStatus(string message, MessageType messageType)
        {
            lastReceipt = message;
            lastMessageType = messageType;
            Repaint();
        }
    }
}
