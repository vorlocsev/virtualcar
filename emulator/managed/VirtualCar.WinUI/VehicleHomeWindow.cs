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
    private readonly TextBlock _equipmentStatus = new() { TextWrapping = TextWrapping.Wrap };
    private readonly StackPanel _equipmentEditor = new() { Spacing = 8 };
    private readonly Dictionary<int, string> _equipmentEdits = new();
    private int _equipmentOffset = -1;
    private bool _equipmentRendering;
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
        foreach (var item in new FrameworkElement[] { _ignition, _engine, _prepareState, _stateStatus })
            _statePanel.Children.Add(item);
        _content.Children.Add(_statePanel);
        Id(_ignition, "VC094C.Ignition"); Id(_engine, "VC094C.Engine");
        Id(_prepareState, "VC094C.Prepare"); Id(_stateStatus, "VC094C.State.Status");
        _ignition.SelectionChanged += (_, _) => SelectState();
        _engine.SelectionChanged += (_, _) => SelectState();
        _prepareState.Click += async (_, _) => await PrepareStateAsync();
        var equipmentContent = new StackPanel { Spacing = 8 };
        equipmentContent.Children.Add(_configurationRows);
        foreach (var item in new FrameworkElement[] { _equipmentParameter, _equipmentValue, _equipmentReset, _equipmentStatus })
            _equipmentEditor.Children.Add(item);
        equipmentContent.Children.Add(_equipmentEditor);
        _configuration.Content = equipmentContent;
        Id(_equipmentParameter, "VC094D.Equipment.Parameter"); Id(_equipmentValue, "VC094D.Equipment.Value");
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
        if (candidate is not { } c || profile.Id != LocalVehicleData.Id || _choice.IsOriginal)
            return candidate;
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

    private void RenderState(BuiltInVehicle profile, DriverRegistration.Info registration)
    {
        bool local = profile.Id == LocalVehicleData.Id;
        _statePanel.Visibility = local ? Visibility.Visible : Visibility.Collapsed;
        if (!local) return;
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
        _prepareState.IsEnabled = editable && !_choice.IsOriginal && !prepared && BaseCandidate(profile) is not null;
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
        if (_closed || _busy || !_prepareState.IsEnabled || Selected.Id != LocalVehicleData.Id) return;
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
                "\n" + T("Nothing is applied to the simulator or vehicle.", "Изменения не применяются к эмулятору или автомобилю.");
        }
        finally { _equipmentRendering = false; }
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
            _modules.Text = T("Configured diagnostic routes: ", "Настроено диагностических маршрутов: ") + slots +
                T(" (not ECU discovery)", " (не обнаружение блоков)");
            _availability.Text = local ? T("Equipment snapshot included. Draft changes are not applied to the simulator.", "Комплектация включена. Черновик не применяется к эмулятору.") :
                T("Engine and ignition controls require a reviewed vehicle profile. Advanced configuration remains available.",
                "Управление двигателем и зажиганием требует проверенного профиля. Расширенная настройка доступна отдельно.");
            var registration = DriverRegistration.Read();
            RenderState(profile, registration);
            var candidate = Candidate(profile);
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
