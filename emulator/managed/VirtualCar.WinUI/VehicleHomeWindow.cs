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
    private readonly ComboBox _language = new() { MinWidth = 120 };
    private readonly TextBlock _languageNotice = new() { FontSize = 12, TextWrapping = TextWrapping.Wrap, Visibility = Visibility.Collapsed };
    private bool _languageSaveFailed;
    private readonly TextBlock _heading = new() { FontSize = 28, TextWrapping = TextWrapping.Wrap, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold };
    private readonly TextBlock _subheading = new() { FontSize = 13, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _connectionTitle = new() { FontSize = 20, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold };
    private readonly TextBlock _stateTitle = new() { FontSize = 20, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold };
    private readonly TextBlock _equipmentTitle = new() { FontSize = 20, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold };
    private readonly TextBlock _equipmentHint = new() { TextWrapping = TextWrapping.Wrap };
    private readonly StackPanel _left = new() { Spacing = 14 };
    private readonly StackPanel _right = new() { Spacing = 14 };
    private readonly Grid _dashboard = new();
    private Border? _stateCard, _equipmentCard;
    private bool? _wideLayout;
    private bool _hasDetails;
    private readonly TextBlock _name = new() { FontSize = 24, TextWrapping = TextWrapping.Wrap, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold };
    private readonly Image _vehiclePhoto = new() { Height = 210, Stretch = Microsoft.UI.Xaml.Media.Stretch.Uniform, Visibility = Visibility.Collapsed };
    private readonly TextBlock _photoCaption = new() { TextWrapping = TextWrapping.Wrap, FontSize = 12 };
    private string? _photoVehicleId;
    private int _photoRequest;
    private bool _photoReady;
    private readonly TextBlock _description = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _identity = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _modules = new() { TextWrapping = TextWrapping.Wrap };
    private readonly ComboBox _equipmentVariant = new() { HorizontalAlignment = HorizontalAlignment.Stretch, Visibility = Visibility.Collapsed };
    private readonly TextBlock _equipmentVariantStatus = new() { TextWrapping = TextWrapping.Wrap, Visibility = Visibility.Collapsed };
    private EquipmentVariant? _selectedVariant;
    private readonly StackPanel _statePanel = new() { Spacing = 8, Visibility = Visibility.Collapsed };
    private readonly ComboBox _ignition = new() { HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly ComboBox _engine = new() { HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly Button _prepareState = new();
    private readonly TextBlock _stateStatus = new() { TextWrapping = TextWrapping.Wrap };
    private IReadOnlyList<NativeIgnitionSelection?> _ignitions = new NativeIgnitionSelection?[] { null };
    private IReadOnlyList<EcmScenario?> _engines = new EcmScenario?[] { null };
    private VehicleStateChoice _choice = VehicleStateChoice.Original;
    private readonly Expander _configuration = new() { Visibility = Visibility.Collapsed };
    private readonly ComboBox _equipmentParameter = new() { HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly ComboBox _equipmentValue = new() { HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly Button _equipmentReset = new();
    private readonly Button _equipmentPrepare = new();
    private readonly TextBlock _equipmentStatus = new() { TextWrapping = TextWrapping.Wrap };
    private readonly StackPanel _equipmentEditor = new() { Spacing = 8 };
    private readonly Dictionary<int, string> _equipmentEdits = new();
    private int _equipmentOffset = -1;
    private bool _equipmentRendering;
    private readonly ListView _configurationRows = new() { MaxHeight = 320, SelectionMode = ListViewSelectionMode.None };
    private readonly List<BuiltInVehicle> _profiles = new(BuiltInVehicles.All);
    private readonly LocalVehicleProfile? _localProfile;
    private readonly LocalVehicleData.Availability _localAvailability;
    private readonly TextBlock _localNotice = new() { TextWrapping = TextWrapping.Wrap, Visibility = Visibility.Collapsed };
    private readonly TextBlock _availability = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _status = new() { FontSize = 18, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _notice = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Button _connect = new(), _disconnect = new(), _refresh = new(), _advanced = new();
    private readonly StackPanel _content = new() { Spacing = 16, Padding = new Thickness(20), HorizontalAlignment = HorizontalAlignment.Stretch, RequestedTheme = ElementTheme.Dark };
    private readonly UiLanguageSettings? _settings;
    private readonly Action _openAdvanced;
    private readonly bool _homePreview;
    private bool _russian, _busy, _closed, _rendering;
    private string _resultEn = "", _resultRu = "";
    private BuiltInVehicle Selected => _profiles[Math.Max(0, _vehicle.SelectedIndex)];
    private string T(string en, string ru) => _russian ? ru : en;
    private string Helper => Path.Combine(AppContext.BaseDirectory, "driver-tools", "VirtualCar.DriverTool.exe");

    public VehicleHomeWindow(Action openAdvanced, bool homePreview = false)
    {
        _homePreview = homePreview;
        _openAdvanced = openAdvanced;
        Title = "Virtual Car";
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!_homePreview && Path.IsPathFullyQualified(local))
        {
            _settings = new UiLanguageSettings(Path.Combine(local, "VirtualCar", "WinUI", "language.v1"));
            _russian = _settings.Load() == UiLanguage.Russian;
        }

        var top = new Grid { ColumnSpacing = 12 };
        top.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        top.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var english = new ComboBoxItem { Content = "English" };
        var russian = new ComboBoxItem { Content = "Русский" };
        Id(english, "VC094A.Language.EN"); Id(russian, "VC094A.Language.RU");
        _language.Items.Add(english); _language.Items.Add(russian);
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(_language, "Language / Язык");
        _language.SelectedIndex = _russian ? 1 : 0;
        var headingGroup = new StackPanel { Spacing = 3 };
        headingGroup.Children.Add(_heading); headingGroup.Children.Add(_subheading);
        top.Children.Add(headingGroup);
        var languagePanel = new StackPanel { Spacing = 4, MaxWidth = 160, VerticalAlignment = VerticalAlignment.Center };
        languagePanel.Children.Add(_language); languagePanel.Children.Add(_languageNotice);
        Grid.SetColumn(languagePanel, 1); top.Children.Add(languagePanel);
        Id(_languageNotice, "VC095A.Language.Notice");
        _content.Children.Add(top);
        _localAvailability = LocalVehicleData.Probe(AppContext.BaseDirectory, out var loadedProfile);
        _localProfile = loadedProfile;
        if (_localProfile is not null) _profiles.Insert(0, _localProfile.Vehicle);
        Id(_localNotice, "VC095C.LocalProfile.Notice");
        _content.Children.Add(_localNotice);
        foreach (var profile in _profiles)
            _vehicle.Items.Add(new ComboBoxItem { Tag = profile.Id, Content = profile.NameEn });
        _vehicle.SelectedIndex = 0;
        var card = new StackPanel { Spacing = 10 };
        card.Children.Add(_vehicle);
        Id(_vehiclePhoto, "VC094E.Vehicle.Photo"); Id(_photoCaption, "VC094E.Vehicle.PhotoCaption");
        foreach (var item in new FrameworkElement[] { _name, _vehiclePhoto, _photoCaption, _description, _identity, _modules, _availability })
            card.Children.Add(item);
        _left.Children.Add(Card(card));
        Id(_equipmentVariant, "VC094D3.Variant");
        Id(_equipmentVariantStatus, "VC094D3.Variant.Status");
        _equipmentVariant.SelectionChanged += (_, _) =>
        {
            if (_rendering || _busy || _closed || !_equipmentVariant.IsEnabled ||
                Selected.Id != LocalVehicleData.Id || _equipmentVariant.SelectedItem is not ComboBoxItem item ||
                DriverRegistration.Read().Status != DriverRegistration.State.Absent) return;
            _selectedVariant = item.Tag as EquipmentVariant;
            _choice = VehicleStateChoice.Original;
            _resultEn = _resultRu = "";
            Render();
        };
        _statePanel.Children.Add(_stateTitle);
        foreach (var item in new FrameworkElement[] { _ignition, _engine, _prepareState, _stateStatus })
            _statePanel.Children.Add(item);
        _stateCard = Card(_statePanel);
        _right.Children.Add(_stateCard);
        Id(_ignition, "VC094C.Ignition"); Id(_engine, "VC094C.Engine");
        Id(_prepareState, "VC094C.Prepare"); Id(_stateStatus, "VC094C.State.Status");
        _ignition.SelectionChanged += (_, _) => SelectState();
        _engine.SelectionChanged += (_, _) => SelectState();
        _prepareState.Click += async (_, _) => await PrepareStateAsync();
        var equipmentContent = new StackPanel { Spacing = 8 };
        equipmentContent.Children.Add(_configurationRows);
        foreach (var item in new FrameworkElement[] { _equipmentParameter, _equipmentValue, _equipmentReset, _equipmentPrepare, _equipmentStatus })
            _equipmentEditor.Children.Add(item);
        equipmentContent.Children.Add(_equipmentEditor);
        _configuration.Content = equipmentContent;
        Id(_equipmentParameter, "VC094D.Equipment.Parameter"); Id(_equipmentValue, "VC094D.Equipment.Value");
        Id(_equipmentPrepare, "VC094D2.Equipment.Prepare");
        _equipmentPrepare.Click += async (_, _) => await PrepareEquipmentAsync();
        Id(_equipmentReset, "VC094D.Equipment.Reset"); Id(_equipmentStatus, "VC094D.Equipment.Status");
        _equipmentParameter.SelectionChanged += (_, _) =>
        {
            if (_equipmentRendering || _rendering || _busy) return;
            if (_equipmentParameter.SelectedItem is ComboBoxItem item && item.Tag is int offset)
                _equipmentOffset = offset;
            Render();
        };
        _equipmentValue.SelectionChanged += (_, _) =>
        {
            if (_equipmentRendering || _rendering || _busy || _localProfile?.Editor is not { } editor ||
                !_equipmentValue.IsEnabled || _equipmentValue.SelectedItem is not ComboBoxItem item ||
                item.Tag is not string code || !editor.Options.TryGetValue(_equipmentOffset, out var row)) return;
            var candidate = new Dictionary<int, string>(_equipmentEdits);
            if (code == row.BaselineCode) candidate.Remove(_equipmentOffset);
            else candidate[_equipmentOffset] = code;
            try
            {
                editor.Preview(candidate);
                _equipmentEdits.Clear();
                foreach (var pair in candidate) _equipmentEdits.Add(pair.Key, pair.Value);
            }
            catch (Exception) { /* Invalid choices never replace the current draft. */ }
            Render();
        };
        _equipmentReset.Click += (_, _) => { if (!_busy) { _equipmentEdits.Clear(); Render(); } };
        var equipmentPanel = new StackPanel { Spacing = 10 };
        foreach (var item in new FrameworkElement[] { _equipmentTitle, _equipmentVariant, _equipmentVariantStatus, _equipmentHint, _configuration })
            equipmentPanel.Children.Add(item);
        _equipmentCard = Card(equipmentPanel);
        _right.Children.Add(_equipmentCard);
        Id(_configuration, "VC094B.Configuration");
        Id(_configurationRows, "VC094B.Configuration.Rows");
        var connection = new StackPanel { Spacing = 10 };
        foreach (var item in new FrameworkElement[] { _connectionTitle, _status, _connect, _disconnect, _refresh, _notice })
            connection.Children.Add(item);
        _left.Children.Add(Card(connection));
        _left.Children.Add(_advanced);
        foreach (var button in new[] { _connect, _disconnect, _refresh, _advanced, _prepareState, _equipmentPrepare, _equipmentReset })
        {
            button.HorizontalAlignment = HorizontalAlignment.Stretch;
            button.MinHeight = 36;
        }
        if (Application.Current.Resources.TryGetValue("AccentButtonStyle", out var accent) && accent is Style style)
            _connect.Style = style;
        _dashboard.ColumnDefinitions.Add(new ColumnDefinition());
        _dashboard.ColumnDefinitions.Add(new ColumnDefinition());
        _dashboard.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        _dashboard.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        _dashboard.Children.Add(_left); _dashboard.Children.Add(_right);
        _content.Children.Add(_dashboard);
        _dashboard.SizeChanged += (_, args) => ApplyLayout(args.NewSize.Width);
        ApplyLayout(0);
        Id(_dashboard, "VC094F.Dashboard");
        Id(_connectionTitle, "VC094F.Connection.Title");
        Id(_stateTitle, "VC094F.State.Title");
        Id(_equipmentTitle, "VC094F.Equipment.Title");
        Content = new ScrollViewer { Content = _content, VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled, HorizontalScrollMode = ScrollMode.Disabled,
            HorizontalContentAlignment = HorizontalAlignment.Stretch, RequestedTheme = ElementTheme.Dark, Background = Brush(21,25,32) };
        Id(_vehicle, "VC094A.Vehicle"); Id(_language, "VC094A.Language");
        Id(_status, "VC094A.Connection.Status"); Id(_connect, "VC094A.Connection.Enable");
        Id(_disconnect, "VC094A.Connection.Disable"); Id(_refresh, "VC094A.Refresh");
        Id(_advanced, "VC094A.Advanced"); Id(_notice, "VC094A.Notice");
        Id(_name, "VC094A.Vehicle.Name"); Id(_identity, "VC094A.Vehicle.Identity");
        Id(_modules, "VC094A.Vehicle.Modules"); Id(_availability, "VC094A.Vehicle.Availability");
        _vehicle.SelectionChanged += (_, _) => { if (!_rendering) { _resultEn = _resultRu = ""; Render(); } };
        _language.SelectionChanged += (_, _) =>
        {
            if (_language.SelectedIndex < 0 || _busy || _closed || _rendering) return;
            _russian = _language.SelectedIndex == 1;
            _languageSaveFailed = !_homePreview && !(_settings?.TrySave(_russian ? UiLanguage.Russian : UiLanguage.English) ?? false);
            Render();
        };
        _refresh.Click += (_, _) => { _photoVehicleId = null; Render(); };
        _connect.Click += async (_, _) => await ChangeAsync(true);
        _disconnect.Click += async (_, _) => await ChangeAsync(false);
        _advanced.Click += (_, _) => { if (!_homePreview && !_busy && !_closed) _openAdvanced(); };
        Closed += (_, _) => _closed = true;
        Render();
        ResizeForDisplay();
    }

    private static Microsoft.UI.Xaml.Media.SolidColorBrush Brush(byte r, byte g, byte b) =>
        new(Windows.UI.Color.FromArgb(255, r, g, b));

    private static Border Card(FrameworkElement child) => new()
    {
        Background = Brush(31, 37, 47),
        BorderBrush = Brush(56, 65, 78),
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(14),
        Padding = new Thickness(16),
        Child = child
    };

    private void ApplyLayout(double width)
    {
        var plan = HomeLayoutPlan.ForWidth(width, _hasDetails);
        _right.Visibility = _hasDetails ? Visibility.Visible : Visibility.Collapsed;
        if (_wideLayout == plan.TwoColumns) return;
        _wideLayout = plan.TwoColumns;
        _dashboard.ColumnSpacing = plan.Gap;
        _dashboard.RowSpacing = plan.TwoColumns ? 0 : 14;
        _dashboard.ColumnDefinitions[0].Width = new GridLength(plan.LeftWeight, GridUnitType.Star);
        _dashboard.ColumnDefinitions[1].Width = plan.TwoColumns
            ? new GridLength(plan.RightWeight, GridUnitType.Star) : new GridLength(0);
        Grid.SetRow(_right, plan.TwoColumns ? 0 : 1);
        Grid.SetColumn(_right, plan.TwoColumns ? 1 : 0);
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
        int w = Math.Min(work.Width, (int)Math.Round(1180 * scale)), h = Math.Min(work.Height, (int)Math.Round(800 * scale));
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

    private (string Path, string Sha)? BaseCandidate(BuiltInVehicle profile)
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

    private (string Path, string Sha)? Candidate(BuiltInVehicle profile)
    {
        var candidate = BaseCandidate(profile);
        if (candidate is not { } c || profile.Id != LocalVehicleData.Id) return candidate;
        if (_selectedVariant is { } variant)
        {
            try
            {
                var current = LocalVehicleData.Load(AppContext.BaseDirectory);
                if (!_choice.IsOriginal || current.Editor is not { } editor || current.References is not { } refs ||
                    !EquipmentVariantPackages.Matches(AppContext.BaseDirectory, editor, refs,
                        LocalVehicleData.ReadProfile(AppContext.BaseDirectory), c.Sha, variant)) return null;
                string library = EquipmentVariantPackages.Library(AppContext.BaseDirectory, variant);
                return DriverRegistration.Fingerprint(library).Equals(c.Sha, StringComparison.OrdinalIgnoreCase) ? (library, c.Sha) : null;
            }
            catch (Exception) { return null; }
        }
        if (_choice.IsOriginal) return candidate;
        try
        {
            byte[] baseline = LocalVehicleData.ReadProfile(AppContext.BaseDirectory);
            string path = Path.Combine(VehicleStatePackages.Folder(AppContext.BaseDirectory, _choice), "VirtualCarJ2534.dll");
            if (!VehicleStatePackages.Matches(AppContext.BaseDirectory, _choice, baseline, c.Sha) ||
                !BuiltInVehicles.IsNativePathSupported(path) ||
                !DriverRegistration.Fingerprint(path).Equals(c.Sha, StringComparison.OrdinalIgnoreCase)) return null;
            return (path, c.Sha);
        }
        catch (Exception) { return null; }
    }

    private HomeProviderLocation? RegisteredLocation(DriverRegistration.Info registration)
    {
        if (registration.Status != DriverRegistration.State.Registered) return null;
        try
        {
            return HomeProviderPaths.Recognize(AppContext.BaseDirectory, registration.Library,
                _localProfile?.References?.Variants ?? Array.Empty<EquipmentVariant>());
        }
        catch (Exception) { return null; }
    }

    private (string Path, string Sha)? DisconnectCandidate(DriverRegistration.Info registration,
        (string Path, string Sha)? selectedCandidate)
    {
        if (registration.Status != DriverRegistration.State.Registered) return null;
        if (selectedCandidate is { } c && SamePath(registration.Library, c.Path)) return c;
        var location = RegisteredLocation(registration);
        if (location is null) return null;
        // Recovery does not depend on the damaged INI. It still requires the
        // registered native library to match an independently checked demo copy
        // from this same distribution. Never remove unknown or changed DLLs.
        try
        {
            var reference = BaseCandidate(BuiltInVehicles.All.Single(v => v.Id == "p2"));
            if (reference is not { } known || !DriverRegistration.Fingerprint(location.Library)
                    .Equals(known.Sha, StringComparison.OrdinalIgnoreCase)) return null;
            return (location.Library, known.Sha);
        }
        catch (Exception) { return null; }
    }

    private string IgnitionLabel(NativeIgnitionSelection? state) => state switch
    {
        NativeIgnitionSelection.Baseline => T("Baseline position", "Исходное положение"),
        NativeIgnitionSelection.PositionIICandidate => T("Position II (lab)", "Положение II (эмуляция)"),
        _ => T("As supplied", "Без изменений")
    };

    private string EngineLabel(EcmScenario? state) => state switch
    {
        EcmScenario.Stationary => T("Stationary", "Двигатель остановлен"),
        EcmScenario.Cranking => T("Cranking", "Запуск"),
        EcmScenario.ColdIdle => T("Cold idle", "Холодный холостой ход"),
        EcmScenario.Warming => T("Warming up", "Прогрев"),
        EcmScenario.WarmIdle => T("Warm idle", "Прогретый холостой ход"),
        EcmScenario.Dynamic => T("Dynamic warmup", "Динамический прогрев"),
        _ => T("As supplied", "Без изменений")
    };

    private void SelectState()
    {
        if (_rendering || _busy || _closed || Selected.Id != LocalVehicleData.Id ||
            _ignition.SelectedIndex < 0 || _engine.SelectedIndex < 0) return;
        _choice = new(_ignitions[_ignition.SelectedIndex], _engines[_engine.SelectedIndex]);
        _resultEn = _resultRu = "";
        Render();
    }

    private string VariantLabel(EquipmentVariant variant)
    {
        var row = _localProfile!.Rows.Single(x => x.Offset == variant.Offset);
        var value = _localProfile.Editor!.Options[variant.Offset].Choices.Single(x => x.Code == variant.Code);
        return row.Name + ": " + value.Text;
    }

    private void RenderVariant(BuiltInVehicle profile, DriverRegistration.Info registration)
    {
        var refs = profile.Id == LocalVehicleData.Id ? _localProfile?.References : null;
        _equipmentVariant.Visibility = _equipmentVariantStatus.Visibility = refs is null ? Visibility.Collapsed : Visibility.Visible;
        if (refs is null) return;
        var all = refs.Variants;
        if (registration.Status == DriverRegistration.State.Registered)
        {
            _selectedVariant = all.FirstOrDefault(v => SamePath(registration.Library,
                EquipmentVariantPackages.Library(AppContext.BaseDirectory, v)));
            if (_selectedVariant is not null) _choice = VehicleStateChoice.Original;
        }
        var visible = all.Where(v => v == _selectedVariant ||
            Directory.Exists(EquipmentVariantPackages.Folder(AppContext.BaseDirectory, v))).ToList();
        _equipmentVariant.Header = T("Configuration for next connection", "Комплектация для подключения");
        _equipmentVariant.Items.Clear();
        _equipmentVariant.Items.Add(new ComboBoxItem { Content = T("Original equipment", "Исходная комплектация") });
        foreach (var variant in visible)
            _equipmentVariant.Items.Add(new ComboBoxItem { Tag = variant, Content = VariantLabel(variant) });
        _equipmentVariant.SelectedIndex = _selectedVariant is null ? 0 :
            visible.FindIndex(v => v == _selectedVariant) + 1;
        _equipmentVariant.IsEnabled = !_busy && registration.Status == DriverRegistration.State.Absent;
        _equipmentVariantStatus.Text = _selectedVariant is null ?
            T("Original configuration selected. Draft changes are separate.", "Выбрана исходная комплектация. Черновик отдельно.") :
            T("Selected configuration: ", "Выбранная комплектация: ") + VariantLabel(_selectedVariant) + "\n" +
            (Candidate(profile) is null
                ? T("Copy unavailable or changed. Connection blocked.", "Копия недоступна или изменена. Подключение заблокировано.")
                : T("Prepared simulator copy. Not proof of a client connection.", "Подготовленная копия эмулятора. Не подтверждение подключения программы."));
    }

    private void RenderState(BuiltInVehicle profile, DriverRegistration.Info registration)
    {
        bool local = profile.Id == LocalVehicleData.Id;
        _statePanel.Visibility = local ? Visibility.Visible : Visibility.Collapsed;
        if (!local) return;
        if (_selectedVariant is not null)
        {
            _choice = VehicleStateChoice.Original;
            _ignition.IsEnabled = _engine.IsEnabled = _prepareState.IsEnabled = false;
            _ignition.Header = T("Ignition", "Зажигание"); _engine.Header = T("Engine", "Двигатель");
            _ignition.Items.Clear(); _engine.Items.Clear();
            _ignition.Items.Add(IgnitionLabel(null)); _engine.Items.Add(EngineLabel(null));
            _ignition.SelectedIndex = _engine.SelectedIndex = 0;
            _prepareState.Content = T("Prepare vehicle state", "Подготовить состояние автомобиля");
            _stateStatus.Text = T("Combined equipment and engine/ignition changes are not yet supported.", "Совместное изменение комплектации, двигателя и зажигания пока недоступно.");
            return;
        }
        byte[]? baseline = null;
        try
        {
            baseline = LocalVehicleData.ReadProfile(AppContext.BaseDirectory);
            _ignitions = VehicleStatePackages.Ignitions(baseline);
            _engines = VehicleStatePackages.Engines(baseline);
        }
        catch (Exception)
        {
            baseline = null;
            _ignitions = new NativeIgnitionSelection?[] { null };
            _engines = new EcmScenario?[] { null };
        }
        if (!_ignitions.Contains(_choice.Ignition) || !_engines.Contains(_choice.Engine))
            _choice = VehicleStateChoice.Original;
        // A registered state must remain identifiable after a process restart.
        // Path recognition is not connection authentication.
        if (registration.Status == DriverRegistration.State.Registered)
            foreach (var i in _ignitions)
                foreach (var e in _engines)
                {
                    var choice = new VehicleStateChoice(i, e);
                    if (SamePath(registration.Library, Path.Combine(VehicleStatePackages.Folder(AppContext.BaseDirectory, choice), "VirtualCarJ2534.dll")))
                        _choice = choice;
                }
        _ignition.Header = T("Ignition", "Зажигание");
        _engine.Header = T("Engine", "Двигатель");
        _ignition.Items.Clear(); _engine.Items.Clear();
        foreach (var i in _ignitions) _ignition.Items.Add(IgnitionLabel(i));
        foreach (var e in _engines) _engine.Items.Add(EngineLabel(e));
        _ignition.SelectedIndex = _ignitions.ToList().IndexOf(_choice.Ignition);
        _engine.SelectedIndex = _engines.ToList().IndexOf(_choice.Engine);
        bool editable = !_busy && baseline is not null && registration.Status == DriverRegistration.State.Absent;
        _ignition.IsEnabled = editable && _ignitions.Count > 1;
        _engine.IsEnabled = editable && _engines.Count > 1;
        _prepareState.Content = T("Prepare vehicle state", "Подготовить состояние автомобиля");
        bool prepared = baseline is not null && Candidate(profile) is not null;
        _prepareState.IsEnabled = !_homePreview && editable && !_choice.IsOriginal && !prepared && BaseCandidate(profile) is not null;
        _stateStatus.Text = (registration.Status != DriverRegistration.State.Absent ?
            T("Disable the adapter and close diagnostic clients before changing states.", "Отключите адаптер и закройте диагностические программы перед изменением состояния.") :
            prepared ? T("Prepared for the next diagnostic connection.", "Подготовлено для следующего диагностического подключения.") :
            T("State not prepared.", "Состояние не подготовлено.")) +
            (_engines.Count == 1 ? "\n" + T("Engine scenarios are unavailable for this reviewed baseline.", "Сценарии двигателя недоступны для этого проверенного профиля.") : "") +
            (_ignitions.Count == 1 ? "\n" + T("Ignition scenarios are unavailable for this baseline.", "Сценарии зажигания недоступны для этого профиля.") : "") +
            "\n" + T("Configured simulation only; not live vehicle state.", "Настроенная эмуляция, не текущее состояние реального автомобиля.");
    }

    private async Task PrepareStateAsync()
    {
        if (_homePreview || _closed || _busy || !_prepareState.IsEnabled || Selected.Id != LocalVehicleData.Id) return;
        var choice = _choice;
        var source = BaseCandidate(Selected);
        if (source is not { } s || DriverRegistration.Read().Status != DriverRegistration.State.Absent) { Render(); return; }
        _busy = true; Render();
        try
        {
            var dialog = new ContentDialog
            {
                XamlRoot = _content.XamlRoot,
                Title = T("Prepare this vehicle state?", "Подготовить состояние автомобиля?"),
                Content = IgnitionLabel(choice.Ignition) + "\n" + EngineLabel(choice.Engine) + "\n\n" +
                    T("Close all diagnostic clients. A separate simulation copy will be created; the original profile is unchanged.",
                      "Закройте все диагностические программы. Будет создана отдельная копия эмулятора; исходный профиль не изменится."),
                PrimaryButtonText = T("Prepare", "Подготовить"), CloseButtonText = T("Cancel", "Отмена"),
                DefaultButton = ContentDialogButton.Close
            };
            if (await dialog.ShowAsync() != ContentDialogResult.Primary || _closed) return;
            if (DriverRegistration.Read().Status != DriverRegistration.State.Absent || BaseCandidate(Selected) != s)
                throw new InvalidOperationException();
            byte[] baseline = LocalVehicleData.ReadProfile(AppContext.BaseDirectory);
            await Task.Run(() => VehicleStatePackages.Prepare(AppContext.BaseDirectory, choice, baseline, s.Sha));
            _resultEn = "State prepared. Enable the adapter to use it.";
            _resultRu = "Состояние подготовлено. Для использования включите адаптер.";
        }
        catch (Exception)
        {
            _resultEn = "Could not prepare the state. Original profile retained.";
            _resultRu = "Не удалось подготовить состояние. Исходный профиль сохранён.";
        }
        finally { _busy = false; if (!_closed) Render(); }
    }

    private async Task PrepareEquipmentAsync()
    {
        if (_homePreview || _busy || _closed || !_equipmentPrepare.IsEnabled || Selected.Id != LocalVehicleData.Id) return;
        var edits = new Dictionary<int, string>(_equipmentEdits);
        _busy = true; Render();
        try
        {
            var dialog = new ContentDialog
            {
                XamlRoot = _content.XamlRoot,
                Title = T("Prepare and select equipment?", "Подготовить и выбрать комплектацию?"),
                Content = T("Close all diagnostic clients. The original stays unchanged. A separate simulator copy will be selected for the next connection. The adapter is not enabled automatically.",
                    "Закройте диагностические программы. Исходный автомобиль останется без изменений. Отдельная копия будет выбрана для следующего подключения. Адаптер автоматически не включается."),
                PrimaryButtonText = T("Prepare", "Подготовить"),
                CloseButtonText = T("Cancel", "Отмена"), DefaultButton = ContentDialogButton.Close
            };
            if (await dialog.ShowAsync() != ContentDialogResult.Primary || _closed) return;
            if (DriverRegistration.Read().Status != DriverRegistration.State.Absent) throw new InvalidOperationException();
            var current = LocalVehicleData.Load(AppContext.BaseDirectory);
            if (current.Vehicle != Selected || current.Editor is not { } editor || current.References is not { } refs)
                throw new InvalidDataException();
            byte[] baseline = LocalVehicleData.ReadProfile(AppContext.BaseDirectory);
            var edit = edits.Single();
            var variant = refs.Variants.Single(v => v.Offset == edit.Key && v.Code == edit.Value);
            var source = BaseCandidate(Selected) ?? throw new InvalidDataException();
            await Task.Run(() =>
            {
                refs.Prepare(AppContext.BaseDirectory, editor, baseline, edits);
                EquipmentVariantPackages.Prepare(AppContext.BaseDirectory, editor, refs, baseline, source.Sha, variant);
            });
            if (DriverRegistration.Read().Status != DriverRegistration.State.Absent) throw new InvalidOperationException();
            _selectedVariant = variant;
            _choice = VehicleStateChoice.Original;
            _resultEn = "Equipment copy prepared and selected. Enable the adapter separately.";
            _resultRu = "Копия комплектации подготовлена и выбрана. Включите адаптер отдельно.";
        }
        catch (Exception)
        {
            _resultEn = "Equipment copy not prepared.";
            _resultRu = "Не удалось подготовить копию комплектации.";
        }
        finally { _busy = false; if (!_closed) Render(); }
    }

    private string EquipmentFinding(string id) => id switch
    {
        "PETROL_HEATER" => T("Diesel heater is incompatible with the petrol scenario.", "Дизельный отопитель несовместим с бензиновым двигателем."),
        "AUTO_STARTBLOCK" => T("Starter interlock does not match automatic transmission.", "Блокировка запуска не соответствует автоматической коробке."),
        "AC_HEATER_ONLY" => T("Air conditioning conflicts with the selected heater.", "Кондиционер несовместим с выбранным отопителем."),
        "AC_REAR" => T("Rear air conditioning requires air conditioning.", "Задний кондиционер требует наличия кондиционера."),
        "AC_CLIMATE" => T("Climate unit conflicts with air conditioning selection.", "Климатический блок не соответствует выбору кондиционера."),
        "AQS_FILTER" => T("Review air quality system and filter selection.", "Проверьте систему качества воздуха и фильтр."),
        "PARK_AEM" => T("Parking assistance requires the accessory module.", "Парковочный ассистент требует блока дополнительного оборудования."),
        "AIRBAG_SWITCH" => T("Passenger airbag switch requires a passenger airbag.", "Выключатель подушки требует наличия пассажирской подушки."),
        "OWS_CAL" => T("Occupant weight calibration requires the weight sensor system.", "Калибровка веса пассажира требует соответствующего датчика."),
        "TPMS_LOAD" => T("Tyre pressure and heavy-load warning selections disagree.", "Настройки контроля давления шин и предупреждения о нагрузке не совпадают."),
        "XENON_ADJUST" => T("Active bi-xenon requires automatic adjustment in this scenario.", "Активный биксенон требует автоматической регулировки в этом сценарии."),
        "ALARM_OPTIONS" => T("Review alarm accessories.", "Проверьте дополнительное оборудование сигнализации."),
        "HEATER_CALL" => T("Review remote heater start and heater equipment.", "Проверьте дистанционный запуск отопителя и его наличие."),
        "RTI_CONTROL" => T("Review navigation system and control unit.", "Проверьте навигационную систему и её блок управления."),
        "AUDIO_AMP" => T("Review radio and amplifier selection.", "Проверьте магнитолу и усилитель."),
        "AUDIO_SYSTEM" => T("Review infotainment equipment.", "Проверьте комплектацию мультимедийной системы."),
        _ => T("Review selection.", "Проверьте выбранное значение.")
    };

    private void RenderEquipment(bool local)
    {
        _equipmentRendering = true;
        try
        {
            var editor = local ? _localProfile?.Editor : null;
            _equipmentEditor.Visibility = editor is null ? Visibility.Collapsed : Visibility.Visible;
            if (editor is null) return;
            _equipmentParameter.Header = T("Equipment parameter", "Параметр комплектации");
            _equipmentValue.Header = T("Value", "Значение");
            _equipmentReset.Content = T("Reset draft", "Сбросить изменения");
            var rows = _localProfile!.Rows;
            var selectable = rows.Where(r => editor.Options[r.Offset].Choices.Count > 0).ToList();
            if (!selectable.Any(r => r.Offset == _equipmentOffset))
                _equipmentOffset = selectable.FirstOrDefault()?.Offset ?? -1;
            _equipmentParameter.Items.Clear();
            foreach (var row in selectable)
                _equipmentParameter.Items.Add(new ComboBoxItem { Tag = row.Offset,
                    Content = row.Name + (_equipmentEdits.ContainsKey(row.Offset) ? " *" : "") });
            _equipmentParameter.SelectedIndex = selectable.FindIndex(r => r.Offset == _equipmentOffset);
            _equipmentValue.Items.Clear();
            if (_equipmentOffset >= 0)
            {
                var row = rows.Single(r => r.Offset == _equipmentOffset);
                var options = editor.Options[_equipmentOffset];
                _equipmentValue.Items.Add(new ComboBoxItem { Tag = options.BaselineCode, Content = row.Value + T(" (original)", " (исходное)") });
                foreach (var option in options.Choices)
                    _equipmentValue.Items.Add(new ComboBoxItem { Tag = option.Code, Content = option.Text });
                string selected = _equipmentEdits.GetValueOrDefault(_equipmentOffset, options.BaselineCode);
                _equipmentValue.SelectedIndex = _equipmentValue.Items.Cast<ComboBoxItem>().ToList().FindIndex(x => Equals(x.Tag, selected));
            }
            var preview = editor.Preview(_equipmentEdits);
            _equipmentParameter.IsEnabled = !_busy && selectable.Count > 0;
            _equipmentValue.IsEnabled = !_busy && _equipmentOffset >= 0;
            _equipmentReset.IsEnabled = !_busy && _equipmentEdits.Count > 0;
            _equipmentPrepare.Content = T("Prepare and select equipment", "Подготовить и выбрать комплектацию");
            bool eligible = preview.Status == "pass" && _localProfile.References?.Supports(_equipmentEdits) == true;
            _equipmentPrepare.IsEnabled = !_homePreview && !_busy && eligible && DriverRegistration.Read().Status == DriverRegistration.State.Absent;
            string status = preview.Status switch
            {
                "blocked" => T("Incompatible selection", "Несовместимые параметры"),
                "review" => T("Review required", "Требуется проверка"),
                _ => T("Lab checks passed", "Лабораторная проверка пройдена")
            };
            _equipmentStatus.Text = T("Draft only · changed: ", "Только черновик · изменено: ") + preview.ChangedCount + " · " + status +
                (preview.Errors.Count == 0 ? "" : "\n" + T("Errors: ", "Ошибки: ") + string.Join("\n", preview.Errors.Select(EquipmentFinding))) +
                (preview.Warnings.Count == 0 ? "" : "\n" + T("Warnings: ", "Предупреждения: ") + string.Join("\n", preview.Warnings.Select(EquipmentFinding))) +
                (preview.TopologyReview ? "\n" + T("Equipment topology requires review.", "Требуется проверка состава оборудования.") : "") +
                "\n" + T("Draft selection is separate from the configuration used for connection.", "Черновик не меняет комплектацию, выбранную для подключения.") +
                "\n" + (eligible ? T("Independent reference available for this selection.", "Есть эталон исходного компилятора для выбранного изменения.") : T("Preparation requires a referenced single change without warnings.", "Подготовка требует одного изменения с эталоном и без предупреждений."));
        }
        finally { _equipmentRendering = false; }
    }

    private void UpdatePhotoCaption(string vehicleId)
    {
        var info = VehicleArtwork.ForVehicle(vehicleId);
        _photoCaption.Text = info is null ?
            T("Generic diagnostic profile · no specific vehicle model", "Универсальный профиль · конкретная модель не задана") :
            _photoReady ? T(info.CaptionEn, info.CaptionRu) + " · " + T("Photo: ", "Фото: ") + info.Author :
            T("Reference photograph unavailable", "Фото модели недоступно");
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(_vehiclePhoto,
            info is null ? "" : T(info.CaptionEn, info.CaptionRu));
    }

    private async Task UpdatePhotoAsync(string vehicleId)
    {
        if (_photoVehicleId == vehicleId)
        {
            UpdatePhotoCaption(vehicleId);
            return;
        }
        _photoVehicleId = vehicleId;
        int request = ++_photoRequest;
        _photoReady = false;
        _vehiclePhoto.Source = null;
        _vehiclePhoto.Visibility = Visibility.Collapsed;
        UpdatePhotoCaption(vehicleId);
        var info = VehicleArtwork.ForVehicle(vehicleId);
        if (info is null) return;
        try
        {
            byte[] bytes = await Task.Run(() => VehicleArtwork.Load(AppContext.BaseDirectory, vehicleId));
            if (_closed || request != _photoRequest) return;
            using var stream = new Windows.Storage.Streams.InMemoryRandomAccessStream();
            using (var writer = new Windows.Storage.Streams.DataWriter(stream))
            {
                writer.WriteBytes(bytes);
                await writer.StoreAsync();
                writer.DetachStream();
            }
            stream.Seek(0);
            var bitmap = new Microsoft.UI.Xaml.Media.Imaging.BitmapImage();
            await bitmap.SetSourceAsync(stream);
            if (_closed || request != _photoRequest) return;
            if (bitmap.PixelWidth != info.Width || bitmap.PixelHeight != info.Height)
                throw new InvalidDataException();
            _vehiclePhoto.Source = bitmap;
            _vehiclePhoto.Visibility = Visibility.Visible;
            _photoReady = true;
            UpdatePhotoCaption(vehicleId);
        }
        catch (Exception)
        {
            if (_closed || request != _photoRequest) return;
            _vehiclePhoto.Source = null;
            _vehiclePhoto.Visibility = Visibility.Collapsed;
            _photoReady = false;
            UpdatePhotoCaption(vehicleId);
        }
    }

    private void Render()
    {
        if (_closed || _rendering) return;
        _rendering = true;
        try
        {
            var registration = DriverRegistration.Read();
            var registered = RegisteredLocation(registration);
            int selection = Math.Max(0, _vehicle.SelectedIndex);
            if (registered is not null)
            {
                int index = _profiles.FindIndex(v => v.Id == registered.VehicleId);
                if (index >= 0) selection = index;
            }
            for (int i = 0; i < _profiles.Count; i++)
                ((ComboBoxItem)_vehicle.Items[i]).Content = T(_profiles[i].NameEn, _profiles[i].NameRu);
            _vehicle.SelectedIndex = -1; _vehicle.SelectedIndex = selection;
            var profile = Selected;
            _heading.Text = "Virtual Car";
            _languageNotice.Text = T("Language preference could not be saved.", "Не удалось сохранить выбранный язык.");
            _languageNotice.Visibility = _languageSaveFailed ? Visibility.Visible : Visibility.Collapsed;
            _subheading.Text = _homePreview ? T("Read-only interface preview", "Просмотр интерфейса без записи") : T("Your virtual vehicle", "Ваш виртуальный автомобиль");
            _localNotice.Visibility = _localAvailability == LocalVehicleData.Availability.Invalid ? Visibility.Visible : Visibility.Collapsed;
            _localNotice.Text = T("The local XC90 V8 profile could not be validated. Demonstration profiles are visible, but enabling the adapter is blocked. Repair the package and restart Virtual Car.",
                "Локальный профиль XC90 V8 не прошёл проверку. Демонстрационные профили доступны для просмотра, но включение адаптера заблокировано. Восстановите пакет и перезапустите Virtual Car.");
            _connectionTitle.Text = T("Connection", "Подключение");
            _stateTitle.Text = T("Vehicle state", "Состояние автомобиля");
            _equipmentTitle.Text = T("Equipment", "Комплектация");
            _vehicle.Header = T("Choose a vehicle", "Выберите автомобиль");
            _name.Text = T(profile.NameEn, profile.NameRu);
            _ = UpdatePhotoAsync(profile.Id);
            _description.Text = T(profile.DescriptionEn, profile.DescriptionRu);
            bool local = profile.Id == LocalVehicleData.Id;
            _identity.Text = (local ? "VIN: " : T("Demo VIN: ", "Демонстрационный VIN: ")) + profile.Vin;
            _configuration.Visibility = local ? Visibility.Visible : Visibility.Collapsed;
            _hasDetails = local;
            ApplyLayout(_dashboard.ActualWidth);
            if (_stateCard is not null) _stateCard.Visibility = local ? Visibility.Visible : Visibility.Collapsed;
            if (_equipmentCard is not null) _equipmentCard.Visibility = local ? Visibility.Visible : Visibility.Collapsed;
            _equipmentHint.Text = local && _localProfile is not null ? T("Equipment parameters: ", "Параметры комплектации: ") + _localProfile.Rows.Count +
                T(" · protected: ", " · защищено: ") + _localProfile.Rows.Count(x => x.Locked) +
                "\n" + T("Equipment names and values retain their original catalog language.", "Названия и значения сохраняются на языке исходного каталога.") : "";
            _configuration.Header = local && _localProfile?.Editor is not null ? T("Vehicle equipment · draft", "Комплектация автомобиля · черновик") : T("Vehicle equipment · read only", "Комплектация автомобиля · просмотр");
            _configurationRows.Items.Clear();
            if (local && _localProfile is not null)
                foreach (var row in _localProfile.Rows)
                    _configurationRows.Items.Add(new TextBlock { TextWrapping = TextWrapping.Wrap,
                        Text = row.Name + ": " + (_equipmentEdits.TryGetValue(row.Offset, out var code) && _localProfile.Editor is { } editor
                            ? editor.Options[row.Offset].Choices.Single(x => x.Code == code).Text + " *" : row.Value) +
                            (row.Locked ? T(" (protected)", " (защищено)") : "") });
            else _configuration.IsExpanded = false;
            RenderEquipment(local);
            var slots = local ? 8 : NativeEcuInventory.Inspect(BuiltInVehicles.ReadProfile(profile.Id)).Count;
            _modules.Text = T("Configured routes: ", "Настроено маршрутов: ") + slots +
                T(" · not an ECU discovery result", " · не результат поиска блоков");
            _availability.Text = local ? T("Equipment snapshot included. Select prepared configuration separately.", "Комплектация включена. Подготовленная конфигурация выбирается отдельно.") :
                T("Engine and ignition controls require a reviewed vehicle profile. Advanced configuration remains available.",
                "Управление двигателем и зажиганием требует проверенного профиля. Расширенная настройка доступна отдельно.");
            RenderVariant(profile, registration);
            RenderState(profile, registration);
            var candidate = Candidate(profile);
            bool own = candidate is { } c && registration.Status == DriverRegistration.State.Registered &&
                SamePath(registration.Library, c.Path);
            var disconnectCandidate = DisconnectCandidate(registration, candidate);
            bool activationCandidate = candidate is not null && (_localAvailability != LocalVehicleData.Availability.Invalid || own);
            var connection = HomeConnectionPlan.Create(registration.Status switch
            {
                DriverRegistration.State.Absent => HomeRegistration.Absent,
                DriverRegistration.State.Registered => HomeRegistration.Registered,
                _ => HomeRegistration.Review
            }, activationCandidate, own, _busy, disconnectCandidate is not null);
            _status.Text = connection.State switch
            {
                HomeConnectionState.Ready => T("Ready to connect", "Готов к подключению"),
                HomeConnectionState.Unavailable => T("Simulation not ready", "Эмуляция не подготовлена"),
                HomeConnectionState.Owned => T("Adapter enabled", "Адаптер включён"),
                HomeConnectionState.Other => T("Another adapter profile is active", "Активен другой профиль адаптера"),
                HomeConnectionState.Recovery => T("Registered profile requires recovery", "Зарегистрированный профиль требует восстановления"),
                _ => T("Connection requires review in advanced mode", "Требуется проверка подключения в расширенном режиме")
            };
            _connect.Content = T("Enable adapter", "Включить адаптер");
            _disconnect.Content = T("Disable adapter", "Отключить адаптер");
            _refresh.Content = T("Refresh", "Обновить");
            _advanced.Content = T("Advanced settings", "Расширенные настройки");
            _vehicle.IsEnabled = _language.IsEnabled = _advanced.IsEnabled = _refresh.IsEnabled = !_busy;
            _vehicle.IsEnabled = !_busy && registration.Status == DriverRegistration.State.Absent;
            _advanced.IsEnabled = !_homePreview && !_busy;
            _connect.IsEnabled = !_homePreview && _localAvailability != LocalVehicleData.Availability.Invalid && connection.CanEnable;
            _disconnect.IsEnabled = !_homePreview && connection.CanDisable;
            bool showDisconnect = connection.State is HomeConnectionState.Owned or HomeConnectionState.Recovery;
            _connect.Visibility = showDisconnect ? Visibility.Collapsed : Visibility.Visible;
            _disconnect.Visibility = showDisconnect ? Visibility.Visible : Visibility.Collapsed;
            _notice.Text = (connection.State switch
            {
                HomeConnectionState.Ready => T("Enable the adapter, then open your diagnostic program.", "Включите адаптер, затем откройте диагностическую программу."),
                HomeConnectionState.Owned => T("Open your diagnostic program. Close it before disabling the adapter.", "Откройте диагностическую программу. Закройте её перед отключением адаптера."),
                HomeConnectionState.Unavailable => T("Check that the selected vehicle or state is prepared.", "Проверьте подготовку выбранного автомобиля или состояния."),
                HomeConnectionState.Recovery => T("Close diagnostic clients, then disable this registered adapter. No profile files will be changed.", "Закройте диагностические программы и отключите зарегистрированный адаптер. Файлы профилей не изменятся."),
                _ => T("Check the connection in advanced settings.", "Проверьте подключение в расширенных настройках.")
            }) + "\n" + T("VIDA compatibility is not yet confirmed.", "Совместимость с VIDA пока не подтверждена.") +
                (string.IsNullOrEmpty(_resultEn) ? "" : "\n" + T(_resultEn, _resultRu));
        }
        finally { _rendering = false; }
    }

    private async Task ChangeAsync(bool enable)
    {
        if (_homePreview || _busy || _closed || (enable && _localAvailability == LocalVehicleData.Availability.Invalid) ||
            !(enable ? _connect.IsEnabled : _disconnect.IsEnabled)) return;
        var profile = Selected;
        var candidate = enable ? Candidate(profile) : DisconnectCandidate(DriverRegistration.Read(), Candidate(profile));
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
            var before = DriverRegistration.Read();
            var now = enable ? Candidate(profile) : DisconnectCandidate(before, Candidate(profile));
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
