"""VC114: no external live session. Stage byte-exact legacy INI and compact binding UI."""
from pathlib import Path
import hashlib, sys, runpy

def sha(b): return hashlib.sha256(b).hexdigest().upper()
def once(s,a,b):
    if s.count(a)!=1: raise ValueError("Unexpected VC114 anchor: "+a[:100])
    return s.replace(a,b,1)
def read(root,p,digest):
    raw=(root/p).read_bytes()
    if sha(raw)!=digest.upper(): raise ValueError("Unexpected input "+p)
    return raw.decode("utf-8")
def write(root,p,s): (root/p).write_bytes(s.encode("utf-8"))

WINDOW=r'''using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace VirtualCar.WinUI;

// No background state publisher or vehicle session is created.
internal sealed class LiveControlWindow : Window
{
    private readonly TextBox sourcePath = new() { Header = "Рабочий провайдер", Text = @"C:\VC099-VIDA-511\provider" };
    private readonly TextBox buildPath = new() { IsReadOnly = true, Header = "Original VC108R inner ZIP / Исходный ZIP VC108R", Text = @"E:\VirtualCar\Builds\VC108R-45858063194-1\VirtualCar-VC108R-development.zip" };
    private readonly CheckBox closed = new() { Content = "VIDA и клиенты закрыты" };
    private readonly Button connect = new() { Content = "Подключить VIDA", HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly Button restore = new() { Content = "Вернуть прежний драйвер", HorizontalAlignment = HorizontalAlignment.Stretch };
    private readonly TextBlock status = new() { TextWrapping = TextWrapping.Wrap, FontSize = 14 };
    private readonly TextBlock detail = new() { TextWrapping = TextWrapping.Wrap, FontSize = 12 };
    private ProviderFlow? flow;
    private bool busy;
    private string notice = "";
    private readonly string python = Path.Combine(AppContext.BaseDirectory,"python","python.exe");
    private readonly string tools = Path.Combine(AppContext.BaseDirectory,"VC109-tools");

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint GetDpiForWindow(nint hwnd);
    private void SizeCompact()
    {
        uint dpi=GetDpiForWindow(WinRT.Interop.WindowNative.GetWindowHandle(this));
        double scale=(dpi==0?96:dpi)/96.0;
        var area=Microsoft.UI.Windowing.DisplayArea.GetFromWindowId(AppWindow.Id,Microsoft.UI.Windowing.DisplayAreaFallback.Primary);
        int w=(int)Math.Round(420*scale), h=(int)Math.Round(360*scale);
        if(area is not null){w=Math.Min(w,area.WorkArea.Width);h=Math.Min(h,area.WorkArea.Height);}
        AppWindow.Resize(new Windows.Graphics.SizeInt32(w,h));
    }
    public LiveControlWindow()
    {
        Title="Virtual Car · XC90";
        var panel=new StackPanel{Padding=new Thickness(16),Spacing=10};
        panel.Children.Add(new TextBlock{Text="XC90 V8",FontSize=26});
        panel.Children.Add(new TextBlock{Text="Автономный автомобиль · без IPC",FontSize=12});
        panel.Children.Add(status);
        panel.Children.Add(closed);panel.Children.Add(connect);panel.Children.Add(restore);
        var settings=new StackPanel{Spacing=6};
        settings.Children.Add(sourcePath);settings.Children.Add(buildPath);settings.Children.Add(detail);
        panel.Children.Add(new Expander{Header="Подробности",Content=settings,HorizontalAlignment=HorizontalAlignment.Stretch,HorizontalContentAlignment=HorizontalAlignment.Stretch});
        var scroll=new ScrollViewer{Content=panel,VerticalScrollBarVisibility=ScrollBarVisibility.Auto};
        bool sized=false;
        scroll.Loaded+=(_,_)=>{if(!sized){sized=true;SizeCompact();}};
        Content=scroll;
        connect.Click+=async(_,_)=>await ChangeAsync(false);
        restore.Click+=async(_,_)=>await ChangeAsync(true);
        closed.Checked+=(_,_)=>Render();closed.Unchecked+=(_,_)=>Render();
        sourcePath.TextChanged+=(_,_)=>Render();
        AppWindow.Closing+=(_,a)=>{if(busy)a.Cancel=true;};
        try
        {
            flow=ProviderFlow.Recover(python,tools,buildPath.Text);
            if(flow is not null) sourcePath.Text=Path.GetDirectoryName(flow.Original)!;
        }
        catch(Exception ex){notice="Проверка регистрации: "+ex.Message;}
        Render();
    }
    private void Render()
    {
        bool active=flow?.Active()==true;
        bool original=flow?.Restored()??ProviderFlow.IsOriginal(sourcePath.Text);
        status.Text=(busy?"Выполняется…":active?"Драйвер выбран · можно открыть VIDA":original?"Готов к подключению":"Другая регистрация · проверьте путь")
            +(notice.Length>0?"\n"+notice:"");
        connect.IsEnabled=!busy && closed.IsChecked==true && original && (flow is null||flow.CanApply);
        restore.IsEnabled=!busy && closed.IsChecked==true && active;
        closed.IsEnabled=!busy;
        sourcePath.IsEnabled=!busy && flow is null;
        detail.Text=flow is null?"Используется текущий INI. Двигатель моделируется внутри DLL; показания читаются в VIDA.":
            "Кандидат: "+flow.Target+"\nЖурнал отката: "+flow.Journal;
    }
    private async Task ChangeAsync(bool undo)
    {
        if(busy||closed.IsChecked!=true)return;
        busy=true;notice="";Render();
        try
        {
            if(undo)
            {
                if(flow is null)throw new InvalidOperationException("Нет журнала отката");
                await flow.RollbackAsync();flow=null;notice="Прежний драйвер восстановлен";
            }
            else
            {
                if(flow is null)
                {
                    var candidate=new ProviderFlow(python,tools,buildPath.Text,sourcePath.Text,Guid.NewGuid().ToString("N"));
                    await candidate.PrepareAsync();
                    flow=candidate;
                }
                await flow.ApplyAsync();notice="Подключено. В VIDA: J2534 Lab Adapter";
            }
        }
        catch(Exception ex){notice=ex.Message;}
        finally{busy=false;closed.IsChecked=false;Render();}
    }
}
'''

