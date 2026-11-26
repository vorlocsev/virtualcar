using Microsoft.UI.Xaml;

namespace VirtualCar.WinUI;

public partial class App : Application
{
    private Window? _window;

    public App() => InitializeComponent();

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        var arguments = Environment.GetCommandLineArgs().Skip(1).ToArray();
        if (arguments.Length == 0)
        {
            VehicleHomeWindow? home = null;
            home = new VehicleHomeWindow(() =>
            {
                _window = new CemPreviewWindow();
                _window.Activate();
                home?.Close();
            });
            _window = home;
            _window.Activate();
            return;
        }
        bool previewOnly = arguments.SequenceEqual(new[] { "--preview-only" });
        bool diagnosticsOnly = arguments.SequenceEqual(new[] { "--diagnostics-only" });
        bool registrationOnly = arguments.SequenceEqual(new[] { "--registration-only" });
        // Only explicit advanced mode enables the original non-ephemeral workspace.
        bool ephemeral = !arguments.SequenceEqual(new[] { "--advanced" });
        _window = new CemPreviewWindow(ephemeral, previewOnly, diagnosticsOnly, registrationOnly);
        _window.Activate();
    }
}
