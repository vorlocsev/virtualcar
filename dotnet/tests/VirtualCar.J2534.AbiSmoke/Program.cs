using System.Runtime.InteropServices;

if (args.Length != 1)
    throw new ArgumentException("Expected a private ABI-probe DLL path.");

string dll = Path.GetFullPath(args[0]);
if (!File.Exists(dll))
    throw new FileNotFoundException("ABI-probe DLL was not built.");

string[] names =
[
    "PassThruOpen", "PassThruClose", "PassThruConnect", "PassThruDisconnect",
    "PassThruReadMsgs", "PassThruWriteMsgs", "PassThruStartPeriodicMsg",
    "PassThruStopPeriodicMsg", "PassThruStartMsgFilter", "PassThruStopMsgFilter",
    "PassThruSetProgrammingVoltage", "PassThruReadVersion",
    "PassThruGetLastError", "PassThruIoctl"
];

// Native AOT native libraries do not support FreeLibrary. Deliberately
// never unload; this whole test process exits immediately after probing.
nint module = NativeLibrary.Load(dll);
foreach (string name in names)
{
    if (!NativeLibrary.TryGetExport(module, name, out nint fn) || fn == 0)
        throw new Exception("Missing undecorated J2534 native export: " + name);
}

unsafe
{
    var open = (delegate* unmanaged[Stdcall]<void*, uint*, uint>)
        NativeLibrary.GetExport(module, "PassThruOpen");
    uint id = 123;
    uint result = open(null, &id);
    if (result != 1 || id != 0)
        throw new Exception("ABI probe must reject unsupported Open and zero the handle.");

    var connect = (delegate* unmanaged[Stdcall]<uint, uint, uint, uint, uint*, uint>)
        NativeLibrary.GetExport(module, "PassThruConnect");
    uint channel = 123;
    result = connect(0, 5, 0, 500000, &channel);
    if (result != 1 || channel != 0)
        throw new Exception("ABI probe must reject unsupported Connect and zero the channel.");
}

Console.WriteLine($"PASS native J2534 ABI probe: {names.Length} exports, {IntPtr.Size * 8}-bit loader, no diagnostic TX.");
