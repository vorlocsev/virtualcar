using Microsoft.UI.Xaml;

namespace VirtualCar.WinUI;

public partial class App : Application
{
    private Window? _window;

    public App() => InitializeComponent();

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        var arguments = Environment.GetCommandLineArgs().Skip(1).ToArray();
        bool previewOnly = arguments.SequenceEqual(new[] { "--preview-only" });
        bool ephemeral = previewOnly || arguments.SequenceEqual(new[] { "--ephemeral-settings" });
        _window = new CemPreviewWindow(ephemeral, previewOnly);
        _window.Activate();
    }
}
