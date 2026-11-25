using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VirtualCar.Core;

namespace VirtualCar.WinUI;

// Standalone lab preview. No activation, export, ECU I/O or provider registration.
public sealed class CemPreviewWindow : Window
{
    private readonly TextBox _python = new() { Header = "Python.exe (абсолютный путь)" };
    private readonly TextBox _script = new() { Header = "vc071_view.py (абсолютный путь)" };
    private readonly TextBox _data = new() { Header = "Локальный каталог CEM529 (вне Git)" };
    private readonly TextBox _search = new() { PlaceholderText = "Поиск по названию или смещению" };
    private readonly ComboBox _filter = new() { MinWidth = 150 };
    private readonly ListView _rows = new() { SelectionMode = ListViewSelectionMode.Single };
    private readonly ComboBox _options = new() { HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly TextBlock _counts = new() { Text = "Профиль не загружен" };
    private readonly TextBlock _detail = new() { TextWrapping = TextWrapping.Wrap };
    private readonly TextBlock _audit = new() { TextWrapping = TextWrapping.Wrap, IsTextSelectionEnabled = true };
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap };
    private readonly Button _load = new() { Content = "Загрузить профиль" };
    private readonly Button _cancel = new() { Content = "Отмена" };
    private readonly Button _reset = new() { Content = "Закрыть профиль" };
    private readonly Button _preview = new() { Content = "Проверить вариант" };
    private readonly Button _revert = new() { Content = "Вернуть исходное" };
    private readonly Button _clear = new() { Content = "Сбросить все изменения" };
    private readonly ProgressRing _progress = new() { Width = 24, Height = 24 };
    private CemPreviewViewModel? _model;
    private CancellationTokenSource? _operation;
    private Dictionary<int, string> _edits = new();
    private bool _closed;
    private bool _rebuilding;
    private bool Busy => _operation is not null;
    private CemPreview? Snapshot => _model?.Snapshot;
    private CemRow? Selected => (_rows.SelectedItem as ListViewItem)?.Tag as CemRow;

    public CemPreviewWindow()
    {
        Title = "Virtual Car — CEM529 Preview";
        var root = new Grid { Padding = new Thickness(20), RowSpacing = 12 };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var heading = new StackPanel { Spacing = 4 };
        heading.Children.Add(new TextBlock { Text = "Конфигурация CEM529", FontSize = 28 });
        heading.Children.Add(new TextBlock
        {
            Text = "Лабораторный предварительный просмотр. Экспорт и запись в ECU недоступны.",
            TextWrapping = TextWrapping.Wrap
        });
        Add(root, heading, 0);

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
        Add(root, inputs, 1);

        var filters = new Grid { ColumnSpacing = 12 };
        filters.ColumnDefinitions.Add(new ColumnDefinition());
        filters.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        filters.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        foreach (string item in new[] { "Все", "Изменённые", "Защищённые", "Доступные" }) _filter.Items.Add(item);
        _filter.SelectedIndex = 0;
        Add(filters, _search, 0); Add(filters, _filter, 0, 1); Add(filters, _counts, 0, 2);
        Add(root, filters, 2);

        var workspace = new Grid { ColumnSpacing = 20 };
        workspace.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(3, GridUnitType.Star) });
        workspace.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(2, GridUnitType.Star) });
        Add(workspace, _rows, 0, 0);
        var right = new StackPanel { Spacing = 10 };
        right.Children.Add(new TextBlock { Text = "Параметр", FontSize = 20 });
        right.Children.Add(_detail);
        right.Children.Add(_options);
        right.Children.Add(_preview); right.Children.Add(_revert); right.Children.Add(_clear);
        right.Children.Add(new TextBlock { Text = "Аудит конфигурации", FontSize = 20 });
        right.Children.Add(_audit);
        Add(workspace, new ScrollViewer { Content = right, VerticalScrollBarVisibility = ScrollBarVisibility.Auto }, 0, 1);
        Add(root, workspace, 3);
        Add(root, _status, 4);
        Content = root;
        AppWindow.Resize(new Windows.Graphics.SizeInt32(1200, 800));

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
        RefreshRows(null);
    }

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
                _status.Text = "Не удалось открыть профиль. Проверьте локальные пути.";
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
            _status.Text = "Проверка конфигурации…";
            RefreshRows(null);
            await model.RefreshAsync(candidate.Select(p => new CemEdit(p.Key, p.Value)), cancel.Token);
            if (_closed) return;
            var result = model.Snapshot ?? throw new InvalidDataException();
            _edits = new Dictionary<int, string>(candidate);
            _status.Text = result.Status switch
            {
                "pass" => "Предварительная проверка пройдена. Не является приёмкой VIDA.",
                "review" => "Требуется проверка предупреждений или топологии.",
                _ => "Вариант заблокирован политикой зависимостей."
            };
        }
        catch (Exception ex)
        {
            _model = null;
            _edits.Clear();
            if (!_closed) _status.Text = ex is OperationCanceledException
                ? "Операция отменена. Загрузите исходный профиль заново."
                : "Проверка не выполнена. Загрузите исходный профиль заново.";
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
        _status.Text = "Профиль закрыт.";
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
            _counts.Text = snapshot is null ? "Нет данных" :
                $"Параметры: {snapshot.Rows.Count} · защищено: {snapshot.Rows.Count(r => r.Locked)} · изменено: {snapshot.Rows.Count(r => r.Changed)}";
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
                    string state = row.Locked ? "[Защищено]" : row.Changed ? "[Изменено]" : "";
                    var item = new ListViewItem
                    {
                        Tag = row,
                        Content = new TextBlock { Text = $"{row.Offset:D3}  {row.Name}  {state}\n{row.SelectedCode}  {row.SelectedText}", TextWrapping = TextWrapping.Wrap }
                    };
                    _rows.Items.Add(item);
                    if (selectedOffset == row.Offset) _rows.SelectedItem = item;
                }
                _audit.Text = $"Статус: {snapshot.Status}\nТопология: {(snapshot.TopologyReviewRequired ? "требует проверки" : "без новых замечаний")}\n" +
                    $"Ошибки: {snapshot.Errors.Count}\n{string.Join("\n", snapshot.Errors)}\n" +
                    $"Предупреждения: {snapshot.Warnings.Count}\n{string.Join("\n", snapshot.Warnings)}\n" +
                    $"SHA256 аудита: {snapshot.AuditSha256}\nOEM / VIDA / физический J2534: не подтверждены.";
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
        _detail.Text = row is null ? "Выберите параметр." :
            $"{row.Name}\nСмещение: {row.Offset}\nИсходное: {row.BaselineCode} — {row.BaselineText}\n" +
            $"Выбранное: {row.SelectedCode} — {row.SelectedText}\n" +
            (row.Locked ? "Защищённое поле." : "Допустимые варианты из каталога:");
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
        _search.IsEnabled = _filter.IsEnabled = _rows.IsEnabled = loaded;
        _options.IsEnabled = loaded && Selected is { Locked: false } && _options.Items.Count > 0;
        _preview.IsEnabled = _options.IsEnabled && (_options.SelectedItem as ComboBoxItem)?.Tag is CemOption { Selectable: true };
        _revert.IsEnabled = loaded && Selected is { Changed: true, Locked: false };
        _clear.IsEnabled = loaded && _edits.Count > 0;
    }
}
