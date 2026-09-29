#nullable disable
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace GameCult.Brokkr
{
    // Admission: decides whether the editor may run an intent at all. BrokkrEditorService asks before every
    // BrokkrUnityCommandExecutor.Execute; the window's buttons write intents like any other caller, so the operator
    // and an agent pass through this one gate. Pure logic, so it is tested outside Unity.
    public sealed class BrokkrCommandPolicy
    {
        // Scene mutation and editor lifecycle. Actions that write assets into the project (createScriptableObject,
        // createPrefabVariant) and saveScene are absent: the operator opts in per project.
        public static readonly string[] DefaultAllowedActions =
        {
            "createGameObject", "attachComponent", "setGameObjectTransform", "setGameObjectActive",
            "setGameObjectParent", "setComponentProperty", "instantiatePrefab", "assignMaterial",
            "refreshAssets", "setEditorPlayState", "setEditorPaused", "captureEditorView"
        };

        public const string CaptureAction = "captureEditorView";
        public const int MaxCaptureDimension = 8192;

        private readonly HashSet<string> allowed;
        private readonly string projectRoot;

        public BrokkrCommandPolicy(string projectRoot, IEnumerable<string> allowedActions)
        {
            this.projectRoot = projectRoot ?? throw new ArgumentNullException(nameof(projectRoot));
            allowed = new HashSet<string>(allowedActions ?? throw new ArgumentNullException(nameof(allowedActions)),
                StringComparer.Ordinal);
        }

        public static IEnumerable<string> ParseAllowedActions(string commaSeparated) =>
            (commaSeparated ?? "")
            .Split(new[] { ',', ';', '\n' }, StringSplitOptions.RemoveEmptyEntries)
            .Select(action => action.Trim())
            .Where(action => action.Length > 0);

        // The only directory captureEditorView writes to; an intent's outputPath is relative to it.
        public static string CaptureDirectory(string projectRoot) =>
            Path.GetFullPath(Path.Combine(projectRoot, ".brokkr", "captures"));

        // The one place that turns an intent's outputPath into a file path. It refuses every spelling that could
        // leave the capture directory, whatever the host OS thinks a rooted path is, and writes only PNG names.
        public static string ResolveCapturePath(string projectRoot, string outputPath)
        {
            if (string.IsNullOrWhiteSpace(outputPath))
            {
                throw new ArgumentException("Capture outputPath is required.");
            }

            var separators = new[] { '/', '\\' };
            if (outputPath.IndexOf(':') >= 0
                || separators.Contains(outputPath[0])
                || outputPath.Split(separators).Any(segment => segment == "..")
                || outputPath.IndexOfAny(Path.GetInvalidPathChars()) >= 0)
            {
                throw new ArgumentException(
                    "Capture outputPath must be a plain relative path inside .brokkr/captures.");
            }

            if (!outputPath.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException("Capture outputPath must name a .png file.");
            }

            var directory = CaptureDirectory(projectRoot);
            var full = Path.GetFullPath(Path.Combine(directory, outputPath));
            if (!full.StartsWith(directory + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            {
                throw new ArgumentException("Capture outputPath resolves outside .brokkr/captures.");
            }

            return full;
        }

        public BrokkrCommandAdmission Decide(BrokkrUnityCommand command)
        {
            if (!allowed.Contains(command.action ?? ""))
            {
                return BrokkrCommandAdmission.Deny($"Action '{command.action}' is not allowed for this project.");
            }

            if (command.action == CaptureAction)
            {
                try
                {
                    ResolveCapturePath(projectRoot, command.outputPath);
                }
                catch (ArgumentException error)
                {
                    return BrokkrCommandAdmission.Deny(error.Message);
                }

                if (command.width < 0 || command.height < 0
                    || command.width > MaxCaptureDimension || command.height > MaxCaptureDimension)
                {
                    return BrokkrCommandAdmission.Deny(
                        $"Capture width and height must be between 0 and {MaxCaptureDimension}.");
                }
            }

            return BrokkrCommandAdmission.Allow;
        }
    }

    public sealed class BrokkrCommandAdmission
    {
        public static readonly BrokkrCommandAdmission Allow = new BrokkrCommandAdmission(true, "");

        public bool Allowed { get; }
        public string Reason { get; }

        private BrokkrCommandAdmission(bool allowed, string reason)
        {
            Allowed = allowed;
            Reason = reason;
        }

        public static BrokkrCommandAdmission Deny(string reason) => new BrokkrCommandAdmission(false, reason);

        // A refusal is as inspectable as an acceptance: it gets a receipt of its own.
        public BrokkrUnityCommandReceipt DeniedReceipt(BrokkrUnityCommand command) => new BrokkrUnityCommandReceipt
        {
            commandId = command.commandId,
            status = "denied",
            message = Reason,
            observedAt = DateTime.UtcNow.ToString("O")
        };
    }
}
