using System.Text;
using System.Text.Json;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class EquipmentReferenceChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC094D2 01 exact scoped compiler output", () => Run(Test01)),
        ("VC094D2 02 checksum and unchanged identity/tail", () => Run(Test02)),
        ("VC094D2 03 block warnings and topology review", () => Run(Test03)),
        ("VC094D2 04 independent matching digest", () => Run(Test04)),
        ("VC094D2 05 reject absent and wrong references", () => Run(Test05)),
        ("VC094D2 06 reject duplicate reference", () => Run(Test06)),
        ("VC094D2 07 detached copy and repeat", () => Run(Test07)),
        ("VC094D2 08 reject altered baseline and existing copy", () => Run(Test08))
    ];
    private static Task Run(Action a) { a(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
    private static void Reject(Action a)
    {
        try { a(); }
        catch (InvalidDataException) { return; }
        catch (InvalidOperationException) { return; }
        throw new Exception("Expected rejection");
    }
    private static byte[] Block()
    {
        byte[] b = new byte[142]; b[0]=0x8c; b[8]=2; b[33]=1; b[141]=0x23; b[1]=0x26; return b;
    }
    private static byte[] Ini(byte[] b) => Encoding.ASCII.GetBytes(
        "[Vehicle]\r\nVIN=LAB-ONLY\r\n[VC054_F106Lab]\r\nBlockHex=" +
        Convert.ToHexString(b).ToLowerInvariant() + "\r\nLayout=donor-142\r\nEnabled=1\r\n; end\r\n");
    private static ManagedEquipmentPreview Editor()
    {
        var b = Block(); int[] locked = [2,3,4,8,9,10,12,16,28,33,36,123];
        var rows = Enumerable.Range(2,128).Where(i=>i!=7).Select(i=>new
        {
            offset=i, baseline_code=b[i].ToString("X2"),
            choices=locked.Contains(i) ? Array.Empty<object>() :
                Enumerable.Range(1,5).Where(v=>v!=b[i]).Select(v=>(object)new {code=v.ToString("X2"),text="Lab value "+v}).ToArray()
        });
        return new(b, JsonSerializer.SerializeToUtf8Bytes(new {schema="vc094d-cem-options-v1",rows}));
    }
    private static Dictionary<int,string> Edit(int offset=60,string code="01") => new() {[offset]=code};
    private static byte[] Expected()
    {
        var b=Block(); b[60]=1; b[1]++; return Ini(b);
    }
    private static EquipmentReferences Ref(string? sha=null, bool duplicate=false)
    {
        var entry=new {offset=60,code="01",ini_sha256=sha??NativeEcmScenarioApply.Digest(Expected())};
        return new(JsonSerializer.SerializeToUtf8Bytes(new {schema="vc094d2-single-edit-references-v1",
            cases=duplicate ? new[]{entry,entry} : new[]{entry}}));
    }
    private static void Test01()
    {
        var before=Ini(Block()); var result=Editor().CompileReviewed(before,Edit());
        Require(result.SequenceEqual(Expected()) && before.SequenceEqual(Ini(Block())));
    }
    private static void Test02()
    {
        var b=ManagedEquipmentPreview.ExtractBlock(Editor().CompileReviewed(Ini(Block()),Edit()));
        Require(Enumerable.Range(0,142).Where(i=>b[i]!=Block()[i]).SequenceEqual(new[]{1,60}));
    }
    private static void Test03()
    {
        var e=Editor(); var b=Ini(Block());
        Reject(()=>e.CompileReviewed(b,Edit(23,"03")));
        Reject(()=>e.CompileReviewed(b,Edit(75,"04")));
        Reject(()=>e.CompileReviewed(b,Edit(13,"01")));
    }
    private static void Test04()
    {
        var refs=Ref(); Require(refs.Count==1 && refs.Supports(Edit()));
        refs.VerifyAll(Editor(),Ini(Block()));
        Require(refs.Compile(Editor(),Ini(Block()),Edit()).SequenceEqual(Expected()));
    }
    private static void Test05()
    {
        Require(!Ref().Supports(Edit(61)));
        Reject(()=>Ref().Compile(Editor(),Ini(Block()),Edit(61)));
        Reject(()=>Ref(new string('0',64)).VerifyAll(Editor(),Ini(Block())));
        Require(!Ref().Supports(new Dictionary<int,string>{{60,"01"},{61,"01"}}));
    }
    private static void Test06()=>Reject(()=>Ref(duplicate:true));
    private static void WithRoot(Action<string,byte[]> a)
    {
        string root=Path.Combine(Path.GetTempPath(),"VC094D2-"+Guid.NewGuid().ToString("N"));
        var folder=LocalVehicleData.Folder(root); Directory.CreateDirectory(folder);
        byte[] baseline=Ini(Block()); File.WriteAllBytes(Path.Combine(folder,"virtualcar.ini"),baseline);
        try { a(root,baseline); }
        finally { Directory.Delete(root,true); }
    }
    private static void Test07()=>WithRoot((root,baseline)=>
    {
        var refs=Ref(); var editor=Editor();
        string path=refs.Prepare(root,editor,baseline,Edit());
        Require(File.ReadAllBytes(path).SequenceEqual(Expected()));
        Require(refs.Prepare(root,editor,baseline,Edit())==path);
        Require(File.ReadAllBytes(Path.Combine(LocalVehicleData.Folder(root),"virtualcar.ini")).SequenceEqual(baseline));
    });
    private static void Test08()=>WithRoot((root,baseline)=>
    {
        var refs=Ref(); var editor=Editor();
        string path=refs.Prepare(root,editor,baseline,Edit());
        File.AppendAllText(path,";changed");
        var changed=File.ReadAllBytes(path);
        Reject(()=>refs.Prepare(root,editor,baseline,Edit()));
        Require(File.ReadAllBytes(path).SequenceEqual(changed));
        File.AppendAllText(Path.Combine(LocalVehicleData.Folder(root),"virtualcar.ini"),";changed");
        Reject(()=>refs.Prepare(root,editor,baseline,Edit()));
    });
}
