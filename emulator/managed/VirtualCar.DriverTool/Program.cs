using System.Security.Principal;
using VirtualCar.DriverTool;

if (!OperatingSystem.IsWindows()) return 2;
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
        else if (args.Length == 2 && args[0] == "remove" && Path.IsPathFullyQualified(args[1]))
            DriverRegistration.Remove(args[1]);
        else return 2;
        return 0;
    }
    finally { if (entered) mutex.ReleaseMutex(); }
}
catch (Exception) { return 5; }
