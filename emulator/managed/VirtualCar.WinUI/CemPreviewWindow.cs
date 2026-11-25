using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VirtualCar.Core;
using VirtualCar.DriverTool;
using System.Diagnostics;

namespace VirtualCar.WinUI;

// Standalone laboratory UI. No direct ECU I/O; local profile and provider mutations require confirmation.
public sealed class CemPreviewWindow : Window
{
    private readonly TextBox _python = new() { Header = "Python.exe (absolute path)" };
    private readonly TextBox _script = new() { Header = "vc071_view.py (absolute path)" };
    private readonly TextBox _data = new() { Header = "Local CEM529 directory (outside Git)" };
    private readonly TextBox _search = new() { PlaceholderText = "Search by name or offset" };
    private readonly ComboBox _filter = new() { MinWidth = 150 };
    private readonly ListView _rows = new() { SelectionMode = ListViewSelectionMode.Single };
    private readonly ComboBox _options = new() { HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly TextBlock _counts = new() { Text = "No profile loaded" };
    private readonly TextBlock _detail = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _audit = new() { TextWrapping = TextWrapping.Wrap, IsTextSelectionEnabled = true };
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Button _load = new() { Content = "Load profile" };
    private readonly Button _cancel = new() { Content = "Cancel" };
    private readonly Button _reset = new() { Content = "Close profile" };
    private readonly Button _preview = new() { Content = "Preview selection" };
    private readonly Button _revert = new() { Content = "Revert to baseline" };
    private readonly Button _clear = new() { Content = "Reset all changes" };
    private readonly ComboBox _language = new() { MinWidth = 88 };
    private readonly TextBlock _heading = new() { FontSize = 28 };
    private readonly ListView _navigation = new() { SelectionMode = ListViewSelectionMode.Single, MinWidth = 180 };
    private readonly Grid _editor = new() { RowSpacing = 12 };
    private readonly StackPanel _placeholder = new() { Spacing = 12, Padding = new Thickness(12) };
    private readonly ScrollViewer _workspaceScroll = new() { VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
    private readonly TextBlock _placeholderHeading = new() { FontSize = 24, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _placeholderText = new() { TextWrapping = TextWrapping.Wrap };
    private readonly StackPanel _monitorPanel = new() { Spacing = 8 };
    private readonly TextBox _monitorPath = new();
    private readonly Button _monitorStart = new();
    private readonly Button _monitorStop = new();
    private readonly Button _monitorRefresh = new();
    private readonly ComboBox _monitorDirection = new() { MinWidth = 120 };
    private readonly TextBox _monitorFilter = new();
    private readonly ComboBox _monitorView = new() { MinWidth = 180 };
    private readonly TextBlock _journalSummary = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _monitorStatus = new() { TextWrapping = TextWrapping.Wrap };
    private readonly ListView _monitorRows = new() { MaxHeight = 300, SelectionMode = ListViewSelectionMode.None };
    private Microsoft.UI.Dispatching.DispatcherQueueTimer? _monitorTimer;
    private NativeTraceSnapshot? _monitorSnapshot;
    private bool _monitorRunning;
    private bool _monitorFailed;
    private readonly StackPanel _modulePanel = new() { Spacing = 10 };
    private readonly Button _moduleRefresh = new();
    private readonly TextBlock _moduleStatus = new() { TextWrapping = TextWrapping.Wrap };
    private readonly ListView _moduleList = new() { MaxHeight = 360, SelectionMode = ListViewSelectionMode.None };
    private IReadOnlyList<NativeEcuSlot>? _moduleSlots;
    private bool _moduleFailed;
    private readonly StackPanel _vehiclePanel = new() { Spacing = 10 };
    private readonly TextBox _vehicleProfile = new();
    private readonly ComboBox _vehicleScenario = new() { MinWidth = 220 };
    private readonly TextBlock _vehicleInfo = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBox _vehiclePatch = new() { IsReadOnly = true, AcceptsReturn = true, TextWrapping = TextWrapping.Wrap };
    private readonly Button _vehicleInspect = new();
    private readonly Button _vehicleApply = new();
    private readonly ComboBox _ignition = new() { MinWidth = 220 };
    private readonly TextBlock _ignitionInfo = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Button _ignitionApply = new();
    private readonly TextBox _vehicleBackup = new();
    private readonly Button _vehicleRestore = new();
    private readonly TextBlock _vehicleResult = new() { TextWrapping = TextWrapping.Wrap };
    private string? _inspectedPath;
    private bool _vehicleBusy;
    private string _vehicleResultEn = "";
    private string _vehicleResultRu = "";
    private byte[]? _vehicleBytes;
    private bool _vehicleUpdating;
    private bool _vehicleFailed;
    private readonly StackPanel _driverPanel = new() { Spacing = 10 };
    private readonly TextBox _driverPath = new();
    private readonly TextBlock _driverStatus = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _driverResult = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Button _driverRefresh = new();
    private readonly Button _driverInstall = new();
    private readonly Button _driverRemove = new();
    private DriverRegistration.Info _driverInfo = new(DriverRegistration.State.Unavailable, null);
    private bool _driverBusy;
    private string _driverResultEn = "";
    private string _driverResultRu = "";
    private enum Section { Vehicle, Configuration, Modules, Diagnostics, Connection }
    private Section _section = Section.Configuration;
    private readonly TextBlock _subtitle = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _parameterHeading = new() { FontSize = 20 };
    private readonly TextBlock _auditHeading = new() { FontSize = 20 };
    private readonly UiLanguageSettings? _languageSettings;
    private readonly TextBlock _languageNotice = new() { TextWrapping = TextWrapping.Wrap };
    private readonly bool _ephemeral;
    private bool _languageSaveFailed;
    private bool _russian;
    private string _statusEn = "";
    private string _statusRu = "";
    private string T(string en, string ru) => _russian ? ru : en;
    private readonly ProgressRing _progress = new() { Width = 24, Height = 24 };
    private CemPreviewViewModel? _model;
    private CancellationTokenSource? _operation;
    private Dictionary<int, string> _edits = new();
    private bool _closed;
    private bool _rebuilding;
    private bool Busy => _operation is not null || _driverBusy || _vehicleBusy;
    private CemPreview? Snapshot => _model?.Snapshot;
    private CemRow? Selected => (_rows.SelectedItem as ListViewItem)?.Tag as CemRow;

    public CemPreviewWindow(bool ephemeral = false)
    {
        _ephemeral = ephemeral;
        if (!ephemeral)
        {
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            if (Path.IsPathFullyQualified(local))
                _languageSettings = new UiLanguageSettings(Path.Combine(local, "VirtualCar", "WinUI", "language.v1"));
            _russian = _languageSettings?.Load() == UiLanguage.Russian;
        }
        Title = "Virtual Car — CEM529 Preview";
        var shell = new Grid { Padding = new Thickness(20), RowSpacing = 12 };
        shell.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        shell.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        var body = new Grid { ColumnSpacing = 16 };
        body.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(190) });
        body.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        AutomationId(_navigation, "VC077.Navigation");
        foreach (Section section in Enum.GetValues<Section>())
        {
            var item = new ListViewItem { Tag = section, Content = SectionLabel(section) };
            AutomationId(item, "VC077.Nav." + section);
            _navigation.Items.Add(item);
            if (section == _section) _navigation.SelectedItem = item;
        }
        Add(body, _navigation, 0);
        var page = new Grid();
        _placeholder.Children.Add(_placeholderHeading);
        _placeholder.Children.Add(_placeholderText);
        _monitorPanel.Children.Add(_monitorPath);
        var monitorActions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        monitorActions.Children.Add(_monitorStart);
        monitorActions.Children.Add(_monitorStop);
        monitorActions.Children.Add(_monitorRefresh);
        _monitorPanel.Children.Add(monitorActions);
        foreach (string label in new[] { "All", "TX", "RX" })
            _monitorDirection.Items.Add(new ComboBoxItem { Content = label });
        _monitorDirection.SelectedIndex = 0;
        _monitorPanel.Children.Add(_monitorDirection);
        var canView = new ComboBoxItem { Content = "CAN Monitor" };
        var journalView = new ComboBoxItem { Content = "Diagnostic journal" };
        AutomationId(canView, "VC086.View.Can");
        AutomationId(journalView, "VC086.View.Journal");
        _monitorView.Items.Add(canView);
        _monitorView.Items.Add(journalView);
        _monitorView.SelectedIndex = 0;
        _monitorPanel.Children.Add(_monitorView);
        _monitorPanel.Children.Add(_journalSummary);
        AutomationId(_monitorView, "VC085.Diagnostics.View");
        AutomationId(_journalSummary, "VC085.Diagnostics.Summary");
        _monitorView.SelectionChanged += (_, _) => RenderMonitor();
        _monitorPanel.Children.Add(_monitorFilter);
        _monitorPanel.Children.Add(_monitorStatus);
        _monitorPanel.Children.Add(_monitorRows);
        _placeholder.Children.Add(_monitorPanel);
        if (!_ephemeral) _monitorPath.Text = Path.Combine(Path.GetTempPath(), NativeCanTrace.LegacyLogFile);
        AutomationId(_monitorStart, "VC084.Monitor.Start");
        AutomationId(_monitorStop, "VC084.Monitor.Stop");
        AutomationId(_monitorRefresh, "VC084.Monitor.Refresh");
        _monitorStart.Click += (_, _) => StartMonitor();
        _monitorStop.Click += (_, _) => { StopMonitor(); RenderMonitor(); };
        _monitorRefresh.Click += (_, _) => ReadMonitor();
        _monitorPath.TextChanged += (_, _) => { StopMonitor(); _monitorSnapshot = null; _monitorFailed = false; RenderMonitor(); };
        _monitorDirection.SelectionChanged += (_, _) => RenderMonitor();
        _monitorFilter.TextChanged += (_, _) => RenderMonitor();
        _modulePanel.Children.Add(_moduleRefresh);
        _modulePanel.Children.Add(_moduleStatus);
        _modulePanel.Children.Add(_moduleList);
        _placeholder.Children.Add(_modulePanel);
        AutomationId(_moduleRefresh, "VC083.Modules.Refresh");
        AutomationId(_moduleStatus, "VC083.Modules.Status");
        _moduleRefresh.Click += (_, _) => InspectModules();
        _vehiclePanel.Children.Add(_vehicleProfile);
        _vehiclePanel.Children.Add(_vehicleInspect);
        _vehiclePanel.Children.Add(_vehicleScenario);
        _vehiclePanel.Children.Add(_vehicleInfo);
        _vehiclePanel.Children.Add(_vehiclePatch);
        _vehiclePanel.Children.Add(_vehicleApply);
        foreach (NativeIgnitionSelection choice in Enum.GetValues<NativeIgnitionSelection>())
            _ignition.Items.Add(new ComboBoxItem { Tag = choice, Content = IgnitionLabel(choice) });
        _ignition.SelectedIndex = 0;
        _vehiclePanel.Children.Add(_ignition);
        _vehiclePanel.Children.Add(_ignitionInfo);
        _vehiclePanel.Children.Add(_ignitionApply);
        AutomationId(_ignitionApply, "VC082.Ignition.Apply");
        AutomationId(_ignition, "VC082.Ignition.Selection");
        _ignitionApply.Click += async (_, _) => await ApplyVehicleAsync(ignition: true);
        _ignition.SelectionChanged += (_, _) => { if (!_vehicleUpdating) RenderIgnition(); };
        _vehiclePanel.Children.Add(_vehicleBackup);
        _vehiclePanel.Children.Add(_vehicleRestore);
        AutomationId(_vehicleRestore, "VC081.Vehicle.Restore");
        _vehicleRestore.Click += async (_, _) => await RestoreVehicleAsync();
        _vehicleBackup.TextChanged += (_, _) => RenderVehicle();
        _vehiclePanel.Children.Add(_vehicleResult);
        AutomationId(_vehicleApply, "VC080.Vehicle.Apply");
        _vehicleApply.Click += async (_, _) => await ApplyVehicleAsync();
        _placeholder.Children.Add(_vehiclePanel);
        foreach (EcmScenario scenario in Enum.GetValues<EcmScenario>())
            _vehicleScenario.Items.Add(new ComboBoxItem { Tag = scenario, Content = ScenarioLabel(scenario) });
        _vehicleScenario.SelectedIndex = 0;
        AutomationId(_vehicleInspect, "VC079.Vehicle.Inspect");
        AutomationId(_vehicleScenario, "VC079.Vehicle.Scenario");
        _vehicleInspect.Click += (_, _) => InspectVehicle();
        _vehicleProfile.TextChanged += (_, _) =>
        {
            _vehicleBytes = null;
            _inspectedPath = null;
            _vehicleBackup.Text = "";
            _vehicleFailed = false;
            VehicleResult("", "");
            RenderVehicle();
        };
        _vehicleScenario.SelectionChanged += (_, _) => { if (!_vehicleUpdating) RenderVehicle(); };
        _driverPanel.Children.Add(_driverStatus);
        _driverPanel.Children.Add(_driverPath);
        var driverActions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        driverActions.Children.Add(_driverRefresh);
        driverActions.Children.Add(_driverInstall);
        driverActions.Children.Add(_driverRemove);
        _driverPanel.Children.Add(driverActions);
        _driverPanel.Children.Add(_driverResult);
        _placeholder.Children.Add(_driverPanel);
        AutomationId(_driverInstall, "VC078.Driver.Install");
        AutomationId(_driverRemove, "VC078.Driver.Remove");
        AutomationId(_driverRefresh, "VC078.Driver.Refresh");
        AutomationId(_driverStatus, "VC078.Driver.Status");
        _driverRefresh.Click += (_, _) => RefreshDriver();
        _driverInstall.Click += async (_, _) => await ChangeDriverAsync(true);
        _driverRemove.Click += async (_, _) => await ChangeDriverAsync(false);
        AutomationId(_placeholderHeading, "VC077.PlaceholderHeading");
        AutomationId(_placeholderText, "VC077.PlaceholderText");
        page.Children.Add(_editor);
        _workspaceScroll.Content = _placeholder;
        page.Children.Add(_workspaceScroll);
        Add(body, page, 0, 1);
        Add(shell, body, 1);
        var root = _editor;
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var header = new Grid { ColumnSpacing = 16 };
        header.ColumnDefinitions.Add(new ColumnDefinition());
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var heading = new StackPanel { Spacing = 4 };
        heading.Children.Add(_heading);
        heading.Children.Add(_subtitle);
        var english = new ComboBoxItem { Content = "EN" };
        var russian = new ComboBoxItem { Content = "RU" };
        AutomationId(english, "VC075.Language.EN");
        AutomationId(russian, "VC075.Language.RU");
        _language.Items.Add(english);
        _language.Items.Add(russian);
        _language.SelectedIndex = _russian ? 1 : 0;
        AutomationId(_language, "VC075.Language");
        AutomationId(_heading, "VC075.Heading");
        AutomationId(_load, "VC075.Load");
        AutomationId(_search, "VC075.Search");
        AutomationId(_filter, "VC075.Filter");
        AutomationId(_auditHeading, "VC075.AuditHeading");
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(_language, "Language / Язык");
        Add(header, heading, 0);
        var languagePanel = new StackPanel { Spacing = 4, MaxWidth = 220 };
        languagePanel.Children.Add(_language);
        languagePanel.Children.Add(_languageNotice);
        Add(header, languagePanel, 0, 1);
        Add(shell, header, 0);

        var inputs = new Grid { ColumnSpacing = 12, RowSpacing = 8 };
        for (int i = 0; i < 3; i++) inputs.ColumnDefinitions.Add(new ColumnDefinition());
        inputs.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        inputs.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        Add(inputs, _python, 0, 0); Add(inputs, _script, 0, 1); Add(inputs, _data, 0, 2);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(_load); actions.Children.Add(_cancel); actions.Children.Add(_reset);
        actions.Children.Add(_progress);
        Grid.SetColumnSpan(actions, 3);
        Add(inputs, actions, 1);
        Add(root, inputs, 0);

        var filters = new Grid { ColumnSpacing = 12 };
        filters.ColumnDefinitions.Add(new ColumnDefinition());
        filters.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        filters.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        foreach (string item in new[] { "All", "Changed", "Locked", "Editable" }) _filter.Items.Add(new ComboBoxItem { Content = item });
        _filter.SelectedIndex = 0;
        Add(filters, _search, 0); Add(filters, _filter, 0, 1); Add(filters, _counts, 0, 2);
        Add(root, filters, 1);

        var workspace = new Grid { ColumnSpacing = 20 };
        workspace.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(3, GridUnitType.Star) });
        workspace.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(2, GridUnitType.Star) });
        Add(workspace, _rows, 0, 0);
        var right = new StackPanel { Spacing = 10 };
        right.Children.Add(_parameterHeading);
        right.Children.Add(_detail);
        right.Children.Add(_options);
        right.Children.Add(_preview); right.Children.Add(_revert); right.Children.Add(_clear);
        right.Children.Add(_auditHeading);
        right.Children.Add(_audit);
        Add(workspace, new ScrollViewer { Content = right, VerticalScrollBarVisibility = ScrollBarVisibility.Auto }, 0, 1);
        Add(root, workspace, 2);
        Add(root, _status, 3);
        Content = shell;
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1200, 800));

        _navigation.SelectionChanged += (_, _) =>
        {
            if (_closed) return;
            if (Busy || (_navigation.SelectedItem as ListViewItem)?.Tag is not Section section)
            {
                // Retain a valid selection even if a selection is cleared programmatically.
                var current = _navigation.Items.OfType<ListViewItem>().Single(i => (Section)i.Tag == _section);
                if (_navigation.SelectedItem != current) _navigation.SelectedItem = current;
                return;
            }
            _section = section;
            _moduleSlots = null;
            _moduleFailed = false;
            if (section == Section.Connection) RefreshDriver();
            ShowSection();
            _workspaceScroll.ChangeView(null, 0, null, true);
        };
        _load.Click += async (_, _) => await LoadAsync();
        _cancel.Click += (_, _) => _operation?.Cancel();
        _reset.Click += (_, _) => ResetProfile();
        _search.TextChanged += (_, _) => RefreshRows(Selected?.Offset);
        _filter.SelectionChanged += (_, _) => RefreshRows(Selected?.Offset);
        _rows.SelectionChanged += (_, _) => { if (!_rebuilding) RefreshDetail(); };
        _options.SelectionChanged += (_, _) => UpdateControls();
        _preview.Click += async (_, _) =>
        {
            if (Busy || Selected is not { Locked: false } row ||
                (_options.SelectedItem as ComboBoxItem)?.Tag is not CemOption option || !option.Selectable)
                return;
            var edits = new Dictionary<int, string>(_edits);
            if (option.Code == row.BaselineCode) edits.Remove(row.Offset);
            else edits[row.Offset] = option.Code;
            await RunAsync(edits, row.Offset);
        };
        _revert.Click += async (_, _) =>
        {
            if (Busy || Selected is not { Changed: true } row) return;
            var edits = new Dictionary<int, string>(_edits);
            edits.Remove(row.Offset);
            await RunAsync(edits, row.Offset);
        };
        _clear.Click += async (_, _) => { if (!Busy && _edits.Count > 0) await RunAsync(new(), Selected?.Offset); };
        Closed += (_, _) => { _closed = true; StopMonitor(); _operation?.Cancel(); };
        _language.SelectionChanged += (_, _) =>
        {
            if (_closed || _language.SelectedIndex < 0) return;
            _russian = _language.SelectedIndex == 1;
            _languageSaveFailed = !_ephemeral && !(_languageSettings?.TrySave(
                _russian ? UiLanguage.Russian : UiLanguage.English) ?? false);
            ApplyLanguage();
        };
        ApplyLanguage();
    }

    // Localize application chrome only; preserve source catalog and policy text.
    // No transport request, model reset or change to the draft is performed here.
    private void ApplyLanguage()
    {
        int? offset = Selected?.Offset;
        string? optionCode = ((_options.SelectedItem as ComboBoxItem)?.Tag as CemOption)?.Code;
        Title = "Virtual Car";
        foreach (var item in _navigation.Items.OfType<ListViewItem>())
            item.Content = SectionLabel((Section)item.Tag);
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(_navigation, T("Workspace navigation", "Навигация"));
        ShowSection();
        _python.Header = T("Python.exe (absolute path)", "Python.exe (абсолютный путь)");
        _script.Header = T("vc071_view.py (absolute path)", "vc071_view.py (абсолютный путь)");
        _data.Header = T("Local CEM529 directory (outside Git)", "Локальный каталог CEM529 (вне Git)");
        _search.PlaceholderText = T("Search by name or offset", "Поиск по названию или смещению");
        _load.Content = T("Load profile", "Загрузить профиль");
        _cancel.Content = T("Cancel", "Отмена");
        _reset.Content = T("Close profile", "Закрыть профиль");
        _preview.Content = T("Preview selection", "Проверить вариант");
        _revert.Content = T("Revert to baseline", "Вернуть исходное");
        _clear.Content = T("Reset all changes", "Сбросить все изменения");
        _parameterHeading.Text = T("Parameter", "Параметр");
        _auditHeading.Text = T("Configuration audit", "Аудит конфигурации");
        string[] labels = [T("All", "Все"), T("Changed", "Изменённые"),
            T("Locked", "Защищённые"), T("Editable", "Доступные")];
        for (int i = 0; i < labels.Length; i++)
            ((ComboBoxItem)_filter.Items[i]).Content = labels[i];
        _languageNotice.Text = _languageSaveFailed
            ? T("Language could not be saved.", "Не удалось сохранить язык.") : "";
        _languageNotice.Visibility = _languageSaveFailed ? Visibility.Visible : Visibility.Collapsed;
        _status.Text = T(_statusEn, _statusRu);
        RefreshRows(offset);
        if (optionCode is not null)
            foreach (var item in _options.Items.OfType<ComboBoxItem>())
                if ((item.Tag as CemOption)?.Code == optionCode)
                {
                    _options.SelectedItem = item;
                    break;
                }
    }

    private string SectionLabel(Section section) => section switch
    {
        Section.Vehicle => T("Virtual vehicle", "Виртуальный автомобиль"),
        Section.Configuration => T("CEM529 Configuration", "Конфигурация CEM529"),
        Section.Modules => T("ECU modules", "Электронные блоки"),
        Section.Diagnostics => T("Diagnostics", "Диагностика"),
        Section.Connection => T("Connection", "Подключение"),
        _ => throw new ArgumentOutOfRangeException(nameof(section))
    };

    private void ShowSection()
    {
        bool configuration = _section == Section.Configuration;
        _heading.Text = SectionLabel(_section);
        _subtitle.Text = configuration
            ? T("Lab preview only. Export and ECU writes are unavailable.",
                "Лабораторный предварительный просмотр. Экспорт и запись в ECU недоступны.")
            : _section == Section.Connection
                ? T("J2534 Lab Adapter — registration only.", "J2534 Lab Adapter — только регистрация.")
                : _section == Section.Vehicle
                    ? T("Native ECM scenario preview — not live telemetry.", "Предпросмотр сценария ECM — не текущая телеметрия.")
                    : _section == Section.Modules
                        ? T("Configured ECU inventory — not discovery.", "Настроенные ECU — не результат обнаружения.")
                        : T("CAN monitor — application log, not wire capture.", "CAN Monitor — журнал приложения, не захват с шины.");
        if (_section != Section.Diagnostics) StopMonitor();
        _monitorPanel.Visibility = _section == Section.Diagnostics ? Visibility.Visible : Visibility.Collapsed;
        RenderMonitor(); 
        _modulePanel.Visibility = _section == Section.Modules ? Visibility.Visible : Visibility.Collapsed;
        RenderModules();
        _vehiclePanel.Visibility = _section == Section.Vehicle ? Visibility.Visible : Visibility.Collapsed;
        RenderVehicle();
        _driverPanel.Visibility = _section == Section.Connection ? Visibility.Visible : Visibility.Collapsed;
        RenderDriver();
        _editor.Visibility = configuration ? Visibility.Visible : Visibility.Collapsed;
        _workspaceScroll.Visibility = configuration ? Visibility.Collapsed : Visibility.Visible;
        _placeholderHeading.Text = SectionLabel(_section);
        _placeholderText.Text = _section switch
        {
            Section.Vehicle => T("Inspect the profile beside the registered J2534 DLL. Applying a scenario requires closing all diagnostic clients and editors. Settings take effect on a subsequent PassThruOpen.",
                "Проверьте профиль рядом с зарегистрированной DLL J2534. Перед применением закройте диагностические программы и редакторы. Настройки вступают в силу при следующем PassThruOpen."),
            Section.Modules => T("Read the profile beside the registered J2534 Lab Adapter. No diagnostic requests are sent.",
                "Чтение профиля рядом с зарегистрированным J2534 Lab Adapter. Диагностические запросы не отправляются."),
            Section.Diagnostics => T("Read existing TX and delivered RX records from the selected local J2534 log. No connection is opened and no messages are sent.",
                "Чтение существующих TX и доставленных RX из локального журнала J2534. Подключение не открывается, запросы не отправляются."),
            Section.Connection => T("J2534 04.04 / x86. Use a reviewed local VirtualCarJ2534.dll in a stable folder. Close VIDA and other diagnostic clients before changing registration. No DLL files are copied or deleted.",
                "J2534 04.04 / x86. Выберите проверенную локальную VirtualCarJ2534.dll в постоянной папке. Закройте VIDA и другие диагностические программы. Файлы DLL не копируются и не удаляются."),
            _ => ""
        };
    }

    private void StartMonitor()
    {
        if (_ephemeral || Busy || _closed || _section != Section.Diagnostics || _monitorRunning) return;
        _monitorRunning = true;
        _monitorTimer ??= DispatcherQueue.CreateTimer();
        _monitorTimer.Interval = TimeSpan.FromSeconds(1);
        _monitorTimer.Tick -= MonitorTick;
        _monitorTimer.Tick += MonitorTick;
        ReadMonitor();
        if (_monitorRunning) _monitorTimer.Start();
    }

    private void MonitorTick(Microsoft.UI.Dispatching.DispatcherQueueTimer sender, object args)
    {
        if (_closed || Busy || _section != Section.Diagnostics) { StopMonitor(); RenderMonitor(); return; }
        ReadMonitor();
    }

    private void StopMonitor()
    {
        _monitorRunning = false;
        _monitorTimer?.Stop();
    }

    private void ReadMonitor()
    {
        if (_ephemeral || Busy || _closed || _section != Section.Diagnostics) return;
        _monitorSnapshot = null;
        _monitorFailed = false;
        try { _monitorSnapshot = NativeCanTrace.ReadFile(_monitorPath.Text.Trim()); }
        catch (Exception) { _monitorFailed = true; StopMonitor(); }
        RenderMonitor();
    }

    private void RenderMonitor()
    {
        _monitorPath.Header = T("Local J2534 log (absolute path)", "Локальный журнал J2534 (абсолютный путь)");
        _monitorStart.Content = T("Start monitor", "Запустить монитор");
        _monitorStop.Content = T("Stop monitor", "Остановить монитор");
        _monitorRefresh.Content = T("Refresh snapshot", "Обновить снимок");
        _monitorDirection.Header = T("Direction", "Направление");
        if (_monitorDirection.Items.Count > 0 && _monitorDirection.Items[0] is ComboBoxItem all)
            all.Content = T("All", "Все");
        _monitorView.Header = T("View", "Представление");
        if (_monitorView.Items.Count == 2)
        {
            ((ComboBoxItem)_monitorView.Items[0]).Content = "CAN Monitor";
            ((ComboBoxItem)_monitorView.Items[1]).Content = T("Diagnostic journal", "Журнал диагностики");
        }
        bool journal = _monitorView.SelectedIndex == 1;
        _journalSummary.Visibility = journal ? Visibility.Visible : Visibility.Collapsed;
        _journalSummary.Text = journal ? T("No log records available.", "Нет записей журнала.") : "";
        _monitorFilter.Header = journal
            ? T("Filter CAN ID / payload / PID / process / SID / DID / NRC", "Фильтр CAN ID / данных / PID / процесса / SID / DID / NRC")
            : T("Filter CAN ID / payload / PID / process", "Фильтр CAN ID / данных / PID / процесса");
        bool enabled = !_ephemeral && !Busy && !_closed;
        _monitorPath.IsEnabled = enabled && !_monitorRunning;
        _monitorStart.IsEnabled = _monitorRefresh.IsEnabled = enabled && !_monitorRunning;
        _monitorStop.IsEnabled = _monitorRunning;
        _monitorRows.Items.Clear();
        if (_monitorSnapshot is null)
        {
            _monitorStatus.Text = _monitorFailed
                ? T("Log unavailable. Monitoring stopped.", "Журнал недоступен. Монитор остановлен.")
                : T("No log read.", "Журнал не прочитан.");
            return;
        }
        string filter = _monitorFilter.Text.Trim();
        int shown = 0;
        var visibleEntries = new List<DiagnosticEntry>();
        foreach (var row in _monitorSnapshot.Rows)
        {
            if (_monitorDirection.SelectedIndex == 1 && row.Direction != NativeTraceDirection.Tx ||
                _monitorDirection.SelectedIndex == 2 && row.Direction != NativeTraceDirection.Rx) continue;
            string can = row.CanId?.ToString("X") ?? "—";
            string protocol = row.Protocol switch { 5 => "CAN", 6 => "ISO15765", _ => "—" };
            string pid = row.Pid.ToString("X8");
            DiagnosticEntry? entry = journal ? NativeDiagnosticJournal.Classify(row) : null;
            string detail = entry is null ? "" : DiagnosticLabel(entry);
            if (filter.Length > 0 && !string.Join(" ", can, row.DataHex, pid, row.Host, detail)
                    .Contains(filter, StringComparison.OrdinalIgnoreCase)) continue;
            if (entry is not null) visibleEntries.Add(entry);
            _monitorRows.Items.Add(new TextBlock
            {
                TextWrapping = TextWrapping.Wrap,
                Text = $"{row.Direction.ToString().ToUpperInvariant()} · {can} · {protocol} · {row.Baud?.ToString() ?? "—"} · PID {pid} {row.Host}\n" +
                    $"CH {row.Channel?.ToString() ?? "—"} · t32 {row.TimeUs?.ToString() ?? "—"} µs · {row.DataHex}" +
                    (row.PossibleTruncation ? T(" [possibly truncated]", " [возможно усечено]") : "") +
                    (journal ? "\n" + detail : "")
            });
            shown++;
        }
        if (journal)
        {
            var counts = NativeDiagnosticJournal.Summarize(visibleEntries);
            _journalSummary.Text = T("Visible records: ", "Видимые записи: ") +
                T("Requests ", "Запросы ") + counts.Requests + " · " +
                T("Positive ", "Положительные ") + counts.Positive + " · " +
                T("Negative ", "Отрицательные ") + counts.Negative + " · " +
                T("Indications ", "Индикации ") + counts.Indications + " · " +
                T("Unclassified ", "Без классификации ") + counts.Unclassified + "\n" +
                T("No request/response matching or ECU acceptance inferred.", "Сопоставление запросов и ответов и приёмка ECU не подтверждаются.");
        }
        _monitorStatus.Text = (_monitorRunning ? T("Monitoring log", "Мониторинг журнала") : T("Snapshot", "Снимок")) +
            $" · {shown}/{_monitorSnapshot.Rows.Count} · " +
            T("Latest 500 records max; not a complete capture.", "До 500 последних записей; не полный захват.") +
            (_monitorSnapshot.TailOnly ? T(" Tail only.", " Только конец файла.") : "");
    }

    private string DiagnosticLabel(DiagnosticEntry entry)
    {
        string label = entry.Kind switch
        {
            DiagnosticKind.Request => T("Request", "Запрос"),
            DiagnosticKind.Positive => T("Positive response shape", "Форма положительного ответа"),
            DiagnosticKind.Negative => T("Negative response shape", "Форма отрицательного ответа"),
            DiagnosticKind.Indication => T("Start of message", "Начало сообщения"),
            _ => T("Unclassified", "Без классификации")
        };
        if (entry.Service is byte sid) label += $" · SID {sid:X2}";
        if (entry.Did is ushort did) label += $" · DID {did:X4}";
        if (entry.Nrc is byte nrc)
        {
            label += $" · NRC {nrc:X2}";
            if (nrc == 0x78) label += T(" (response pending)", " (ответ ожидается)");
        }
        return label;
    }

    private void InspectModules()
    {
        if (_ephemeral || Busy || _closed || _section != Section.Modules) return;
        _moduleSlots = null;
        _moduleFailed = false;
        try
        {
            var info = DriverRegistration.Read();
            if (info.Status != DriverRegistration.State.Registered || info.Library is null || !File.Exists(info.Library))
                throw new InvalidOperationException("No recognized adapter.");
            string path = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(info.Library))!, "virtualcar.ini");
            if (!IsRegisteredProfile(path)) throw new InvalidOperationException("Registration changed.");
            var bytes = NativeEcmScenarioApply.ReadProfile(path);
            var slots = NativeEcuInventory.Inspect(bytes);
            if (!IsRegisteredProfile(path)) throw new InvalidOperationException("Registration changed.");
            _moduleSlots = slots;
        }
        catch (Exception) { _moduleFailed = true; }
        RenderModules();
    }

    private void RenderModules()
    {
        _moduleRefresh.Content = T("Read configured ECUs", "Прочитать настроенные ECU");
        _moduleRefresh.IsEnabled = !_ephemeral && !Busy && !_closed;
        _moduleList.Items.Clear();
        if (_moduleSlots is null)
        {
            _moduleStatus.Text = _moduleFailed
                ? T("Profile unavailable or ambiguous.", "Профиль недоступен или неоднозначен.")
                : T("No inventory read. Discovery not performed.", "Список не прочитан. Обнаружение не выполнялось.");
            return;
        }
        _moduleStatus.Text = T("Profile snapshot: ", "Снимок профиля: ") + _moduleSlots.Count +
            T(" slots. Discovery not performed. Refresh after external changes.",
              " слотов. Обнаружение не выполнялось. Обновите после внешних изменений.");
        foreach (var slot in _moduleSlots)
        {
            string address(uint? id) => id.HasValue ? id.Value.ToString("X") : "—";
            string state = slot.State switch
            {
                EcuRouteState.Configured => T("Configured", "Настроен"),
                EcuRouteState.DefaultsUsed => T("Defaults or missing fields", "Значения по умолчанию или отсутствующие поля"),
                EcuRouteState.DuplicateRequest => T("Duplicate request ID", "Дублирующийся ID запроса"),
                EcuRouteState.FunctionalRequest => T("Functional request ID", "Функциональный ID запроса"),
                _ => T("Invalid or unsupported route", "Некорректный или неподдерживаемый маршрут")
            };
            string rate = slot.ExpectedBaud switch
            {
                null => "—",
                0 => T("Unrestricted", "Без ограничения"),
                _ => slot.ExpectedBaud.Value.ToString()
            };
            var row = new TextBlock
            {
                TextWrapping = TextWrapping.Wrap,
                Text = $"ECU{slot.Index} · {state}\nTX {address(slot.RequestId)} / RX {address(slot.ResponseId)} · {rate}\n" +
                    T("Configured part: ", "Настроенный номер: ") + (slot.PartNumber ?? "—") + " · " +
                    T("Software: ", "ПО: ") + (slot.Software ?? "—")
            };
            _moduleList.Items.Add(row);
        }
    }

    private string ScenarioLabel(EcmScenario scenario) => scenario switch
    {
        EcmScenario.Stationary => T("Stationary / 0 rpm", "Стоянка / 0 об/мин"),
        EcmScenario.Cranking => T("Cranking / 200 rpm", "Прокрутка / 200 об/мин"),
        EcmScenario.ColdIdle => T("Cold idle / 1100 rpm", "Холодный двигатель / 1100 об/мин"),
        EcmScenario.Warming => T("Warming / 900 rpm", "Прогрев / 900 об/мин"),
        EcmScenario.WarmIdle => T("Warm idle / 700 rpm", "Прогретый двигатель / 700 об/мин"),
        EcmScenario.Dynamic => T("Dynamic warm-up / 180 s", "Динамический прогрев / 180 с"),
        _ => throw new ArgumentOutOfRangeException(nameof(scenario))
    };

    private void InspectVehicle()
    {
        if (_closed || Busy || _ephemeral) return;
        _vehicleBytes = null;
        _inspectedPath = null;
        _vehicleFailed = false;
        VehicleResult("", "");
        try
        {
            string path = _vehicleProfile.Text.Trim();
            var input = NativeEcmScenarioApply.ReadProfile(path);
            var plan = NativeEcmScenarioPlan.Inspect(input);
            _vehicleBytes = input;
            _inspectedPath = Path.GetFullPath(path);
            _vehicleUpdating = true;
            _vehicleScenario.SelectedIndex = (int)plan.Selection;
            SyncIgnition();
        }
        catch (Exception) { _vehicleFailed = true; }
        finally { _vehicleUpdating = false; RenderVehicle(); }
    }

    private void RenderVehicle()
    {
        _vehicleProfile.Header = T("Local virtualcar.ini (absolute path)", "Локальный virtualcar.ini (абсолютный путь)");
        _vehicleInspect.Content = T("Inspect profile", "Проверить профиль");
        _vehicleScenario.Header = T("Proposed ECM scenario", "Предлагаемый сценарий ECM");
        _vehiclePatch.Header = T("Merge these keys into existing sections (do not append duplicates)",
            "Замените ключи в существующих секциях (не добавляйте дубликаты)");
        foreach (var item in _vehicleScenario.Items.OfType<ComboBoxItem>())
            item.Content = ScenarioLabel((EcmScenario)item.Tag);
        _vehicleInspect.IsEnabled = !_ephemeral && !Busy && !_closed;
        _vehicleProfile.IsEnabled = !_ephemeral && !Busy && !_closed;
        _vehicleScenario.IsEnabled = _vehicleBytes is not null && !Busy;
        _vehicleApply.Content = T("Apply scenario", "Применить сценарий");
        _vehicleApply.IsEnabled = false;
        _vehicleBackup.Header = T("Local scenario backup (absolute path)", "Локальная копия сценария (абсолютный путь)");
        _vehicleRestore.Content = T("Restore backup", "Восстановить копию");
        _vehicleBackup.IsEnabled = !_ephemeral && !Busy && !_closed && _inspectedPath is not null;
        _vehicleRestore.IsEnabled = _vehicleBackup.IsEnabled && _vehicleBytes is not null &&
            !string.IsNullOrWhiteSpace(_vehicleBackup.Text);
        _vehicleResult.Text = T(_vehicleResultEn, _vehicleResultRu);
        _vehiclePatch.Text = "";
        RenderIgnition();
        if (_vehicleBytes is null)
        {
            _vehicleInfo.Text = _vehicleFailed ? T("Profile unavailable or ambiguous.", "Профиль недоступен или неоднозначен.") :
                T("No inspected profile. No live state available.", "Профиль не проверен. Текущее состояние неизвестно.");
            return;
        }
        var current = NativeEcmScenarioPlan.Inspect(_vehicleBytes);
        if ((_vehicleScenario.SelectedItem as ComboBoxItem)?.Tag is not EcmScenario selected) return;
        var plan = NativeEcmScenarioPlan.Inspect(_vehicleBytes, selected);
        _vehicleInfo.Text = T("Configured selection: ", "Настроенный сценарий: ") + ScenarioLabel(current.Selection) + "\n" +
            (plan.CanApply ? T("Required gates enabled; preview only.", "Требуемые флаги включены; только предпросмотр.") :
                T("Required gates missing. No changes proposed.", "Не включены требуемые флаги. Изменения не предлагаются."));
        if (plan.CanApply)
        {
            _vehiclePatch.Text = plan.IniPatch;
            _vehicleApply.IsEnabled = !_ephemeral && !Busy && !_closed && _inspectedPath is not null;
        }
    }

    private string IgnitionLabel(NativeIgnitionSelection choice) =>
        choice == NativeIgnitionSelection.PositionIICandidate
            ? T("Position II candidate (07)", "Кандидат положения II (07)")
            : T("Baseline (04)", "Исходное значение (04)");

    private void SyncIgnition()
    {
        if (_vehicleBytes is null) return;
        try { _ignition.SelectedIndex = (int)NativeIgnitionPlan.Inspect(_vehicleBytes).Configured; }
        catch (InvalidDataException) { _ignition.SelectedIndex = 0; }
    }

    private void RenderIgnition()
    {
        _ignition.Header = T("CEM A45F laboratory candidate", "Лабораторный кандидат CEM A45F");
        _ignitionApply.Content = T("Apply ignition candidate", "Применить кандидат зажигания");
        foreach (var item in _ignition.Items.OfType<ComboBoxItem>())
            item.Content = IgnitionLabel((NativeIgnitionSelection)item.Tag);
        _ignition.IsEnabled = _ignitionApply.IsEnabled = false;
        _ignitionInfo.Text = T("No inspected profile.", "Профиль не проверен.");
        if (_vehicleBytes is null) return;
        try
        {
            var state = NativeIgnitionPlan.Inspect(_vehicleBytes);
            _ignitionInfo.Text = T("Configured: ", "Настроено: ") + IgnitionLabel(state.Configured) + "\n" +
                (state.CanApply
                    ? T("Synthetic response on the next J2534 open; not a verified key position.",
                        "Синтетический ответ при следующем открытии J2534; положение ключа не подтверждено.")
                    : T("GGD CEM lab flag is disabled. No change permitted.",
                        "Флаг GGD CEM отключён. Изменение недоступно."));
            _ignition.IsEnabled = _ignitionApply.IsEnabled =
                state.CanApply && !_ephemeral && !_closed && !Busy && _inspectedPath is not null;
        }
        catch (InvalidDataException)
        {
            _ignitionInfo.Text = T("Ambiguous ignition configuration.", "Неоднозначная конфигурация зажигания.");
        }
    }

    private void VehicleResult(string en, string ru)
    {
        _vehicleResultEn = en;
        _vehicleResultRu = ru;
    }

    private static bool IsRegisteredProfile(string path)
    {
        var info = DriverRegistration.Read();
        if (info.Status != DriverRegistration.State.Registered || info.Library is null ||
            !File.Exists(info.Library)) return false;
        string expected = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(info.Library))!, "virtualcar.ini");
        return string.Equals(expected, path, StringComparison.OrdinalIgnoreCase);
    }

    private async Task ApplyVehicleAsync(bool ignition = false)
    {
        if (_ephemeral || Busy || _closed || _section != Section.Vehicle ||
            _vehicleBytes is null || _inspectedPath is null ||
            (_vehicleScenario.SelectedItem as ComboBoxItem)?.Tag is not EcmScenario selected) return;
        string path = _inspectedPath;
        string sha = NativeEcmScenarioApply.Digest(_vehicleBytes);
        var ignitionChoice = (_ignition.SelectedItem as ComboBoxItem)?.Tag is NativeIgnitionSelection choice
            ? choice : NativeIgnitionSelection.Baseline;
        if (ignition)
        {
            try { if (!NativeIgnitionPlan.Inspect(_vehicleBytes).CanApply) return; }
            catch (InvalidDataException) { return; }
        }
        else if (!NativeEcmScenarioPlan.Inspect(_vehicleBytes, selected).CanApply) return;
        _vehicleBusy = true;
        UpdateControls();
        RenderVehicle();
        try
        {
            if (!IsRegisteredProfile(path))
                throw new InvalidOperationException("Profile does not match current registration.");
            var dialog = new ContentDialog
            {
                XamlRoot = _vehiclePanel.XamlRoot,
                Title = ignition ? T("Apply ignition candidate?", "Применить кандидат зажигания?") : T("Apply ECM scenario?", "Применить сценарий ECM?"),
                Content = path + "\n" + (ignition ? IgnitionLabel(ignitionChoice) : ScenarioLabel(selected)) + "\nSHA256: " + sha + "\n\n" +
                    T("Confirm all diagnostic clients and profile editors are closed. A backup will be created if the file changes. Reopen the diagnostic connection manually afterward.",
                      "Подтвердите закрытие диагностических программ и редакторов. При изменении создаётся резервная копия. Затем вручную откройте диагностическое подключение."),
                PrimaryButtonText = T("Apply", "Применить"),
                CloseButtonText = T("Cancel", "Отмена"),
                DefaultButton = ContentDialogButton.Close
            };
            if (await dialog.ShowAsync() != ContentDialogResult.Primary || _closed) return;
            var result = await Task.Run(() =>
            {
                if (!IsRegisteredProfile(path))
                    throw new InvalidOperationException("Registration changed.");
                return ignition ? NativeIgnitionPlan.Apply(path, sha, ignitionChoice) : NativeEcmScenarioApply.Apply(path, sha, selected);
            });
            if (_closed) return;
            _vehicleBytes = NativeEcmScenarioApply.ReadProfile(path);
            if (NativeEcmScenarioApply.Digest(_vehicleBytes) != result.Sha256)
                throw new IOException("Profile changed after apply.");
            if (result.BackupPath is not null) _vehicleBackup.Text = result.BackupPath;
            VehicleResult(result.Changed
                ? "Saved. Reopen J2534 manually. Backup: " + result.BackupPath
                : "No changes needed.",
                result.Changed
                ? "Сохранено. Откройте J2534 заново вручную. Копия: " + result.BackupPath
                : "Изменения не требуются.");
        }
        catch (Exception)
        {
            _vehicleBytes = null;
            _inspectedPath = null;
            _vehicleFailed = true;
            VehicleResult("Apply not confirmed. Check registration, profile and backups; inspect again.",
                "Применение не подтверждено. Проверьте регистрацию, профиль и копии; повторите проверку.");
        }
        finally
        {
            _vehicleBusy = false;
            if (!_closed) { UpdateControls(); RenderVehicle(); }
        }
    }

    private async Task RestoreVehicleAsync()
    {
        if (_ephemeral || Busy || _closed || _section != Section.Vehicle ||
            _vehicleBytes is null || _inspectedPath is null ||
            string.IsNullOrWhiteSpace(_vehicleBackup.Text)) return;
        string path = _inspectedPath;
        string backup = _vehicleBackup.Text.Trim();
        string sha = NativeEcmScenarioApply.Digest(_vehicleBytes);
        _vehicleBusy = true;
        UpdateControls();
        RenderVehicle();
        try
        {
            if (!IsRegisteredProfile(path))
                throw new InvalidOperationException("Profile does not match current registration.");
            var backupBytes = NativeEcmScenarioApply.ReadBackup(path, backup);
            string backupSha = NativeEcmScenarioApply.Digest(backupBytes);
            var backupPlan = NativeEcmScenarioPlan.Inspect(backupBytes);
            var dialog = new ContentDialog
            {
                XamlRoot = _vehiclePanel.XamlRoot,
                Title = T("Restore scenario backup?", "Восстановить копию сценария?"),
                Content = path + "\n" + T("Current SHA256: ", "Текущий SHA256: ") + sha +
                    "\n" + backup + "\n" + T("Backup SHA256: ", "SHA256 копии: ") + backupSha +
                    "\n" + ScenarioLabel(backupPlan.Selection) + "\n\n" +
                    T("Close all diagnostic clients and profile editors. Only scenario-related backups are accepted. The current file will be backed up if changed.",
                      "Закройте диагностические программы и редакторы. Допустимы только копии, относящиеся к сценарию. Текущий файл будет сохранён при изменении."),
                PrimaryButtonText = T("Restore", "Восстановить"),
                CloseButtonText = T("Cancel", "Отмена"),
                DefaultButton = ContentDialogButton.Close
            };
            if (await dialog.ShowAsync() != ContentDialogResult.Primary || _closed) return;
            var result = await Task.Run(() =>
            {
                if (!IsRegisteredProfile(path)) throw new InvalidOperationException("Registration changed.");
                return NativeEcmScenarioApply.Restore(path, backup, sha, backupSha);
            });
            if (_closed) return;
            _vehicleBytes = NativeEcmScenarioApply.ReadProfile(path);
            if (NativeEcmScenarioApply.Digest(_vehicleBytes) != result.Sha256)
                throw new IOException("Profile changed after restore.");
            _vehicleUpdating = true;
            try { _vehicleScenario.SelectedIndex = (int)NativeEcmScenarioPlan.Inspect(_vehicleBytes).Selection; SyncIgnition(); }
            finally { _vehicleUpdating = false; }
            if (result.BackupPath is not null) _vehicleBackup.Text = result.BackupPath;
            VehicleResult(result.Changed
                ? "Restored. Reopen J2534 manually. Recovery copy: " + result.BackupPath : "No changes needed.",
                result.Changed
                ? "Восстановлено. Откройте J2534 заново вручную. Копия для отмены: " + result.BackupPath : "Изменения не требуются.");
        }
        catch (Exception)
        {
            _vehicleBytes = null;
            _inspectedPath = null;
            _vehicleFailed = true;
            VehicleResult("Restore not confirmed. Review the profile and backups; inspect again.",
                "Восстановление не подтверждено. Проверьте профиль и копии; повторите проверку.");
        }
        finally
        {
            _vehicleBusy = false;
            if (!_closed) { UpdateControls(); RenderVehicle(); }
        }
    }

    private string DriverToolPath => Path.Combine(AppContext.BaseDirectory, "driver-tools", "VirtualCar.DriverTool.exe");

    private void RefreshDriver()
    {
        if (_ephemeral || _driverBusy || _closed) return;
        _driverInfo = DriverRegistration.Read();
        RenderDriver();
    }

    private void RenderDriver()
    {
        _driverPath.Header = T("Reviewed x86 DLL (absolute path)", "Проверенная x86 DLL (абсолютный путь)");
        _driverRefresh.Content = T("Refresh", "Обновить");
        _driverInstall.Content = T("Install driver", "Установить драйвер");
        _driverRemove.Content = T("Remove driver", "Удалить драйвер");
        _driverStatus.Text = _driverInfo.Status switch
        {
            DriverRegistration.State.Absent => T("Not registered", "Не зарегистрирован"),
            DriverRegistration.State.Registered => T("Registered (registry only)", "Зарегистрирован (только реестр)") + "\n" + _driverInfo.Library,
            DriverRegistration.State.LegacyRegistered => T("Previous registration found. Remove it before installing.", "Обнаружена прежняя регистрация. Удалите её перед установкой.") + "\n" + _driverInfo.Library,
            DriverRegistration.State.Conflict => T("Conflicting registration — manual review required.", "Конфликт регистрации — требуется ручная проверка."),
            _ => T("Registry unavailable", "Реестр недоступен")
        };
        _driverResult.Text = T(_driverResultEn, _driverResultRu);
        bool enabled = !_ephemeral && !Busy && !_closed && File.Exists(DriverToolPath);
        _driverPath.IsEnabled = enabled && _driverInfo.Status == DriverRegistration.State.Absent;
        _driverRefresh.IsEnabled = !_ephemeral && !Busy && !_closed;
        _driverInstall.IsEnabled = enabled && _driverInfo.Status == DriverRegistration.State.Absent;
        _driverRemove.IsEnabled = enabled && (_driverInfo.Status is DriverRegistration.State.Registered or DriverRegistration.State.LegacyRegistered);
        if (_ephemeral)
            _driverResult.Text = T("Driver changes disabled in smoke mode.", "Изменения драйвера отключены в тестовом режиме.");
        else if (!File.Exists(DriverToolPath))
            _driverResult.Text = T("Driver tool not published.", "Утилита регистрации не собрана.");
    }

    private void DriverResult(string en, string ru)
    {
        _driverResultEn = en;
        _driverResultRu = ru;
    }

    private async Task ChangeDriverAsync(bool install)
    {
        if (_ephemeral || Busy || _closed || _section != Section.Connection || !File.Exists(DriverToolPath)) return;
        RefreshDriver();
        if (install ? _driverInfo.Status != DriverRegistration.State.Absent :
            _driverInfo.Status is not (DriverRegistration.State.Registered or DriverRegistration.State.LegacyRegistered)) return;
        string path = install ? _driverPath.Text.Trim() : _driverInfo.Library!;
        _driverBusy = true;
        UpdateControls();
        RenderDriver();
        try
        {
            string? hash = install ? await Task.Run(() => DriverRegistration.Fingerprint(path)) : null;
            if (_closed) return;
            var dialog = new ContentDialog
            {
                XamlRoot = _driverPanel.XamlRoot,
                Title = install ? T("Install J2534 Lab Adapter?", "Установить J2534 Lab Adapter?") :
                    T("Remove J2534 registration?", "Удалить регистрацию J2534?"),
                Content = path + (hash is null ? "" : "\nSHA256: " + hash) + "\n\n" +
                    T("Confirm that diagnostic clients are closed. Administrator approval is required.",
                      "Подтвердите, что диагностические программы закрыты. Требуются права администратора."),
                PrimaryButtonText = install ? T("Install", "Установить") : T("Remove", "Удалить"),
                CloseButtonText = T("Cancel", "Отмена"),
                DefaultButton = ContentDialogButton.Close
            };
            if (await dialog.ShowAsync() != ContentDialogResult.Primary || _closed) return;
            var start = new ProcessStartInfo
            {
                FileName = DriverToolPath,
                WorkingDirectory = Path.GetDirectoryName(DriverToolPath)!,
                UseShellExecute = true,
                Verb = "runas"
            };
            start.ArgumentList.Add(install ? "install" : "remove");
            start.ArgumentList.Add(path);
            if (hash is not null) start.ArgumentList.Add(hash);
            using var process = Process.Start(start) ?? throw new InvalidOperationException();
            await process.WaitForExitAsync();
            var after = DriverRegistration.Read();
            bool verified = install
                ? after.Status == DriverRegistration.State.Registered &&
                  string.Equals(after.Library, Path.GetFullPath(path), StringComparison.OrdinalIgnoreCase)
                : after.Status == DriverRegistration.State.Absent;
            if (process.ExitCode == 0 && verified)
                DriverResult("Registration updated.", "Регистрация обновлена.");
            else
                DriverResult("Registration not confirmed. Review the status.", "Регистрация не подтверждена. Проверьте состояние.");
        }
        catch (System.ComponentModel.Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            DriverResult("Administrator approval cancelled.", "Запрос прав администратора отменён.");
        }
        catch (Exception)
        {
            DriverResult("Operation rejected or failed. Check the DLL and registration.", "Операция отклонена или не выполнена. Проверьте DLL и регистрацию.");
        }
        finally
        {
            _driverBusy = false;
            if (!_closed)
            {
                RefreshDriver();
                UpdateControls();
            }
        }
    }

    private void SetStatus(string en, string ru)
    {
        _statusEn = en;
        _statusRu = ru;
        _status.Text = T(en, ru);
    }

    private static void AutomationId(DependencyObject element, string id) =>
        Microsoft.UI.Xaml.Automation.AutomationProperties.SetAutomationId(element, id);

    private static void Add(Grid grid, UIElement child, int row, int column = 0)
    {
        Grid.SetRow(child, row); Grid.SetColumn(child, column); grid.Children.Add(child);
    }

    private async Task LoadAsync()
    {
        if (_ephemeral || _closed || Busy || _model is not null) return;
        try
        {
            var transport = new CemPreviewProcessTransport(_python.Text.Trim(), _script.Text.Trim(), _data.Text.Trim());
            _model = new CemPreviewViewModel(new CemPreviewClient(transport));
            await RunAsync(new(), null);
        }
        catch (Exception)
        {
            if (!_closed)
            {
                ResetProfile();
                SetStatus("Could not open the profile. Check the local paths.", "Не удалось открыть профиль. Проверьте локальные пути.");
            }
        }
    }

    private async Task RunAsync(Dictionary<int, string> candidate, int? selectedOffset)
    {
        if (Busy || _model is null || _closed) return;
        var model = _model;
        using var cancel = new CancellationTokenSource();
        _operation = cancel;
        try
        {
            SetStatus("Checking configuration…", "Проверка конфигурации…");
            RefreshRows(null);
            await model.RefreshAsync(candidate.Select(p => new CemEdit(p.Key, p.Value)), cancel.Token);
            if (_closed) return;
            var result = model.Snapshot ?? throw new InvalidDataException();
            _edits = new Dictionary<int, string>(candidate);
            switch (result.Status)
            {
                case "pass":
                    SetStatus("Preview checks passed. VIDA acceptance is not established.",
                        "Предварительная проверка пройдена. Не является приёмкой VIDA.");
                    break;
                case "review":
                    SetStatus("Warnings or topology require review.", "Требуется проверка предупреждений или топологии.");
                    break;
                default:
                    SetStatus("Selection blocked by dependency policy.", "Вариант заблокирован политикой зависимостей.");
                    break;
            }
        }
        catch (Exception ex)
        {
            _model = null;
            _edits.Clear();
            if (!_closed)
            {
                if (ex is OperationCanceledException)
                    SetStatus("Operation cancelled. Reload the baseline profile.", "Операция отменена. Загрузите исходный профиль заново.");
                else
                    SetStatus("Preview failed. Reload the baseline profile.", "Проверка не выполнена. Загрузите исходный профиль заново.");
            }
        }
        finally
        {
            _operation = null;
            if (!_closed) RefreshRows(selectedOffset);
        }
    }

    private void ResetProfile()
    {
        if (Busy) return;
        _model = null;
        _edits.Clear();
        SetStatus("Profile closed.", "Профиль закрыт.");
        RefreshRows(null);
    }

    private void RefreshRows(int? selectedOffset)
    {
        if (_closed) return;
        _rebuilding = true;
        try
        {
            _rows.Items.Clear();
            var snapshot = Busy ? null : Snapshot;
            _counts.Text = snapshot is null ? T("No data", "Нет данных") :
                $"{T("Parameters", "Параметры")}: {snapshot.Rows.Count} · {T("locked", "защищено")}: {snapshot.Rows.Count(r => r.Locked)} · {T("changed", "изменено")}: {snapshot.Rows.Count(r => r.Changed)}";
            if (snapshot is not null)
            {
                string query = _search.Text.Trim();
                foreach (var row in snapshot.Rows)
                {
                    if (_filter.SelectedIndex == 1 && !row.Changed ||
                        _filter.SelectedIndex == 2 && !row.Locked ||
                        _filter.SelectedIndex == 3 && (row.Locked || !row.Options.Any(o => o.Selectable && o.Code != row.BaselineCode)))
                        continue;
                    if (query.Length > 0 && !row.Name.Contains(query, StringComparison.OrdinalIgnoreCase) &&
                        !row.Offset.ToString().Contains(query, StringComparison.Ordinal)) continue;
                    string state = row.Locked ? T("[Locked]", "[Защищено]") : row.Changed ? T("[Changed]", "[Изменено]") : "";
                    var item = new ListViewItem
                    {
                        Tag = row,
                        Content = new TextBlock { Text = $"{row.Offset:D3}  {row.Name}  {state}\n{row.SelectedCode}  {row.SelectedText}", TextWrapping = TextWrapping.Wrap }
                    };
                    _rows.Items.Add(item);
                    if (selectedOffset == row.Offset) _rows.SelectedItem = item;
                }
                string auditStatus = snapshot.Status switch
                {
                    "pass" => T("Passed", "Пройдено"),
                    "review" => T("Review required", "Требуется проверка"),
                    "blocked" => T("Blocked", "Заблокировано"),
                    _ => snapshot.Status
                };
                _audit.Text = $"{T("Status", "Статус")}: {auditStatus}\n{T("Topology", "Топология")}: {(snapshot.TopologyReviewRequired ? T("review required", "требует проверки") : T("no new review flags", "без новых замечаний"))}\n" +
                    $"{T("Errors", "Ошибки")}: {snapshot.Errors.Count}\n{string.Join("\n", snapshot.Errors)}\n" +
                    $"{T("Warnings", "Предупреждения")}: {snapshot.Warnings.Count}\n{string.Join("\n", snapshot.Warnings)}\n" +
                    $"{T("Audit SHA256", "SHA256 аудита")}: {snapshot.AuditSha256}\n{T("OEM / VIDA / physical J2534: not verified.", "OEM / VIDA / физический J2534: не подтверждены.")}";
            }
            else _audit.Text = "";
        }
        finally { _rebuilding = false; }
        RefreshDetail();
    }

    private void RefreshDetail()
    {
        _options.Items.Clear();
        var row = Busy ? null : Selected;
        _detail.Text = row is null ? T("Select a parameter.", "Выберите параметр.") :
            $"{row.Name}\n{T("Offset", "Смещение")}: {row.Offset}\n{T("Baseline", "Исходное")}: {row.BaselineCode} — {row.BaselineText}\n" +
            $"{T("Selected", "Выбранное")}: {row.SelectedCode} — {row.SelectedText}\n" +
            (row.Locked ? T("Locked field.", "Защищённое поле.") : T("Selectable catalog options:", "Допустимые варианты из каталога:"));
        if (row is { Locked: false })
        {
            foreach (var option in row.Options.Where(o => o.Selectable && o.Code != row.SelectedCode))
                _options.Items.Add(new ComboBoxItem { Tag = option, Content = $"{option.Code} — {option.Text}" });
        }
        UpdateControls();
    }

    private void UpdateControls()
    {
        bool loaded = Snapshot is not null && !Busy;
        _python.IsEnabled = _script.IsEnabled = _data.IsEnabled = !_ephemeral && _model is null && !Busy;
        _load.IsEnabled = !_ephemeral && _model is null && !Busy;
        _cancel.IsEnabled = _operation is not null;
        _reset.IsEnabled = _model is not null && !Busy;
        _progress.IsActive = Busy;
        _navigation.IsEnabled = !Busy;
        _language.IsEnabled = !Busy;
        _search.IsEnabled = _filter.IsEnabled = _rows.IsEnabled = loaded;
        _options.IsEnabled = loaded && Selected is { Locked: false } && _options.Items.Count > 0;
        _preview.IsEnabled = _options.IsEnabled && (_options.SelectedItem as ComboBoxItem)?.Tag is CemOption { Selectable: true };
        _revert.IsEnabled = loaded && Selected is { Changed: true, Locked: false };
        _clear.IsEnabled = loaded && _edits.Count > 0;
    }
}
