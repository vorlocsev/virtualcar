using System.Text;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class VehicleArtworkChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC094E 01 map known XC90 V8 reference", () => Run(Test01)),
        ("VC094E 02 distinguish platform examples from exact models", () => Run(Test02)),
        ("VC094E 03 no misleading generic OBD photograph", () => Run(Test03)),
        ("VC094E 04 bounded JPEG header and dimensions", () => Run(Test04)),
        ("VC094E 05 reject invalid JPEG header or oversized input", () => Run(Test05)),
        ("VC094E 06 load matching packaged bytes", () => Run(Test06)),
        ("VC094E 07 reject modified artwork and missing hash", () => Run(Test07)),
        ("VC094E 08 reject missing artwork and arbitrary profile", () => Run(Test08))
    ];
    private static Task Run(Action action) { action(); return Task.CompletedTask; }
    private static void Require(bool ok) { if (!ok) throw new InvalidOperationException(); }
    private static void Reject(Action action)
    {
        try { action(); }
        catch (InvalidDataException) { return; }
        catch (IOException) { return; }
        throw new InvalidOperationException("Expected rejection");
    }

    // Synthetic header fixture only: not a decodable photograph.
    private static byte[] Header(int width, int height) =>
    [
        0xff,0xd8,0xff,0xc0,0x00,0x11,0x08,
        (byte)(height>>8),(byte)height,(byte)(width>>8),(byte)width,3,
        1,0x11,0,2,0x11,0,3,0x11,0,
        0xff,0xda,0x00,0x0c,3,1,0,2,0,3,0,0,0x3f,0,
        1,0xff,0xd9
    ];
    private static void Test01()
    {
        var v=VehicleArtwork.ForVehicle(LocalVehicleData.Id);
        Require(v is {Key:"xc90-v8",Author:"OSX",Width:960,Height:538});
        Require(v!.CaptionEn.Contains("2006–2008",StringComparison.Ordinal));
    }
    private static void Test02()
    {
        var p=VehicleArtwork.ForVehicle("p2");
        Require(p is {Key:"p2-reference",Author:"M 93",Width:960,Height:701});
        Require(p==VehicleArtwork.ForVehicle("p2-vin-demo"));
        Require(p!=VehicleArtwork.ForVehicle(LocalVehicleData.Id));
    }
    private static void Test03()
    {
        Require(VehicleArtwork.ForVehicle("obd") is null);
        Require(VehicleArtwork.ForVehicle("../xc90-v8") is null);
        Require(VehicleArtwork.ForVehicle("XC90") is null);
    }
    private static void Test04()
    {
        Require(VehicleArtwork.HasExpectedFrame(Header(960,538),960,538));
        Require(VehicleArtwork.HasExpectedFrame(Header(960,701),960,701));
        Require(!VehicleArtwork.HasExpectedFrame(Header(960,538),960,701));
        Require(!VehicleArtwork.HasExpectedFrame(Header(4000,3000),960,538));
    }
    private static void Test05()
    {
        Require(!VehicleArtwork.HasExpectedFrame(new byte[1024*1024+1],960,538));
        byte[] raw=Header(960,538); raw[5]=0xff;
        Require(!VehicleArtwork.HasExpectedFrame(raw,960,538));
        Require(!VehicleArtwork.HasExpectedFrame(Header(960,538)[..^2],960,538));
        Require(!VehicleArtwork.HasExpectedFrame("not jpeg"u8,960,538));
    }
    private static void WithRoot(Action<string,string,byte[]> action)
    {
        string root=Path.Combine(Path.GetTempPath(),"VC094E-"+Guid.NewGuid().ToString("N"));
        string folder=Path.Combine(root,"artwork"); Directory.CreateDirectory(folder);
        byte[] bytes=Header(960,538); string path=Path.Combine(folder,"xc90-v8.jpg");
        File.WriteAllBytes(path,bytes);
        File.WriteAllText(Path.Combine(folder,"xc90-v8.sha256"),NativeEcmScenarioApply.Digest(bytes),Encoding.ASCII);
        try { action(root,path,bytes); }
        finally { Directory.Delete(root,true); }
    }
    private static void Test06()=>WithRoot((root,path,bytes)=>
    {
        Require(VehicleArtwork.Load(root,LocalVehicleData.Id).SequenceEqual(bytes));
        Require(File.ReadAllBytes(path).SequenceEqual(bytes));
    });
    private static void Test07()=>WithRoot((root,path,bytes)=>
    {
        bytes[35]^=1; File.WriteAllBytes(path,bytes);
        Reject(()=>VehicleArtwork.Load(root,LocalVehicleData.Id));
        File.Delete(Path.Combine(root,"artwork","xc90-v8.sha256"));
        Reject(()=>VehicleArtwork.Load(root,LocalVehicleData.Id));
    });
    private static void Test08()=>WithRoot((root,path,bytes)=>
    {
        Reject(()=>VehicleArtwork.Load(root,"obd"));
        Reject(()=>VehicleArtwork.Load(root,"p2"));
        Reject(()=>VehicleArtwork.Load("relative",LocalVehicleData.Id));
        Reject(()=>VehicleArtwork.Load(root,"../xc90-v8"));
    });
}
