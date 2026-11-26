namespace VirtualCar.Core;

public sealed record HomeProviderLocation(string VehicleId, string Library,
    VehicleStateChoice State, EquipmentVariant? Variant);

/// <summary>Exact paths belonging to this package; path recognition alone is not DLL authentication.</summary>
public static class HomeProviderPaths
{
    public static HomeProviderLocation? Recognize(string root, string? registeredPath,
        IReadOnlyList<EquipmentVariant> knownVariants)
    {
        if (registeredPath is null || !BuiltInVehicles.IsNativePathSupported(registeredPath)) return null;
        bool Match(string path) => string.Equals(registeredPath, path, StringComparison.OrdinalIgnoreCase);
        foreach (var vehicle in BuiltInVehicles.All)
        {
            string path = BuiltInVehicles.PackageLibrary(root, vehicle.Id);
            if (Match(path)) return new(vehicle.Id, path, VehicleStateChoice.Original, null);
        }
        // Recognize only deterministic state paths for removal/review; this
        // does not grant eligibility to activate a state on this baseline.
        var ignition = new NativeIgnitionSelection?[] { null }.Concat(
            Enum.GetValues<NativeIgnitionSelection>().Select(x => (NativeIgnitionSelection?)x));
        var engines = new EcmScenario?[] { null }.Concat(
            Enum.GetValues<EcmScenario>().Select(x => (EcmScenario?)x));
        foreach (var i in ignition)
            foreach (var e in engines)
            {
                var state = new VehicleStateChoice(i,e);
                string path = Path.Combine(VehicleStatePackages.Folder(root,state), "VirtualCarJ2534.dll");
                if (Match(path)) return new(LocalVehicleData.Id,path,state,null);
            }
        foreach (var variant in knownVariants)
        {
            string path = EquipmentVariantPackages.Library(root,variant);
            if (Match(path)) return new(LocalVehicleData.Id,path,VehicleStateChoice.Original,variant);
        }
        return null;
    }
}
