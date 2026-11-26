using System.Diagnostics;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VirtualCar.Core;
using VirtualCar.DriverTool;

namespace VirtualCar.WinUI;

// Ordinary startup: no file pickers, external scripts or automatic writes.
public sealed class VehicleHomeWindow : Window
{
    private readonly ComboBox _vehicle = new() { HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly ComboBox _language = new() { MinWidth = 88 };
    private readonly TextBlock _heading = new() { FontSize = 30, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _name = new() { FontSize = 24, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _description = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _identity = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _modules = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Expander _configuration = new() { Visibility = Visibility.Collapsed };
    private readonly ListView _configurationRows = new() { MaxHeight = 320, SelectionMode = ListViewSelectionMode.None };
    private readonly List<BuiltInVehicle> _profiles = new(BuiltInVehicles.All);
    private readonly LocalVehicleProfile? _localProfile;
    private readonly TextBlock _availability = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _status = new() { FontSize = 18, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _notice = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Button _connect = new(), _disconnect = new(), _refresh = new(), _advanced = new();
    private readonly StackPanel _content = new() { Spacing = 12, Padding = new Thickness(24) };
    private readonly UiLanguageSettings? _settings;
    private readonly Action _openAdvanced;
    private bool _russian, _busy, _closed, _rendering;
    private string _resultEn = "", _resultRu = "";
    private BuiltInVehicle Selected => _profiles[Math.Max(0, _vehicle.SelectedIndex)];
    private string T(string en, string ru) => _russian ? ru : en;
    private string Helper => Path.Combine(AppContext.BaseDirectory, "driver-tools", "VirtualCar.DriverTool.exe");

    public VehicleHomeWindow(Action openAdvanced)
    {
        _openAdvanced = openAdvanced;
        Title = "Virtual Car";
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (Path.IsPathFullyQualified(local))
        {
            _settings = new UiLanguageSettings(Path.Combine(local, "VirtualCar", "WinUI", "language.v1"));
            _russian = _settings.Load() == UiLanguage.Russian;
        }

        var top = new Grid { ColumnSpacing = 12 };
        top.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        top.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        _language.Items.Add("EN"); _language.Items.Add("RU");
        _language.SelectedIndex = _russian ? 1 : 0;
        top.Children.Add(_heading); Grid.SetColumn(_language, 1); top.Children.Add(_language);
        _content.Children.Add(top);
        try
        {
            _localProfile = LocalVehicleData.Load(AppContext.BaseDirectory);
            _profiles.Insert(0, _localProfile.Vehicle);
        }
        catch (Exception) { /* An absent or invalid local package is not a selectable vehicle. */ }
        foreach (var profile in _profiles)
            _vehicle.Items.Add(new ComboBoxItem { Tag = profile.Id, Content = profile.NameEn });
        _vehicle.SelectedIndex = 0;
        _content.Children.Add(_vehicle);
        var card = new StackPanel { Spacing = 8, Padding = new Thickness(18) };
        foreach (var item in new FrameworkElement[] { _name, _description, _identity, _modules, _availability })
            card.Children.Add(item);
        _content.Children.Add(new Border { CornerRadius = new CornerRadius(12), BorderThickness = new Thickness(1),
            BorderBrush = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Gray), Child = card });
        _configuration.Content = _configurationRows;
        _content.Children.Add(_configuration);
        Id(_configuration, "VC094B.Configuration");
        Id(_configurationRows, "VC094B.Configuration.Rows");
        _content.Children.Add(_status);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(_connect); actions.Children.Add(_disconnect); actions.Children.Add(_refresh);
        _content.Children.Add(actions);
        _content.Children.Add(_notice);
        _content.Children.Add(_advanced);
        Content = new ScrollViewer { Content = _content, VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
        Id(_vehicle, "VC094A.Vehicle"); Id(_language, "VC094A.Language");
        Id(_status, "VC094A.Connection.Status"); Id(_connect, "VC094A.Connection.Enable");
        Id(_disconnect, "VC094A.Connection.Disable"); Id(_refresh, "VC094A.Refresh");
        Id(_advanced, "VC094A.Advanced"); Id(_notice, "VC094A.Notice");
        Id(_name, "VC094A.Vehicle.Name"); Id(_identity, "VC094A.Vehicle.Identity");
        Id(_modules, "VC094A.Vehicle.Modules"); Id(_availability, "VC094A.Vehicle.Availability");
        _vehicle.SelectionChanged += (_, _) => { if (!_rendering) { _resultEn = _resultRu = ""; Render(); } };
        _language.SelectionChanged += (_, _) =>
        {
            if (_language.SelectedIndex < 0 || _busy || _closed) return;
            _russian = _language.SelectedIndex == 1;
            _settings?.TrySave(_russian ? UiLanguage.Russian : UiLanguage.English);
            Render();
        };
        _refresh.Click += (_, _) => Render();
        _connect.Click += async (_, _) => await ChangeAsync(true);
        _disconnect.Click += async (_, _) => await ChangeAsync(false);
        _advanced.Click += (_, _) => { if (!_busy && !_closed) _openAdvanced(); };
        Closed += (_, _) => _closed = true;
        Render();
        ResizeForDisplay();
    }

    private static void Id(DependencyObject element, string id) =>
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetAutomationId(element, id);

    private void ResizeForDisplay()
    {
        var area = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(AppWindow.Id,
            Microsoft.UI.Windowing.DisplayAreaFallback.Nearest);
        var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
        double scale = Math.Max(1.0, GetDpiForWindow(hwnd) / 96.0);
        var work = area.WorkArea;
        int w = Math.Min(work.Width, (int)Math.Round(1000 * scale)), h = Math.Min(work.Height, (int)Math.Round(720 * scale));
        if (w > 0 && h > 0) AppWindow.MoveAndResize(new Windows.Graphics.RectInt32(
            work.X + (work.Width-w)/2, work.Y + (work.Height-h)/2, w, h));
    }
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint GetDpiForWindow(IntPtr hwnd);

    private static bool SamePath(string? a, string b) =>
        string.Equals(a, b, StringComparison.OrdinalIgnoreCase);

    private static byte[] ReadLocal(string path, int max)
    {
        for (FileSystemInfo? item = new FileInfo(path); item is not null;
            item = item is FileInfo file ? file.Directory : ((DirectoryInfo)item).Parent)
            if ((item.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException();
        using var stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (stream.Length < 1 || stream.Length > max) throw new InvalidDataException();
        byte[] bytes = new byte[(int)stream.Length];
        stream.ReadExactly(bytes);
        if (stream.ReadByte() != -1) throw new InvalidDataException();
        return bytes;
    }

    private (string Path, string Sha)? Candidate(BuiltInVehicle profile)
    {
        try
        {
            bool local = profile.Id == LocalVehicleData.Id;
            string path = local ? Path.Combine(LocalVehicleData.Folder(AppContext.BaseDirectory), "VirtualCarJ2534.dll") :
                BuiltInVehicles.PackageLibrary(AppContext.BaseDirectory, profile.Id);
            if (!BuiltInVehicles.IsNativePathSupported(path) || !File.Exists(Helper)) return null;
            string folder = Path.GetDirectoryName(path)!;
            if (local)
            {
                if (LocalVehicleData.Load(AppContext.BaseDirectory).Vehicle != profile) return null;
            }
            else if (!BuiltInVehicles.MatchesProfile(profile.Id, ReadLocal(Path.Combine(folder, "virtualcar.ini"), 1024 * 1024)))
                return null;
            string expected = System.Text.Encoding.ASCII.GetString(ReadLocal(Path.Combine(folder, "candidate.sha256"), 128)).Trim();
            string actual = DriverRegistration.Fingerprint(path);
            return AcceptanceReportReader.IsHash(expected, 64) && actual.Equals(expected, StringComparison.OrdinalIgnoreCase)
                ? (path, actual) : null;
        }
        catch (Exception) { return null; }
    }

    private void Render()
    {
        if (_closed || _rendering) return;
        _rendering = true;
        try
        {
            int selection = Math.Max(0, _vehicle.SelectedIndex);
            for (int i = 0; i < _profiles.Count; i++)
                ((ComboBoxItem)_vehicle.Items[i]).Content = T(_profiles[i].NameEn, _profiles[i].NameRu);
            _vehicle.SelectedIndex = -1; _vehicle.SelectedIndex = selection;
            var profile = Selected;
            _heading.Text = T("Virtual Car", "Виртуальный автомобиль");
            _vehicle.Header = T("Choose a vehicle", "Выберите автомобиль");
            _name.Text = T(profile.NameEn, profile.NameRu);
            _description.Text = T(profile.DescriptionEn, profile.DescriptionRu);
            bool local = profile.Id == LocalVehicleData.Id;
            _identity.Text = (local ? "VIN: " : T("Demo VIN: ", "Демонстрационный VIN: ")) + profile.Vin;
            _configuration.Visibility = local ? Visibility.Visible : Visibility.Collapsed;
            _configuration.Header = T("Vehicle equipment · read only", "Комплектация автомобиля · просмотр");
            _configurationRows.Items.Clear();
            if (local && _localProfile is not null)
                foreach (var row in _localProfile.Rows)
                    _configurationRows.Items.Add(new TextBlock { TextWrapping = TextWrapping.Wrap,
                        Text = row.Name + ": " + row.Value + (row.Locked ? T(" (protected)", " (защищено)") : "") });
            else _configuration.IsExpanded = false;
            var slots = local ? 8 : NativeEcuInventory.Inspect(BuiltInVehicles.ReadProfile(profile.Id)).Count;
            _modules.Text = T("Configured diagnostic routes: ", "Настроено диагностических маршрутов: ") + slots +
                T(" (not ECU discovery)", " (не обнаружение блоков)");
            _availability.Text = local ? T("Equipment snapshot included. Editing and engine controls remain in advanced mode.", "Комплектация включена. Редактирование и управление двигателем пока в расширенном режиме.") :
                T("Engine and ignition controls require a reviewed vehicle profile. Advanced configuration remains available.",
                "Управление двигателем и зажиганием требует проверенного профиля. Расширенная настройка доступна отдельно.");
            var candidate = Candidate(profile);
            var registration = DriverRegistration.Read();
            bool own = candidate is { } c && registration.Status == DriverRegistration.State.Registered &&
                SamePath(registration.Library, c.Path);
            _status.Text = registration.Status switch
            {
                DriverRegistration.State.Absent when candidate is not null => T("Ready to enable diagnostic adapter", "Готов к включению адаптера"),
                DriverRegistration.State.Absent => T("Diagnostic component not available in this build", "Диагностический компонент отсутствует в этой сборке"),
                DriverRegistration.State.Registered when own => T("Adapter enabled for this vehicle", "Адаптер включён для этого автомобиля"),
                DriverRegistration.State.Registered => T("Another profile or installation is active", "Активен другой профиль или установка"),
                _ => T("Connection requires review in advanced mode", "Требуется проверка подключения в расширенном режиме")
            };
            _connect.Content = T("Enable adapter", "Включить адаптер");
            _disconnect.Content = T("Disable adapter", "Отключить адаптер");
            _refresh.Content = T("Refresh", "Обновить");
            _advanced.Content = T("Advanced settings", "Расширенные настройки");
            _vehicle.IsEnabled = _language.IsEnabled = _advanced.IsEnabled = _refresh.IsEnabled = !_busy;
            _connect.IsEnabled = !_busy && candidate is not null && registration.Status == DriverRegistration.State.Absent;
            _disconnect.IsEnabled = !_busy && own;
            _notice.Text = T("Adapter registration does not mean a diagnostic client is connected. Original VIDA acceptance is not verified.",
                "Регистрация адаптера не означает подключения диагностической программы. Приёмка оригинальной VIDA не подтверждена.") +
                (string.IsNullOrEmpty(_resultEn) ? "" : "\n" + T(_resultEn, _resultRu));
        }
        finally { _rendering = false; }
    }

    private async Task ChangeAsync(bool enable)
    {
        if (_busy || _closed || !(enable ? _connect.IsEnabled : _disconnect.IsEnabled)) return;
        var profile = Selected;
        var candidate = Candidate(profile);
        if (candidate is not { } c) { Render(); return; }
        _busy = true; Render();
        try
        {
            var dialog = new ContentDialog
            {
                XamlRoot = _content.XamlRoot,
                Title = enable ? T("Enable diagnostic adapter?", "Включить диагностический адаптер?") :
                    T("Disable diagnostic adapter?", "Отключить диагностический адаптер?"),
                Content = T("Close VIDA and all other diagnostic clients. Use only an authorized test environment. Windows administrator approval is required.",
                    "Закройте VIDA и остальные диагностические программы. Используйте только разрешённую тестовую среду. Потребуется подтверждение администратора Windows.") +
                    (profile.HistoricalDemo ? "\n" + T(profile.DescriptionEn, profile.DescriptionRu) : ""),
                PrimaryButtonText = enable ? T("Enable", "Включить") : T("Disable", "Отключить"),
                CloseButtonText = T("Cancel", "Отмена"),
                DefaultButton = ContentDialogButton.Close
            };
            if (await dialog.ShowAsync() != ContentDialogResult.Primary || _closed)
            {
                _resultEn = "Cancelled."; _resultRu = "Отменено."; return;
            }
            var now = Candidate(profile);
            var before = DriverRegistration.Read();
            if (now is not { } n || n != c ||
                (enable ? before.Status != DriverRegistration.State.Absent :
                    before.Status != DriverRegistration.State.Registered || !SamePath(before.Library, c.Path)))
                throw new InvalidOperationException();
            var start = new ProcessStartInfo { FileName = Helper, WorkingDirectory = Path.GetDirectoryName(Helper)!,
                UseShellExecute = true, Verb = "runas" };
            start.ArgumentList.Add(enable ? "install" : "remove-canonical");
            start.ArgumentList.Add(c.Path); start.ArgumentList.Add(c.Sha);
            using var process = Process.Start(start) ?? throw new InvalidOperationException();
            await process.WaitForExitAsync();
            var after = DriverRegistration.Read();
            if (process.ExitCode != 0 || (enable ?
                    after.Status != DriverRegistration.State.Registered || !SamePath(after.Library, c.Path) || Candidate(profile) != c :
                    after.Status != DriverRegistration.State.Absent)) throw new InvalidOperationException();
            _resultEn = enable ? "Adapter enabled. Open your diagnostic client manually." : "Adapter disabled.";
            _resultRu = enable ? "Адаптер включён. Откройте диагностическую программу самостоятельно." : "Адаптер отключён.";
        }
        catch (System.ComponentModel.Win32Exception ex) when (ex.NativeErrorCode == 1223)
        { _resultEn = "Administrator approval cancelled."; _resultRu = "Запрос прав администратора отменён."; }
        catch (Exception)
        { _resultEn = "Operation not confirmed. Review advanced settings."; _resultRu = "Операция не подтверждена. Проверьте расширенные настройки."; }
        finally { _busy = false; if (!_closed) Render(); }
    }
}
