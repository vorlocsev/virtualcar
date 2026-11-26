using System.Text;
using System.Text.Json;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class ManagedEquipmentChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC094D 01 baseline coverage and immutable preview", () => Run(Test01)),
        ("VC094D 02 protected and unlisted choices rejected", () => Run(Test02)),
        ("VC094D 03 ten existing blocking rules", () => Run(Test03)),
        ("VC094D 04 six existing warning rules", () => Run(Test04)),
        ("VC094D 05 topology review independent of rules", () => Run(Test05)),
        ("VC094D 06 option integrity and original labels", () => Run(Test06)),
        ("VC094D 07 missing and duplicate rows rejected", () => Run(Test07)),
        ("VC094D 08 extract exact block without changing INI", () => Run(Test08))
    ];
    private static readonly HashSet<int> Locked = [2,3,4,8,9,10,12,16,28,33,36,123];
    private static Task Run(Action a) { a(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
    private static void Reject(Action a)
    {
        try { a(); }
        catch (InvalidDataException) { return; }
        catch (JsonException) { return; }
        throw new InvalidOperationException("Expected rejection");
    }
    private static byte[] Baseline()
    {
        var b = new byte[142]; b[0]=0x8c; b[8]=2; b[33]=1; b[1]=3; return b;
    }
    private static Dictionary<string, object>[] Rows(byte[] b) =>
        Enumerable.Range(2,128).Where(i => i != 7).Select(i => new Dictionary<string, object>
        {
            ["offset"] = i, ["baseline_code"] = b[i].ToString("X2"),
            ["choices"] = Locked.Contains(i) ? Array.Empty<object>() :
                Enumerable.Range(1,254).Where(v => v != b[i]).Select(v => (object)new { code = v.ToString("X2"), text = "Original " + v }).ToArray()
        }).ToArray();
    private static byte[] Encode(object rows) => JsonSerializer.SerializeToUtf8Bytes(new { schema = "vc094d-cem-options-v1", rows });
    private static ManagedEquipmentPreview Editor()
    {
        byte[] b = Baseline(); return new(b, Encode(Rows(b)));
    }
    private static Dictionary<int,string> Edits(params (int Offset, int Value)[] values) =>
        values.ToDictionary(x => x.Offset, x => x.Value.ToString("X2"));
    private static void Test01()
    {
        byte[] b = Baseline(); var editor = new ManagedEquipmentPreview(b, Encode(Rows(b)));
        Require(editor.Options.Count == 127 && editor.Preview(Edits()).Status == "pass");
        var result = editor.Preview(Edits((60,1)));
        Require(result.ChangedCount == 1 && b.SequenceEqual(Baseline()));
        Require(editor.Preview(Edits()).ChangedCount == 0);
    }
    private static void Test02()
    {
        var editor = Editor();
        foreach (var edit in new[] { Edits((8,1)), Edits((7,1)), Edits((60,255)), Edits((60,0)), Edits((130,1)) })
            Reject(() => editor.Preview(edit));
    }
    private static void Test03()
    {
        var editor = Editor();
        foreach (var (id, edits) in new (string, Dictionary<int,string>)[]
        {
            ("PETROL_HEATER", Edits((23,3))), ("AUTO_STARTBLOCK", Edits((71,2))),
            ("AC_HEATER_ONLY", Edits((20,2),(21,1))), ("AC_REAR", Edits((20,1),(105,2))),
            ("AC_CLIMATE", Edits((20,1),(21,2))), ("PARK_AEM", Edits((64,2),(76,1))),
            ("AIRBAG_SWITCH", Edits((73,1),(113,2))), ("OWS_CAL", Edits((91,1))),
            ("TPMS_LOAD", Edits((79,1))), ("XENON_ADJUST", Edits((81,0x11)))
        })
        {
            var result = editor.Preview(edits); Require(result.Errors.Contains(id) && result.Status == "blocked");
        }
    }
    private static void Test04()
    {
        var editor = Editor();
        foreach (var (id, edits) in new (string, Dictionary<int,string>)[]
        {
            ("AQS_FILTER", Edits((75,4))), ("ALARM_OPTIONS", Edits((46,1))),
            ("HEATER_CALL", Edits((23,1),(25,1))), ("RTI_CONTROL", Edits((43,1))),
            ("AUDIO_AMP", Edits((45,1))), ("AUDIO_SYSTEM", Edits((45,0x59),(107,1)))
        })
        {
            var result = editor.Preview(edits); Require(result.Warnings.Contains(id) && result.Status == "review");
        }
    }
    private static void Test05()
    {
        var editor = Editor();
        Require(editor.Preview(Edits((13,1))).TopologyReview && editor.Preview(Edits((13,1))).Status == "review");
        Require(!editor.Preview(Edits((60,1))).TopologyReview);
    }
    private static void Test06()
    {
        byte[] b = Baseline(); var rows = Rows(b);
        var editor = new ManagedEquipmentPreview(b, Encode(rows));
        Require(editor.Options[60].Choices.First().Text == "Original 1");
        rows.First(x => (int)x["offset"] == 60)["baseline_code"] = "FF";
        Reject(() => new ManagedEquipmentPreview(b, Encode(rows)));
        rows = Rows(b); rows.First(x => (int)x["offset"] == 8)["choices"] = new[] { new { code = "01", text = "bad" } };
        Reject(() => new ManagedEquipmentPreview(b, Encode(rows)));
    }
    private static void Test07()
    {
        byte[] b = Baseline(); var rows = Rows(b);
        Reject(() => new ManagedEquipmentPreview(b, Encode(rows.Take(126))));
        rows[1] = rows[0]; Reject(() => new ManagedEquipmentPreview(b, Encode(rows)));
    }
    private static void Test08()
    {
        byte[] b = Baseline();
        string section = "[VC054_F106Lab]\r\nBlockHex=" + Convert.ToHexString(b).ToLowerInvariant() + "\r\nLayout=donor-142\r\nEnabled=1\r\n";
        byte[] ini = Encoding.ASCII.GetBytes(section);
        Require(ManagedEquipmentPreview.ExtractBlock(ini).SequenceEqual(b));
        Reject(() => ManagedEquipmentPreview.ExtractBlock(Encoding.ASCII.GetBytes(section + section)));
        Require(Encoding.ASCII.GetString(ini) == section);
    }
}
