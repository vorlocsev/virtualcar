using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VirtualCar.Core;

namespace VirtualCar.WinUI;

// Standalone lab preview. No activation, export, ECU I/O or provider registration.
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
    private readonly TextBlock _placeholderHeading = new() { FontSize = 24, TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _placeholderText = new() { TextWrapping = TextWrapping.Wrap };
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
    private bool Busy => _operation is not null;
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
        AutomationId(_placeholderHeading, "VC077.PlaceholderHeading");
        AutomationId(_placeholderText, "VC077.PlaceholderText");
        page.Children.Add(_editor);
        page.Children.Add(_placeholder);
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
            ShowSection();
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
        Closed += (_, _) => { _closed = true; _operation?.Cancel(); };
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
            : T("Planned workspace — not implemented.", "Запланированный раздел — не реализован.");
        _editor.Visibility = configuration ? Visibility.Visible : Visibility.Collapsed;
        _placeholder.Visibility = configuration ? Visibility.Collapsed : Visibility.Visible;
        _placeholderHeading.Text = SectionLabel(_section);
        _placeholderText.Text = _section switch
        {
            Section.Vehicle => T("Vehicle state and scenario controls are planned. No runtime is started here.",
                "Планируется управление состоянием и сценариями автомобиля. Запуск эмулятора недоступен."),
            Section.Modules => T("ECU inventory and identification are planned. No ECU discovery is performed.",
                "Планируется список и идентификация блоков. Поиск ECU не выполняется."),
            Section.Diagnostics => T("Read-only diagnostic tools are planned. No diagnostic messages are sent.",
                "Планируются инструменты диагностики только для чтения. Запросы не отправляются."),
            Section.Connection => T("Virtual adapter and connection status are planned. No provider is installed or opened.",
                "Планируется подключение виртуального адаптера. Установка и открытие провайдера не выполняются."),
            _ => ""
        };
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
        if (Busy || _model is not null) return;
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
        _python.IsEnabled = _script.IsEnabled = _data.IsEnabled = _model is null && !Busy;
        _load.IsEnabled = _model is null && !Busy;
        _cancel.IsEnabled = Busy;
        _reset.IsEnabled = _model is not null && !Busy;
        _progress.IsActive = Busy;
        _navigation.IsEnabled = !Busy;
        _search.IsEnabled = _filter.IsEnabled = _rows.IsEnabled = loaded;
        _options.IsEnabled = loaded && Selected is { Locked: false } && _options.Items.Count > 0;
        _preview.IsEnabled = _options.IsEnabled && (_options.SelectedItem as ComboBoxItem)?.Tag is CemOption { Selectable: true };
        _revert.IsEnabled = loaded && Selected is { Changed: true, Locked: false };
        _clear.IsEnabled = loaded && _edits.Count > 0;
    }
}
