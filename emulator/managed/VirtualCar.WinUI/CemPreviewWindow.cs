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
    private readonly TextBlock _counts = new() { Text = "No profile loaded", TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _detail = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _audit = new() { TextWrapping = TextWrapping.Wrap, IsTextSelectionEnabled = true };
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Button _load = new() { Content = "Load profile" };
    private readonly Button _cancel = new() { Content = "Cancel" };
    private readonly Button _reset = new() { Content = "Close profile" };
    private readonly Button _preview = new() { Content = "Preview selection" };
    private readonly Button _revert = new() { Content = "Revert to baseline" };
    private readonly Button _clear = new() { Content = "Reset all changes" };
    private readonly ComboBox _language = new() { MinWidth = 120 };
    private readonly TextBlock _heading = new() { FontSize = 28, TextWrapping = TextWrapping.Wrap };
    private readonly ListView _navigation = new() { SelectionMode = ListViewSelectionMode.Single, MinWidth = 180 };
    private readonly Grid _editor = new() { RowSpacing = 12 };
    private readonly StackPanel _placeholder = new() { Spacing = 12, Padding = new Thickness(12) };
    private readonly ScrollViewer _workspaceScroll = new() { VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
    private readonly TextBlock _placeholderHeading = new() { FontSize = 24, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _placeholderText = new() { TextWrapping = TextWrapping.Wrap };
    private readonly StackPanel _monitorPanel = new() { Spacing = 8 };
    private readonly StackPanel _monitorActions = new() { Orientation = Orientation.Horizontal, Spacing = 8 };
    private readonly StackPanel _acceptancePanel = new() { Spacing = 8, Visibility = Visibility.Collapsed };
    private readonly TextBox _acceptancePath = new();
    private readonly TextBox _acceptanceHead = new();
    private readonly TextBox _acceptanceDll = new();
    private readonly Button _acceptanceImport = new();
    private readonly Button _acceptanceClear = new();
    private readonly TextBox _acceptanceExportPath = new();
    private readonly Button _acceptanceExport = new();
    private readonly TextBlock _acceptanceExportStatus = new() { TextWrapping = TextWrapping.Wrap };
    private int _acceptanceExportResult;
    private readonly TextBlock _acceptanceStatus = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBox _acceptanceSummary = new() { IsReadOnly = true, AcceptsReturn = true, TextWrapping = TextWrapping.Wrap, MinHeight = 140, MaxHeight = 420 };
    private readonly SortedDictionary<string, AcceptanceReport> _acceptanceReports = new(StringComparer.Ordinal);
    private bool _acceptanceFailed;
    private bool AcceptanceView => _monitorView.SelectedIndex == 2;
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
    private readonly TextBox _moduleProfile = new();
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
    private readonly bool _previewOnly;
    private readonly bool _diagnosticsOnly;
    private readonly bool _registrationOnly;
    private bool CanManageRegistration => !_ephemeral || _registrationOnly;
    private bool CanReadDiagnostics => !_ephemeral || _diagnosticsOnly;
    private bool CanLoadProfile => !_ephemeral || _previewOnly;
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

    public CemPreviewWindow(bool ephemeral = false, bool previewOnly = false, bool diagnosticsOnly = false, bool registrationOnly = false)
    {
        _previewOnly = previewOnly;
        _diagnosticsOnly = diagnosticsOnly;
        _registrationOnly = registrationOnly;
        _ephemeral = ephemeral || previewOnly || diagnosticsOnly || registrationOnly;
        ephemeral = _ephemeral;
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
            var item = new ListViewItem
            {
                Tag = section,
                Content = new TextBlock { Text = SectionLabel(section), TextWrapping = TextWrapping.Wrap },
                HorizontalContentAlignment = HorizontalAlignment.Stretch
            };
            Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(item, SectionLabel(section));
            AutomationId(item, "VC077.Nav." + section);
            _navigation.Items.Add(item);
            if (section == _section) _navigation.SelectedItem = item;
        }
        Add(body, _navigation, 0);
        var page = new Grid();
        _placeholder.Children.Add(_placeholderHeading);
        _placeholder.Children.Add(_placeholderText);
        _monitorPanel.Children.Add(_monitorPath);
        _monitorActions.Children.Add(_monitorStart);
        _monitorActions.Children.Add(_monitorStop);
        _monitorActions.Children.Add(_monitorRefresh);
        _monitorPanel.Children.Add(_monitorActions);
        foreach (string label in new[] { "All", "TX", "RX" })
        {
            var item = new ComboBoxItem { Content = label };
            AutomationId(item, "VC088.Direction." + label);
            _monitorDirection.Items.Add(item);
        }
        _monitorDirection.SelectedIndex = 0;
        _monitorPanel.Children.Add(_monitorDirection);
        var canView = new ComboBoxItem { Content = "CAN Monitor" };
        var journalView = new ComboBoxItem { Content = "Diagnostic journal" };
        AutomationId(canView, "VC086.View.Can");
        AutomationId(journalView, "VC086.View.Journal");
        _monitorView.Items.Add(canView);
        _monitorView.Items.Add(journalView);
        var acceptanceView = new ComboBoxItem { Content = "Acceptance evidence" };
        AutomationId(acceptanceView, "VC091.View.Acceptance");
        _monitorView.Items.Add(acceptanceView);
        _monitorView.SelectedIndex = 0;
        _monitorPanel.Children.Add(_monitorView);
        _monitorPanel.Children.Add(_journalSummary);
        AutomationId(_monitorView, "VC085.Diagnostics.View");
        AutomationId(_journalSummary, "VC085.Diagnostics.Summary");
        _monitorView.SelectionChanged += (_, _) => { if (!_rebuilding) RenderMonitor(); };
        _monitorPanel.Children.Add(_monitorFilter);
        _monitorPanel.Children.Add(_monitorStatus);
        _monitorPanel.Children.Add(_monitorRows);
        foreach (var item in new FrameworkElement[] { _acceptanceHead, _acceptanceDll, _acceptancePath,
            _acceptanceImport, _acceptanceClear, _acceptanceStatus, _acceptanceSummary,
            _acceptanceExportPath, _acceptanceExport, _acceptanceExportStatus })
            _acceptancePanel.Children.Add(item);
        AutomationId(_acceptanceHead, "VC091.Acceptance.Head");
        AutomationId(_acceptanceDll, "VC091.Acceptance.DllSha");
        AutomationId(_acceptancePath, "VC091.Acceptance.Path");
        AutomationId(_acceptanceImport, "VC091.Acceptance.Import");
        AutomationId(_acceptanceClear, "VC091.Acceptance.Clear");
        AutomationId(_acceptanceStatus, "VC091.Acceptance.Status");
        AutomationId(_acceptanceSummary, "VC091.Acceptance.Summary");
        AutomationId(_acceptanceExportPath, "VC093.Acceptance.ExportPath");
        AutomationId(_acceptanceExport, "VC093.Acceptance.Export");
        AutomationId(_acceptanceExportStatus, "VC093.Acceptance.ExportStatus");
        _acceptanceExport.Click += (_, _) => ExportAcceptance();
        _acceptanceExportPath.TextChanged += (_, _) => { _acceptanceExportResult = 0; RenderAcceptance(); };
        _acceptanceImport.Click += (_, _) => ImportAcceptance();
        _acceptanceClear.Click += (_, _) => { _acceptanceReports.Clear(); _acceptanceFailed = false; _acceptanceExportResult = 0; RenderAcceptance(); };
        _acceptanceHead.TextChanged += (_, _) => RenderAcceptance();
        _acceptanceDll.TextChanged += (_, _) => RenderAcceptance();
        _acceptancePath.TextChanged += (_, _) => { _acceptanceFailed = false; RenderAcceptance(); };
        _monitorPanel.Children.Add(_acceptancePanel);
        _placeholder.Children.Add(_monitorPanel);
        if (!_ephemeral) _monitorPath.Text = Path.Combine(Path.GetTempPath(), NativeCanTrace.LegacyLogFile);
        AutomationId(_monitorPath, "VC088.Monitor.Path");
        AutomationId(_monitorDirection, "VC088.Monitor.Direction");
        AutomationId(_monitorFilter, "VC088.Monitor.Filter");
        AutomationId(_monitorStatus, "VC088.Monitor.Status");
        AutomationId(_monitorRows, "VC088.Monitor.Rows");
        AutomationId(_monitorStart, "VC084.Monitor.Start");
        AutomationId(_monitorStop, "VC084.Monitor.Stop");
        AutomationId(_monitorRefresh, "VC084.Monitor.Refresh");
        _monitorStart.Click += (_, _) => StartMonitor();
        _monitorStop.Click += (_, _) => { StopMonitor(); RenderMonitor(); };
        _monitorRefresh.Click += (_, _) => ReadMonitor();
        _monitorPath.TextChanged += (_, _) => { StopMonitor(); _monitorSnapshot = null; _monitorFailed = false; RenderMonitor(); };
        _monitorDirection.SelectionChanged += (_, _) => RenderMonitor();
        _monitorFilter.TextChanged += (_, _) => RenderMonitor();
        _modulePanel.Children.Add(_moduleProfile);
        _moduleProfile.Visibility = _diagnosticsOnly ? Visibility.Visible : Visibility.Collapsed;
        AutomationId(_moduleProfile, "VC088.Modules.Profile");
        AutomationId(_moduleList, "VC088.Modules.Rows");
        _moduleProfile.TextChanged += (_, _) => { _moduleSlots = null; _moduleFailed = false; RenderModules(); };
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
        AutomationId(_driverPath, "VC090B.Driver.Path");
        AutomationId(_driverResult, "VC090B.Driver.Result");
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
        AutomationId(_workspaceScroll, "VC089.WorkspaceScroll");
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
        var english = new ComboBoxItem { Content = "English" };
        var russian = new ComboBoxItem { Content = "Русский" };
        AutomationId(english, "VC075.Language.EN");
        AutomationId(russian, "VC075.Language.RU");
        _language.Items.Add(english);
        _language.Items.Add(russian);
        _language.SelectedIndex = _russian ? 1 : 0;
        AutomationId(_language, "VC075.Language");
        AutomationId(_heading, "VC075.Heading");
        AutomationId(_load, "VC075.Load");
        AutomationId(_python, "VC087.Python");
        AutomationId(_script, "VC087.Script");
        AutomationId(_data, "VC087.Data");
        AutomationId(_counts, "VC087.Counts");
        AutomationId(_rows, "VC087.Rows");
        AutomationId(_options, "VC087.Options");
        AutomationId(_detail, "VC087.Detail");
        AutomationId(_audit, "VC087.Audit");
        AutomationId(_status, "VC087.Status");
        AutomationId(_preview, "VC087.Preview");
        AutomationId(_revert, "VC087.Revert");
        AutomationId(_clear, "VC087.Clear");
        AutomationId(_reset, "VC087.Close");
        AutomationId(_cancel, "VC087.Cancel");
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
        foreach (string item in new[] { "All", "Changed", "Locked", "Editable" })
        {
            var filterItem = new ComboBoxItem { Content = item };
            AutomationId(filterItem, "VC087.Filter." + item);
            _filter.Items.Add(filterItem);
        }
        _filter.SelectedIndex = 0;
        filters.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        filters.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
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
        var detailScroll = new ScrollViewer { Content = right, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
        AutomationId(detailScroll, "VC089.DetailScroll");
        Add(workspace, detailScroll, 0, 1);
        Add(root, workspace, 2);
        Add(root, _status, 3);
        Content = shell;
        ResizeForDisplay();
        shell.SizeChanged += (_, _) =>
        {
            // Keep the search usable when localized count text grows at narrow widths.
            bool compact = shell.ActualWidth < 1000;
            Grid.SetRow(_counts, compact ? 1 : 0);
            Grid.SetColumn(_counts, compact ? 0 : 2);
            Grid.SetColumnSpan(_counts, compact ? 3 : 1);
            filters.ColumnDefinitions[2].Width = compact ? new GridLength(0) : GridLength.Auto;
        };

        _navigation.SelectionChanged += (_, _) =>
        {
            if (_closed) return;
            if (Busy || (_navigation.SelectedItem as ListViewItem)?.Tag is not Section section)
            {
                // Retain a valid selection even if a selection is cleared programmatically.
                var current = _navigation.Items.OfType<ListViewItem>().Single(i => (Section)i.Tag == _section);
                if (!ReferenceEquals(_navigation.SelectedItem, current)) _navigation.SelectedItem = current;
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
        _filter.SelectionChanged += (_, _) => { if (!_rebuilding) RefreshRows(Selected?.Offset); };
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
        {
            string label = SectionLabel((Section)item.Tag);
            ((TextBlock)item.Content).Text = label;
            Microsoft.UI.Xaml.Automation.AutomationProperties.SetName(item, label);
        }
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
        RefreshLocalizedComboSelections();
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

    private void RefreshLocalizedComboSelections()
    {
        // WinUI's closed ComboBox selection presenter may retain the original
        // string when an existing ComboBoxItem.Content changes. Re-select the
        // same index after localization; keep the underlying scenario and filter.
        bool wasUpdating = _vehicleUpdating;
        bool wasRebuilding = _rebuilding;
        _vehicleUpdating = true;
        _rebuilding = true;
        try
        {
            foreach (var combo in new[] { _vehicleScenario, _ignition, _monitorDirection, _monitorView, _filter })
            {
                int index = combo.SelectedIndex;
                if (index < 0) continue;
                combo.SelectedIndex = -1;
                combo.SelectedIndex = index;
            }
        }
        finally
        {
            _vehicleUpdating = wasUpdating;
            _rebuilding = wasRebuilding;
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

    private void ResizeForDisplay()
    {
        var area = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(AppWindow.Id, Microsoft.UI.Windowing.DisplayAreaFallback.Nearest);
        var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(this);
        double scale = Math.Max(1.0, GetDpiForWindow(hwnd) / 96.0);
        var work = area.WorkArea;
        int width = Math.Min(work.Width, (int)Math.Round(1200 * scale));
        int height = Math.Min(work.Height, (int)Math.Round(800 * scale));
        if (width > 0 && height > 0)
            AppWindow.MoveAndResize(new Windows.Graphics.RectInt32(work.X + (work.Width - width) / 2, work.Y + (work.Height - height) / 2, width, height));
    }

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint GetDpiForWindow(IntPtr hwnd);

    private void ShowSection()
    {
        bool configuration = _section == Section.Configuration;
        _heading.Text = SectionLabel(_section);
        _subtitle.Text = configuration
            ? _previewOnly
                ? T("Isolated CEM preview. Registry, INI changes and log access disabled.",
                    "Изолированный предпросмотр CEM. Реестр, изменение INI и чтение журналов отключены.")
                : T("Lab preview only. Export and ECU writes are unavailable.",
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
        if (!CanReadDiagnostics || Busy || _closed || _section != Section.Diagnostics || AcceptanceView || _monitorRunning) return;
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
        if (_closed || Busy || _section != Section.Diagnostics || AcceptanceView) { StopMonitor(); RenderMonitor(); return; }
        ReadMonitor();
    }

    private void StopMonitor()
    {
        _monitorRunning = false;
        _monitorTimer?.Stop();
    }

    private void ReadMonitor()
    {
        if (!CanReadDiagnostics || Busy || _closed || _section != Section.Diagnostics || AcceptanceView) return;
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
        if (_monitorView.Items.Count == 3)
        {
            ((ComboBoxItem)_monitorView.Items[0]).Content = "CAN Monitor";
            ((ComboBoxItem)_monitorView.Items[1]).Content = T("Diagnostic journal", "Журнал диагностики");
            ((ComboBoxItem)_monitorView.Items[2]).Content = T("Acceptance evidence", "Доказательства приёмки");
        }
        bool acceptance = AcceptanceView;
        if (acceptance) StopMonitor();
        foreach (var item in new FrameworkElement[] { _monitorPath, _monitorActions, _monitorDirection,
            _monitorFilter, _monitorStatus, _monitorRows })
            item.Visibility = acceptance ? Visibility.Collapsed : Visibility.Visible;
        _acceptancePanel.Visibility = acceptance ? Visibility.Visible : Visibility.Collapsed;
        RenderAcceptance();
        bool journal = _monitorView.SelectedIndex == 1;
        _journalSummary.Visibility = journal ? Visibility.Visible : Visibility.Collapsed;
        _journalSummary.Text = journal ? T("No log records available.", "Нет записей журнала.") : "";
        _monitorFilter.Header = journal
            ? T("Filter CAN ID / payload / PID / process / SID / DID / NRC", "Фильтр CAN ID / данных / PID / процесса / SID / DID / NRC")
            : T("Filter CAN ID / payload / PID / process", "Фильтр CAN ID / данных / PID / процесса");
        bool enabled = CanReadDiagnostics && !Busy && !_closed && !acceptance;
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

    private void ImportAcceptance()
    {
        if (!CanReadDiagnostics || Busy || _closed || _section != Section.Diagnostics || !AcceptanceView || !_acceptanceImport.IsEnabled) return;
        try
        {
            var report = AcceptanceReportReader.ReadFile(_acceptancePath.Text.Trim());
            _acceptanceReports[report.Stage] = report;
            _acceptanceFailed = false;
            _acceptanceExportResult = 0;
        }
        catch (Exception) { _acceptanceFailed = true; }
        RenderAcceptance();
    }

    private void ExportAcceptance()
    {
        if (_ephemeral || Busy || _closed || _section != Section.Diagnostics || !AcceptanceView || !_acceptanceExport.IsEnabled) return;
        try
        {
            AcceptanceSummaryExport.WriteNew(_acceptanceExportPath.Text.Trim(), _acceptanceSummary.Text);
            _acceptanceExportResult = 1;
        }
        catch (Exception) { _acceptanceExportResult = -1; }
        RenderAcceptance();
    }

    private string BundleGateLabel(string key) => key switch
    {
        "environment" => T("Environment", "Среда"),
        "native_preflight" => T("Native preflight", "Нативный транспорт"),
        "registration" => T("Registration", "Регистрация"),
        "binding" => T("VIDA binding", "Привязка VIDA"),
        "readvin" => "ReadVin",
        "ecu" => T("ECU identification", "Идентификация ECU"),
        "catalog" => "T111/T122",
        "file_integrity" => T("Evidence integrity", "Целостность доказательств"),
        _ => key
    };

    private string BundleGateState(string value) => value switch
    {
        "blocked_or_synthetic" => T("Blocked or synthetic", "Заблокировано или синтетика"),
        "owner_claims_only" => T("Owner claims only", "Только заявления владельца"),
        "reported_preflight_consistent" => T("Reported preflight consistent", "Заявленная проверка согласована"),
        "partial_checkpoints" => T("Partial checkpoints", "Неполные контрольные точки"),
        "reported_checkpoints_consistent" => T("Reported checkpoints consistent", "Заявленные точки согласованы"),
        "review_required" => T("Review required", "Требуется проверка"),
        "unbound_report_observation" => T("Unbound observation", "Наблюдение без привязки"),
        "not_tested" or "not_supplied" => T("Not tested / not supplied", "Не проверено / не предоставлено"),
        "supplied_digests_match" => T("Reported digests match", "Заявленные отпечатки совпадают"),
        "no_evidence_files" => T("No evidence files", "Нет файлов доказательств"),
        _ => value
    };

    private string AcceptanceMatch(AcceptanceSourceMatch match) => match switch
    {
        AcceptanceSourceMatch.Matches => T("matches", "совпадает"),
        AcceptanceSourceMatch.Differs => T("differs", "отличается"),
        AcceptanceSourceMatch.NotDeclared => T("not declared", "не указан"),
        _ => T("not compared", "не сравнивался")
    };

    private void RenderAcceptance()
    {
        _acceptanceHead.Header = T("Expected source HEAD (optional, 40 hex)", "Ожидаемый HEAD (необязательно, 40 hex)");
        _acceptanceDll.Header = T("Expected native DLL SHA256 (optional)", "Ожидаемый SHA256 нативной DLL (необязательно)");
        _acceptancePath.Header = T("Local JSON report (absolute path)", "Локальный JSON-отчёт (абсолютный путь)");
        _acceptanceImport.Content = T("Import / replace report", "Импортировать / заменить отчёт");
        _acceptanceClear.Content = T("Clear reports", "Очистить отчёты");
        _acceptanceSummary.Header = T("Summary (select and copy)", "Сводка (выделить и скопировать)");
        bool enabled = CanReadDiagnostics && !Busy && !_closed && _section == Section.Diagnostics && AcceptanceView;
        string head = _acceptanceHead.Text.Trim(), dll = _acceptanceDll.Text.Trim();
        bool valid = (head.Length == 0 || AcceptanceReportReader.IsHash(head, 40)) &&
            (dll.Length == 0 || AcceptanceReportReader.IsHash(dll, 64));
        _acceptancePath.IsEnabled = _acceptanceHead.IsEnabled = _acceptanceDll.IsEnabled = enabled;
        _acceptanceImport.IsEnabled = enabled && valid && _acceptancePath.Text.Trim().Length > 0;
        _acceptanceClear.IsEnabled = enabled && _acceptanceReports.Count > 0;
        _acceptanceExportPath.Header = T("New external summary file (.txt)", "Новый внешний файл сводки (.txt)");
        _acceptanceExport.Content = T("Export summary", "Экспортировать сводку");
        _acceptanceExportPath.IsEnabled = enabled && !_ephemeral;
        _acceptanceExport.IsEnabled = enabled && !_ephemeral && valid && _acceptanceReports.Count > 0 && _acceptanceExportPath.Text.Trim().Length > 0;
        _acceptanceExportStatus.Text = _ephemeral ? T("Export disabled in isolated mode. Copy the summary instead.", "Экспорт отключён в изолированном режиме. Скопируйте сводку.") :
            _acceptanceExportResult switch { 1 => T("New summary created.", "Новая сводка создана."), -1 => T("Export rejected. Existing files are never overwritten.", "Экспорт отклонён. Существующие файлы не перезаписываются."), _ => "" };
        _acceptanceStatus.Text = !valid ? T("Invalid expected fingerprint.", "Некорректный ожидаемый отпечаток.") :
            _acceptanceFailed ? T("Import rejected; prior reports retained.", "Импорт отклонён; прежние отчёты сохранены.") :
            T("Imported reports: ", "Импортировано отчётов: ") + _acceptanceReports.Count;
        var lines = new List<string> { T("Local report claims only. No runtime acceptance is inferred.", "Только сведения из локальных отчётов. Фактическая приёмка не подтверждается.") };
        if (_acceptanceReports.TryGetValue("VC092", out var aggregate) && aggregate.Bundle is { } bundle)
        {
            lines.Add(T("VC092 · Reported aggregate, not reverified by this application", "VC092 · Заявленная сводка, не перепроверенная приложением"));
            lines.Add(T("Scope: ", "Источник: ") + bundle.Scope);
            lines.Add(T("Historical / reported HEAD: ", "Исторический / заявленный HEAD: ") + aggregate.SourceSha);
            lines.Add(T("Registration checkpoints: ", "Контрольные точки регистрации: ") + bundle.Checkpoints + "/5");
            foreach (var gate in bundle.Gates)
                lines.Add(BundleGateLabel(gate.Key) + ": " + BundleGateState(gate.State) + " [" + gate.State + "]");
            lines.Add(T("Catalog sample: ", "Выборка каталога: ") + bundle.CatalogMatched + "/" + bundle.CatalogSampled);
            lines.Add(T("Unconfirmed owner claims: ", "Неподтверждённые заявления владельца: ") + (bundle.MissingClaims.Count == 0 ? T("none declared missing; still not verified", "нет заявленных пропусков; всё равно не проверено") : string.Join(", ", bundle.MissingClaims)));
            lines.Add("Manifest SHA256: " + bundle.ManifestSha);
            foreach (var entry in bundle.Evidence)
            {
                var individual = _acceptanceReports.Values.FirstOrDefault(r => BundleSummary.RoleForStage(r.Stage) == entry.Role);
                string state = individual is null ? T("individual file not imported", "отдельный файл не импортирован") :
                    AcceptanceMatch(bundle.CompareReport(individual) == "matches" ? AcceptanceSourceMatch.Matches : AcceptanceSourceMatch.Differs);
                lines.Add(entry.Role + " · " + state + " · " + entry.Sha256);
            }
            lines.Add("");
        }
        foreach (var report in _acceptanceReports.Values)
        {
            string status = report.Observation switch
            {
                AcceptanceObservation.ReportedPass => T("Reported PASS", "Заявленный PASS"),
                AcceptanceObservation.ReportedFail => T("Reported FAIL", "Заявленный FAIL"),
                AcceptanceObservation.Observed => T("Observation", "Наблюдение"),
                _ => T("Review required", "Требуется проверка")
            };
            lines.Add($"{report.Stage} · {status} · {report.Detail}" +
                (report.Total is int total ? $" · {report.Passed}/{total}" : ""));
            lines.Add("HEAD: " + (report.SourceSha ?? "—") + " · " + AcceptanceMatch(report.CompareSource(valid ? head : null)));
            var dllMatch = report.NativeSha is null ? AcceptanceSourceMatch.NotDeclared :
                !valid || dll.Length == 0 ? AcceptanceSourceMatch.NotCompared :
                report.NativeSha.Equals(dll, StringComparison.OrdinalIgnoreCase) ? AcceptanceSourceMatch.Matches : AcceptanceSourceMatch.Differs;
            lines.Add("DLL SHA256: " + (report.NativeSha ?? "—") + " · " + AcceptanceMatch(dllMatch));
            lines.Add("JSON SHA256: " + report.ReportSha);
        }
        lines.Add("");
        foreach (string stage in new[] { "VC090A", "VC090B/Baseline", "VC090B/InstallCancelled", "VC090B/Installed",
            "VC090B/RemoveCancelled", "VC090B/Restored", "VC090C", "VC090D", "VC090E", "VC092" })
            if (!_acceptanceReports.ContainsKey(stage)) lines.Add(stage + T(" · No report imported", " · Отчёт не импортирован"));
        lines.Add("");
        lines.Add(T("Outstanding runtime gates (not verified by these reports):", "Открытые этапы фактической приёмки (не подтверждены этими отчётами):"));
        lines.Add(T("Registration install/remove; VIDA provider selection; loaded module identity; ReadVin; ECU identification; original T111/T122 catalog; physical J2534 — Not tested.",
            "Установка/удаление регистрации; выбор адаптера VIDA; идентичность модуля; ReadVin; идентификация ECU; оригинальный каталог T111/T122; физический J2534 — не проверено."));
        _acceptanceSummary.Text = string.Join(Environment.NewLine, lines);
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
        if (!CanReadDiagnostics || Busy || _closed || _section != Section.Modules) return;
        _moduleSlots = null;
        _moduleFailed = false;
        try
        {
            if (_diagnosticsOnly)
            {
                _moduleSlots = NativeEcuInventory.Inspect(NativeEcmScenarioApply.ReadProfile(_moduleProfile.Text.Trim()));
            }
            else
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
        }
        catch (Exception) { _moduleFailed = true; }
        RenderModules();
    }

    private void RenderModules()
    {
        _moduleRefresh.Content = T("Read configured ECUs", "Прочитать настроенные ECU");
        _moduleProfile.Header = T("Local virtualcar.ini (read-only, not registered)", "Локальный virtualcar.ini (только чтение, без регистрации)");
        _moduleProfile.IsEnabled = _diagnosticsOnly && !Busy && !_closed;
        _moduleRefresh.IsEnabled = CanReadDiagnostics && !Busy && !_closed;
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
            AutomationId(row, "VC088.Ecu." + slot.Index.ToString(System.Globalization.CultureInfo.InvariantCulture));
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
        if (!CanManageRegistration || _driverBusy || _closed) return;
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
        bool enabled = CanManageRegistration && !Busy && !_closed && File.Exists(DriverToolPath);
        _driverPath.IsEnabled = enabled && _driverInfo.Status == DriverRegistration.State.Absent;
        _driverRefresh.IsEnabled = CanManageRegistration && !Busy && !_closed;
        _driverInstall.IsEnabled = enabled && _driverInfo.Status == DriverRegistration.State.Absent;
        _driverRemove.IsEnabled = enabled && (_driverInfo.Status == DriverRegistration.State.Registered ||
            (!_registrationOnly && _driverInfo.Status == DriverRegistration.State.LegacyRegistered));
        if (!CanManageRegistration)
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
        if (!CanManageRegistration || Busy || _closed || _section != Section.Connection || !File.Exists(DriverToolPath)) return;
        RefreshDriver();
        if (install ? _driverInfo.Status != DriverRegistration.State.Absent :
            _driverInfo.Status is not (DriverRegistration.State.Registered or DriverRegistration.State.LegacyRegistered)) return;
        if (_registrationOnly && !install && _driverInfo.Status != DriverRegistration.State.Registered) return;
        string path = install ? _driverPath.Text.Trim() : _driverInfo.Library!;
        _driverBusy = true;
        UpdateControls();
        RenderDriver();
        try
        {
            string? hash = install || _registrationOnly ? await Task.Run(() => DriverRegistration.Fingerprint(path)) : null;
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
            if (await dialog.ShowAsync() != ContentDialogResult.Primary || _closed)
            {
                DriverResult("Registration change cancelled.", "Изменение регистрации отменено.");
                return;
            }
            var start = new ProcessStartInfo
            {
                FileName = DriverToolPath,
                WorkingDirectory = Path.GetDirectoryName(DriverToolPath)!,
                UseShellExecute = true,
                Verb = "runas"
            };
            start.ArgumentList.Add(install ? "install" : _registrationOnly ? "remove-canonical" : "remove");
            start.ArgumentList.Add(path);
            if (hash is not null) start.ArgumentList.Add(hash);
            using var process = Process.Start(start) ?? throw new InvalidOperationException();
            await process.WaitForExitAsync();
            var after = DriverRegistration.Read();
            bool verified = install
                ? after.Status == DriverRegistration.State.Registered &&
                  string.Equals(after.Library, Path.GetFullPath(path), StringComparison.OrdinalIgnoreCase) &&
                  string.Equals(DriverRegistration.Fingerprint(path), hash, StringComparison.OrdinalIgnoreCase)
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

    private static void Add(Grid grid, FrameworkElement child, int row, int column = 0)
    {
        Grid.SetRow(child, row); Grid.SetColumn(child, column); grid.Children.Add(child);
    }

    private async Task LoadAsync()
    {
        if (!CanLoadProfile || _closed || Busy || _model is not null) return;
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
                    AutomationId(item, "VC087.Row." + row.Offset.ToString(System.Globalization.CultureInfo.InvariantCulture));
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
            {
                var item = new ComboBoxItem { Tag = option, Content = $"{option.Code} — {option.Text}" };
                AutomationId(item, "VC087.Option." + option.Code);
                _options.Items.Add(item);
            }
        }
        UpdateControls();
    }

    private void UpdateControls()
    {
        bool loaded = Snapshot is not null && !Busy;
        _python.IsEnabled = _script.IsEnabled = _data.IsEnabled = CanLoadProfile && _model is null && !Busy;
        _load.IsEnabled = CanLoadProfile && _model is null && !Busy;
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
