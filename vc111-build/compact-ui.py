"""VC113: compact WinUI and bundled interpreter path. Runs after VC112 staging patch."""
from pathlib import Path
import sys

def once(s,a,b):
    if s.count(a)!=1: raise ValueError("Missing or ambiguous VC113 anchor: "+a[:120])
    return s.replace(a,b,1)

def transform(s):
    s=once(s,'    private readonly TextBox pythonPath = new() { Header = "Python executable / Интерпретатор Python" };',
        '    private readonly TextBox pythonPath = new() { Header = "Встроенный Python", IsReadOnly = true, Text = System.IO.Path.Combine(AppContext.BaseDirectory,"python","python.exe") };')
    s=once(s,'    private readonly TextBox toolsPath = new() { Header = "VC109 utility directory / Каталог утилит",',
        '    private readonly TextBox toolsPath = new() { Header = "Служебные файлы", IsReadOnly = true,')
    s=once(s,'    private readonly TextBox buildPath = new() { Header = "Original VC108R inner ZIP / Исходный ZIP VC108R",',
        '    private readonly TextBox buildPath = new() { IsReadOnly = true, Header = "Original VC108R inner ZIP / Исходный ZIP VC108R",')
    s=once(s,'    private bool busy, rendering;', '''    private readonly TextBlock telemetry = new() { TextWrapping = TextWrapping.Wrap, FontSize = 12 };
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint GetDpiForWindow(nint hwnd);
    private void SizeCompact()
    {
        uint dpi = GetDpiForWindow(WinRT.Interop.WindowNative.GetWindowHandle(this));
        double scale = (dpi == 0 ? 96 : dpi) / 96.0;
        var area = Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(AppWindow.Id, Microsoft.UI.Windowing.DisplayAreaFallback.Primary);
        int width = (int)Math.Round(460 * scale);
        int height = (int)Math.Round(520 * scale);
        if (area is not null)
        {
            width = Math.Min(width, area.WorkArea.Width);
            height = Math.Min(height, area.WorkArea.Height);
        }
        AppWindow.Resize(new Windows.Graphics.SizeInt32(width, height));
    }
    private bool busy, rendering;''')
    a=s.index('        Title = "Virtual Car — Live Control Lab";')
    b=s.index('        foreach (var pair in new (DependencyObject Element, string Id)[]',a)
    s=s[:a]+'''        Title = "Virtual Car · XC90";
        create.Content = "Создать сеанс"; end.Content = "Завершить";
        clientsClosed.Content = "VIDA и клиенты закрыты";
        ignition.Header = "Зажигание";
        start.Content = "Старт"; stop.Content = "Стоп"; reset.Content = "Сброс";
        pedal.Header = "Газ (%)";
        applyProvider.Content = "Подключить VIDA";
        restoreProvider.Content = "Вернуть драйвер";
        sourcePath.Header = "Исходный провайдер";
        profile.Header = "Секция IPC";
        values.FontSize = 26;
        status.FontSize = 12;
        var panel = new StackPanel { Padding = new Thickness(14), Spacing = 7 };
        panel.Children.Add(new TextBlock { Text = "XC90 V8", FontSize = 22 });
        panel.Children.Add(new TextBlock { Text = "Виртуальный автомобиль · J2534", FontSize = 12 });
        panel.Children.Add(status);
        panel.Children.Add(new Border { Padding = new Thickness(10), CornerRadius = new CornerRadius(8),
            BorderThickness = new Thickness(1), BorderBrush = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Gray),
            Child = values });
        var session = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
        session.Children.Add(create); session.Children.Add(end); panel.Children.Add(session);
        var engine = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
        engine.Children.Add(start); engine.Children.Add(stop); engine.Children.Add(reset);
        panel.Children.Add(ignition); panel.Children.Add(engine); panel.Children.Add(pedal);
        panel.Children.Add(clientsClosed);
        var connection = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
        connection.Children.Add(applyProvider); connection.Children.Add(restoreProvider);
        panel.Children.Add(connection);
        var details = new StackPanel { Spacing = 6 };
        foreach (var item in new FrameworkElement[] { telemetry, binding, sourcePath, pythonPath, toolsPath, buildPath, profile }) details.Children.Add(item);
        panel.Children.Add(new Expander { Header = "Подробности и настройки", Content = details,
            HorizontalAlignment = HorizontalAlignment.Stretch, HorizontalContentAlignment = HorizontalAlignment.Stretch });
        applyProvider.Click += async (_,_) => await ConnectAsync();
        restoreProvider.Click += async (_,_) => await ChangeProviderAsync(true);
        var scroll = new ScrollViewer { Content = panel, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        bool sized = false;
        scroll.Loaded += (_,_) => { if (!sized) { sized = true; SizeCompact(); } };
        Content = scroll;
        foreach (var item in new[] { "0 — выкл.", "I — аксессуары (CEM не проверен)", "II — вкл." }) ignition.Items.Add(item);
'''+s[b:]
    s=once(s,'    private async Task ChangeProviderAsync(bool rollback)', '''    private async Task ConnectAsync()
    {
        if (busy || clientsClosed.IsChecked != true || publisher?.Read().Snapshot is null) return;
        if (flow is null) await PrepareProviderAsync();
        if (flow?.CanApply == true && clientsClosed.IsChecked == true)
            await ChangeProviderAsync(false);
    }
    private async Task ChangeProviderAsync(bool rollback)''')
    s=once(s,'applyProvider.IsEnabled=ready && flow?.CanApply==true && restored && clientsClosed.IsChecked==true;',
           'applyProvider.IsEnabled=ready && (flow is null || flow.CanApply) && restored && clientsClosed.IsChecked==true;')
    s=once(s,'            string message = busy ? "Busy / Выполняется" : state?.Failed == true ? "Publishing failed; no live data / Ошибка публикации" : ready ? "Published locally; DLL receipt unverified / Опубликовано, приём DLL не проверен" : publisher is null ? "No session / Нет сеанса" : "Waiting for fresh publication / Ожидание актуального снимка";',
           '''            string message = busy ? "Выполняется…" : state?.Failed == true ? "Ошибка публикации" : ready ? (active ? "Драйвер выбран · приём DLL не проверен" : "Автомобиль готов · VIDA не подключена") : publisher is null ? "Нет сеанса" : "Ожидание данных…";''')
    s=once(s,r'''                values.Text = $"{v.Engine} · {e.Rpm} rpm\n{e.BatteryMv/1000.0:F2} V · {e.CoolantC} °C\nMAF {e.MafCentiGps/100.0:F2} g/s · MAP {e.ManifoldKpa} kPa\nLoad {e.LoadPermille/10.0:F1}% · {e.SpeedKph} km/h\nSequence: {v.Sequence}";''',
           r'''                values.Text = $"{e.Rpm} об/мин\n{e.BatteryMv/1000.0:F1} В  ·  {e.CoolantC} °C";
                telemetry.Text = $"{v.Engine} · MAF {e.MafCentiGps/100.0:F2} g/s · MAP {e.ManifoldKpa} kPa\nНагрузка {e.LoadPermille/10.0:F1}% · {e.SpeedKph} км/ч · Seq {v.Sequence}";''')
    s=once(s,'            else values.Text = "—";','            else { values.Text = "— об/мин\\n— В  ·  — °C"; telemetry.Text = "Нет актуальных данных"; }')
    return s

def patch(root):
    p=root/'acceptance/prepare_all.py'
    s=p.read_text(encoding='utf-8')
    anchor="    print('VC112_PUBLICATION_HOTFIX=STAGED')"
    # prepare_all executes inside extracted source directory, never original repo.
    s=once(s,anchor,anchor+'\n    from compact_ui import transform as compact_transform\n    window.write_bytes(compact_transform(window.read_text(encoding="utf-8")).encode("utf-8"))\n    print("VC113_COMPACT_UI=STAGED")')
    p.write_bytes(s.encode('utf-8'))
    (p.parent/'compact_ui.py').write_bytes(Path(__file__).read_bytes())
if __name__=='__main__':
    patch(Path(sys.argv[1]))
    print('VC113_COMPACT_PATCH=PASS')
