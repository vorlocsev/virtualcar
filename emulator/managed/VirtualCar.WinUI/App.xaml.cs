using Microsoft.UI.Xaml;

namespace VirtualCar.WinUI;

public partial class App : Application
{
    private Window? _window;

    public App() => InitializeComponent();

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        bool ephemeral = Environment.GetCommandLineArgs().Skip(1).SequenceEqual(new[] { "--ephemeral-settings" });
        _window = new CemPreviewWindow(ephemeral);
        _window.Activate();
    }
}
