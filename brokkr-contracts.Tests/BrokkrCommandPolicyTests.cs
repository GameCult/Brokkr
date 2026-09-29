using GameCult.Brokkr;

namespace Brokkr.Contracts.Tests;

public sealed class BrokkrCommandPolicyTests
{
    private static readonly string ProjectRoot = Path.Combine(Path.GetTempPath(), "brokkr-policy-project");

    private static BrokkrCommandPolicy Default() =>
        new(ProjectRoot, BrokkrCommandPolicy.DefaultAllowedActions);

    private static BrokkrUnityCommand Capture(string outputPath, int width = 0, int height = 0) => new()
    {
        commandId = "c", action = "captureEditorView", viewKind = "scene", outputPath = outputPath, width = width,
        height = height
    };

    [Theory]
    [InlineData("createScriptableObject")]
    [InlineData("createPrefabVariant")]
    [InlineData("saveScene")]
    public void DefaultPolicyDeniesAssetWritingAndSave(string action)
    {
        var admission = Default().Decide(new BrokkrUnityCommand { commandId = "c", action = action });

        Assert.False(admission.Allowed);
        Assert.Contains(action, admission.Reason);
    }

    [Theory]
    [InlineData("createGameObject")]
    [InlineData("attachComponent")]
    [InlineData("setGameObjectTransform")]
    [InlineData("setGameObjectActive")]
    [InlineData("setGameObjectParent")]
    [InlineData("setComponentProperty")]
    [InlineData("instantiatePrefab")]
    [InlineData("assignMaterial")]
    [InlineData("refreshAssets")]
    [InlineData("setEditorPlayState")]
    [InlineData("setEditorPaused")]
    public void DefaultPolicyAllowsSceneMutationAndLifecycle(string action)
    {
        Assert.True(Default().Decide(new BrokkrUnityCommand { commandId = "c", action = action }).Allowed);
    }

    [Fact]
    public void UnknownActionIsDenied()
    {
        Assert.False(Default().Decide(new BrokkrUnityCommand { commandId = "c", action = "formatDisk" }).Allowed);
        Assert.False(Default().Decide(new BrokkrUnityCommand { commandId = "c", action = "" }).Allowed);
    }

    [Fact]
    public void TheProjectAllowlistDecidesNotTheDefaults()
    {
        var policy = new BrokkrCommandPolicy(ProjectRoot, new[] { "saveScene" });

        Assert.True(policy.Decide(new BrokkrUnityCommand { commandId = "c", action = "saveScene" }).Allowed);
        Assert.False(policy.Decide(new BrokkrUnityCommand { commandId = "c", action = "createGameObject" }).Allowed);
    }

    [Fact]
    public void AllowlistTextParsesCommaSeparatedNames()
    {
        Assert.Equal(
            new[] { "saveScene", "refreshAssets" },
            BrokkrCommandPolicy.ParseAllowedActions(" saveScene, ,refreshAssets;").ToArray());
    }

    [Theory]
    [InlineData("shot.png")]
    [InlineData("views/scene 1.png")]
    [InlineData("a/./b.PNG")]
    public void CaptureInsideTheCaptureDirectoryIsAdmittedAndResolvedThere(string outputPath)
    {
        Assert.True(Default().Decide(Capture(outputPath)).Allowed);

        var resolved = BrokkrCommandPolicy.ResolveCapturePath(ProjectRoot, outputPath);
        Assert.StartsWith(BrokkrCommandPolicy.CaptureDirectory(ProjectRoot) + Path.DirectorySeparatorChar, resolved);
    }

    [Theory]
    [InlineData("C:/Windows/x.png")]
    [InlineData("C:\\Windows\\x.png")]
    [InlineData("/etc/x.png")]
    [InlineData("\\\\server\\share\\x.png")]
    [InlineData("../../x.png")]
    [InlineData("..\\x.png")]
    [InlineData("a/../../x.png")]
    [InlineData("a/../b.png")]
    [InlineData("shot.png:stream")]
    [InlineData(":x.png")]
    [InlineData("\u0000x.png")]
    [InlineData("x.txt")]
    [InlineData("x.cs")]
    [InlineData("noextension")]
    [InlineData("")]
    [InlineData("   ")]
    public void CaptureOutsideTheCaptureDirectoryOrNotAPngIsDenied(string outputPath)
    {
        var admission = Default().Decide(Capture(outputPath));

        Assert.False(admission.Allowed);
        Assert.NotEmpty(admission.Reason);
        Assert.Throws<ArgumentException>(() => BrokkrCommandPolicy.ResolveCapturePath(ProjectRoot, outputPath));
    }

    [Fact]
    public void CaptureDirectoryIsBrokkrCapturesUnderTheProjectRoot()
    {
        Assert.Equal(
            Path.GetFullPath(Path.Combine(ProjectRoot, ".brokkr", "captures")),
            BrokkrCommandPolicy.CaptureDirectory(ProjectRoot));
        Assert.Equal(
            Path.Combine(BrokkrCommandPolicy.CaptureDirectory(ProjectRoot), "shot.png"),
            BrokkrCommandPolicy.ResolveCapturePath(ProjectRoot, "shot.png"));
        Assert.EndsWith(Path.Combine(".brokkr", "captures"), BrokkrCommandPolicy.CaptureDirectory(ProjectRoot));
    }

    [Theory]
    [InlineData(-1, 0)]
    [InlineData(0, -5)]
    [InlineData(8193, 100)]
    [InlineData(100, 100000)]
    public void CaptureDimensionsAreBounded(int width, int height)
    {
        Assert.False(Default().Decide(Capture("shot.png", width, height)).Allowed);
    }

    [Theory]
    [InlineData(0, 0)]
    [InlineData(640, 480)]
    [InlineData(8192, 8192)]
    public void ReasonableCaptureDimensionsAreAdmitted(int width, int height)
    {
        Assert.True(Default().Decide(Capture("shot.png", width, height)).Allowed);
    }

    [Fact]
    public void OnlyCaptureIsHeldToTheCapturePathRule()
    {
        var command = new BrokkrUnityCommand { commandId = "c", action = "refreshAssets", outputPath = "/anything" };

        Assert.True(Default().Decide(command).Allowed);
    }

    [Fact]
    public void DenialGetsAReceiptThatNamesTheIdAndTheReason()
    {
        var command = new BrokkrUnityCommand { commandId = "denied-1", action = "createScriptableObject" };
        var admission = Default().Decide(command);

        var receipt = admission.DeniedReceipt(command);

        Assert.Equal("denied", receipt.status);
        Assert.Equal("denied-1", receipt.commandId);
        Assert.Equal(admission.Reason, receipt.message);
    }
}