def patch(root):
    p='vc109/prepare_profile.py'; s=read(root,p,'86eba3912a0ccee4a2ebd75b6d444fd0b68ad6d2a4c62029fbd215bce91bd0d1')
    s=once(s,"def no_reparse(p):",'''def ordinary_profile(raw):
    profile_check(parse_ini(decode_ini(raw)[0]))
    return raw

def no_reparse(p):''')
    s=once(s,"keys=GATES+[(SECTION,'Enabled'),(SECTION,'SessionDirectory'),(SECTION,'SessionId'),('Vehicle','VIN'),('J2534_2','Enabled')]","keys=GATES+[('Vehicle','VIN'),('J2534_2','Enabled')]")
    a=s.index("    merged,directory=merge(raw,sys.stdin.read(4096)")
    b=s.index("    dll=extract_dll(package)",a)
    s=s[:a]+"    merged=ordinary_profile(raw)\n"+s[b:]
    write(root,p,s); p_hash=sha(s.encode())
    p='vc109/switch_provider.py'; s=read(root,p,'8f936059cc7483c992da5421dbf6d359939517318eb3e1f89fc36463f1e59ed6')
    s=once(s,"decode_ini, parse_ini, merge, SECTION, BUILD_SHA)","decode_ini, parse_ini, ordinary_profile, BUILD_SHA)")
    a=s.index("    ini=parse_ini(decode_ini(merged)[0])")
    b=s.index("    return {'old':str(old)",a)
    s=s[:a]+"    require(ordinary_profile(raw)==merged,'Candidate profile not byte-identical')\n"+s[b:]
    write(root,p,s); switch_hash=sha(s.encode())
    p='vc109/winui/ProviderFlow.cs'; s=read(root,p,'856dd86214c482f41ede99027d2f2a8722a58b8e9194aec5235f0b2a53d1c10e')
    s=once(s,'86EBA3912A0CCEE4A2EBD75B6D444FD0B68AD6D2A4C62029FBD215BCE91BD0D1',p_hash)
    s=once(s,'8F936059CC7483C992DA5421DBF6D359939517318EB3E1F89FC36463F1E59ED6',switch_hash)
    s=once(s,'string sessionId)','string sessionId, bool recover=false)')
    s=once(s,'"vc109-provider-"','"vc114-provider-"')
    s=once(s,'"vc109-rollback-"','"vc114-rollback-"')
    s=once(s,'''        if (Directory.Exists(Candidate)||File.Exists(Candidate)||File.Exists(Journal)||Directory.Exists(Journal)) throw new IOException("Candidate or journal already exists");
        if (!Restored()) throw new InvalidOperationException("Original registration not selected");''','''        if (recover)
        {
            if (!Active() || !File.Exists(Journal)) throw new IOException("Active candidate/journal not found");
        }
        else
        {
            if (Directory.Exists(Candidate)||File.Exists(Candidate)||File.Exists(Journal)||Directory.Exists(Journal)) throw new IOException("Candidate or journal already exists");
            if (!Restored()) throw new InvalidOperationException("Original registration not selected");
        }''')
    s=once(s,'    private static string LocalPath(string p)','''    public static bool IsOriginal(string directory)
    {
        try{return Same(ReadProvider(),Path.Combine(LocalPath(directory),Dll));}catch{return false;}
    }
    public static ProviderFlow? Recover(string python,string tools,string package)
    {
        string? selected=ReadProvider();
        if(selected is null)return null;
        string parent=LocalPath(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData));
        string? dir=Path.GetDirectoryName(selected);
        if(dir is null||!Same(Path.GetDirectoryName(dir),parent))return null;
        string name=Path.GetFileName(dir);
        const string prefix="vc114-provider-";
        if(!name.StartsWith(prefix,StringComparison.OrdinalIgnoreCase))return null;
        string id=name.Substring(prefix.Length);
        if(id.Length!=32||id.Any(c=>!Uri.IsHexDigit(c)))throw new IOException("Unknown candidate ID");
        string journal=LocalPath(Path.Combine(parent,"vc114-rollback-"+id+".json"));
        using var doc=System.Text.Json.JsonDocument.Parse(File.ReadAllText(journal));
        string old=doc.RootElement.GetProperty("old").GetString()??throw new IOException("Missing original path");
        string oldDir=Path.GetDirectoryName(old)??throw new IOException("Missing original directory");
        return new ProviderFlow(python,tools,package,oldDir,id,true);
    }
    private static string LocalPath(string p)''')
    s=once(s,'public async Task PrepareAsync(string section)','public async Task PrepareAsync()')
    s=once(s,'],section,false);','],null,false);')
    s=once(s,'_=await stdout;_=await stderr;\n        if(p.ExitCode!=0) throw new IOException("Profile helper failed: "+p.ExitCode+". Review the utility manually.");','''_=await stdout;var problem=await stderr;
        if(p.ExitCode!=0) throw new IOException("Profile helper failed: "+p.ExitCode+" "+problem.Trim());''')
    write(root,p,s)
    p='acceptance/prepare_all.py'; s=read(root,p,'0a418b77cced754b910ae674ad5e7f8f63b01af2c02be80e22c60f4cc8bbfc2b')
    s=once(s,"    window.write_bytes(result)","    window.write_bytes((ROOT/'vc109/winui/StaticWindow.cs').read_bytes())\n    for name in ('LivePublisher.cs','VehicleState.cs','StateTransport.cs','PrivateSession.cs'):\n        (live/name).unlink()\n    print('VC114_NO_SESSION_UI=STAGED')")
    write(root,p,s);write(root,'vc109/winui/StaticWindow.cs',WINDOW)
    # No external-state worker or IPC code in the native build; the guarded
    # source patch remains inert. Keep only the existing vehicle model + rotation.
    p='acceptance/build-only.ps1';s=read(root,p,'03cdf3ce8c16ebf9b5de910146c064268cb2bcd2a3453c18e64b7f0d4ba255f0')
    import re
    s,n=re.subn(r",'vc108n\\[^']+'","",s)
    if n!=9:raise ValueError("Unexpected external source count: "+str(n))
    s=once(s,"'/DVC108N_EXTERNAL_STATE','/DVC108N_DLL_WORKER',","")
    s=once(s,"@('kernel32.lib','bcrypt.lib','crypt32.lib')","@('kernel32.lib')")
    write(root,p,s)
    p='acceptance/audit_pe.py';s=(root/p).read_text(encoding="utf-8")
    s=once(s,"ALLOWED = {'kernel32.dll','bcrypt.dll','crypt32.dll'}","ALLOWED = {'kernel32.dll'}")
    write(root,p,s)
    # Exercise exact preservation of both encodings and explicit refusal of
    # profiles already containing external-state configuration.
    sys.path.insert(0,str(root/'vc109'))
    from prepare_profile import ordinary_profile, SECTION
    fixture=runpy.run_path(str(root/'vc109/check_profile.py'))['INI']
    for raw in (fixture.encode('latin1'),b'\xff\xfe'+fixture.encode('utf-16-le')):
        assert ordinary_profile(raw)==raw
    try: ordinary_profile((fixture+'['+SECTION+']\r\nEnabled=1\r\n').encode('latin1'))
    except ValueError: pass
    else: raise AssertionError("External session section was accepted")
    print("VC114_PROFILE_COPY=PASS 3/3")
    print("VC114_NO_SESSION_SOURCE=PASS")

if __name__=='__main__': patch(Path(sys.argv[1]))
