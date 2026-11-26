using System.Security.Principal;
using VirtualCar.DriverTool;

if (!OperatingSystem.IsWindows()) return 2;
// Read-only preflight is deliberately before the administrator check and
// mutex. Never load an installed DLL or print its path or fingerprint.
if (args.Length == 2 && args[0] == "inspect")
{
    if (args[1].Length != 64 || !args[1].All(Uri.IsHexDigit)) return 2;
    var info = DriverRegistration.Read();
    string match = "not_assessed";
    if (info.Status == DriverRegistration.State.Registered && info.Library is not null)
    {
        try
        {
            match = string.Equals(DriverRegistration.Fingerprint(info.Library), args[1],
                StringComparison.OrdinalIgnoreCase) ? "exact_bytes" : "different_bytes";
        }
        catch (Exception) { match = "unverifiable"; }
    }
    Console.WriteLine("VC090_REGISTRY_STATE=" + info.Status);
    Console.WriteLine("VC090_REGISTERED_DLL_MATCH=" + match);
    return 0;
}
using var identity = WindowsIdentity.GetCurrent();
if (!new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator)) return 3;
try
{
    using var mutex = new Mutex(false, @"Global\VirtualCar.DriverTool.Registry32.v1");
    bool entered = false;
    try
    {
        try { entered = mutex.WaitOne(TimeSpan.FromSeconds(5)); }
        catch (AbandonedMutexException) { entered = true; }
        if (!entered) return 4;
        if (args.Length == 3 && args[0] == "install" && Path.IsPathFullyQualified(args[1]))
            DriverRegistration.Install(args[1], args[2]);
        else if (args.Length == 3 && args[0] == "remove-canonical" && Path.IsPathFullyQualified(args[1]))
            DriverRegistration.Remove(args[1], canonicalOnly: true, expectedSha256: args[2]);
        else if (args.Length == 2 && args[0] == "remove" && Path.IsPathFullyQualified(args[1]))
            DriverRegistration.Remove(args[1]);
        else return 2;
        return 0;
    }
    finally { if (entered) mutex.ReleaseMutex(); }
}
catch (Exception) { return 5; }
