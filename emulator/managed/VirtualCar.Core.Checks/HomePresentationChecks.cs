using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class HomePresentationChecks
{
    public static (string Name, Func<Task> Test)[] All =>
    [
        ("VC094F 01 wide layout uses two columns", () => Run(() =>
        {
            var p = HomeLayoutPlan.ForWidth(1100);
            Require(p.TwoColumns && p.Gap == 16 && Math.Abs(p.LeftWeight + p.RightWeight - 1) < 0.0001);
        })),
        ("VC094F 02 narrow layout and exact DIP breakpoint", () => Run(() =>
        {
            Require(!HomeLayoutPlan.ForWidth(879.99).TwoColumns);
            Require(HomeLayoutPlan.ForWidth(880).TwoColumns);
            var narrow = HomeLayoutPlan.ForWidth(640);
            Require(narrow.LeftWeight == 1 && narrow.RightWeight == 0 && narrow.Gap == 0);
        })),
        ("VC094F 03 missing details never leave empty column", () => Run(() =>
        {
            Require(!HomeLayoutPlan.ForWidth(1200, false).TwoColumns);
            Require(HomeLayoutPlan.ForWidth(1200, true).TwoColumns);
        })),
        ("VC094F 04 invalid initial width stays compact", () => Run(() =>
        {
            foreach (double width in new[] { 0.0, -1.0, double.NaN, double.PositiveInfinity, double.NegativeInfinity })
                Require(!HomeLayoutPlan.ForWidth(width).TwoColumns);
        })),
        ("VC094F 05 absent registration and valid candidate", () => Run(() =>
        {
            Require(HomeConnectionPlan.Create(HomeRegistration.Absent, true, false, false) ==
                new HomeConnectionPlan(HomeConnectionState.Ready, true, false));
            Require(HomeConnectionPlan.Create(HomeRegistration.Absent, false, false, false) ==
                new HomeConnectionPlan(HomeConnectionState.Unavailable, false, false));
        })),
        ("VC094F 06 owned valid registration permits disable only", () => Run(() =>
        {
            Require(HomeConnectionPlan.Create(HomeRegistration.Registered, true, true, false) ==
                new HomeConnectionPlan(HomeConnectionState.Owned, false, true));
        })),
        ("VC094F 07 other or invalid registration does not permit mutation", () => Run(() =>
        {
            Require(HomeConnectionPlan.Create(HomeRegistration.Registered, true, false, false) ==
                new HomeConnectionPlan(HomeConnectionState.Other, false, false));
            Require(HomeConnectionPlan.Create(HomeRegistration.Registered, false, true, false) ==
                new HomeConnectionPlan(HomeConnectionState.Other, false, false));
            Require(HomeConnectionPlan.Create(HomeRegistration.Review, true, true, false) ==
                new HomeConnectionPlan(HomeConnectionState.Review, false, false));
        })),
        ("VC094F 08 busy never permits an adapter action", () => Run(() =>
        {
            foreach (var registration in Enum.GetValues<HomeRegistration>())
                foreach (bool candidate in new[] { true, false })
                    foreach (bool owned in new[] { true, false })
                    {
                        var plan = HomeConnectionPlan.Create(registration, candidate, owned, true);
                        Require(!plan.CanEnable && !plan.CanDisable);
                    }
        })),
        ("VC095D 01 recognize each embedded provider path", () => Run(() =>
        {
            string root = Path.GetFullPath(Path.Combine(Path.GetTempPath(), "VC095D"));
            foreach (var v in BuiltInVehicles.All)
            {
                var path = BuiltInVehicles.PackageLibrary(root, v.Id);
                var found = HomeProviderPaths.Recognize(root, path, []);
                Require(found is not null && found.VehicleId == v.Id && found.Library == path &&
                    found.State.IsOriginal && found.Variant is null);
            }
        })),
        ("VC095D 02 recognize original and derived state paths", () => Run(() =>
        {
            string root = Path.GetFullPath(Path.Combine(Path.GetTempPath(), "VC095D"));
            foreach (var state in new[] { VehicleStateChoice.Original,
                new VehicleStateChoice(NativeIgnitionSelection.PositionIICandidate, EcmScenario.WarmIdle),
                new VehicleStateChoice(null, EcmScenario.Dynamic) })
            {
                string path = Path.Combine(VehicleStatePackages.Folder(root,state),"VirtualCarJ2534.dll");
                var found = HomeProviderPaths.Recognize(root,path,[]);
                Require(found is not null && found.VehicleId == LocalVehicleData.Id && found.State == state && found.Variant is null);
            }
        })),
        ("VC095D 03 recognize only catalogued equipment variants", () => Run(() =>
        {
            string root = Path.GetFullPath(Path.Combine(Path.GetTempPath(), "VC095D"));
            var variant = new EquipmentVariant(60,"01",new string('a',64));
            string path = EquipmentVariantPackages.Library(root,variant);
            Require(HomeProviderPaths.Recognize(root,path,[variant])?.Variant == variant);
            Require(HomeProviderPaths.Recognize(root,path,[]) is null);
        })),
        ("VC095D 04 reject unknown or noncanonical provider paths", () => Run(() =>
        {
            string root = Path.GetFullPath(Path.Combine(Path.GetTempPath(), "VC095D"));
            foreach (string? path in new string?[] { null, "VirtualCarJ2534.dll",
                Path.Combine(root,"unrelated","VirtualCarJ2534.dll"),
                Path.Combine(root,"vehicle-data","p2","..","p2","VirtualCarJ2534.dll"),
                Path.Combine(root,"vehicle-data","xc90-v8-2009-states","i99-e99","VirtualCarJ2534.dll") })
                Require(HomeProviderPaths.Recognize(root,path,[]) is null);
        })),
        ("VC095D 05 recoverable registration permits disconnect only", () => Run(() =>
        {
            Require(HomeConnectionPlan.Create(HomeRegistration.Registered,false,false,false,true) ==
                new HomeConnectionPlan(HomeConnectionState.Recovery,false,true));
            Require(HomeConnectionPlan.Create(HomeRegistration.Registered,true,true,false,true) ==
                new HomeConnectionPlan(HomeConnectionState.Owned,false,true));
        })),
        ("VC095D 06 unknown registration still blocks both actions", () => Run(() =>
        {
            Require(HomeConnectionPlan.Create(HomeRegistration.Registered,false,false,false,false) ==
                new HomeConnectionPlan(HomeConnectionState.Other,false,false));
        })),
        ("VC095D 07 recovery cannot bypass absent or conflict state", () => Run(() =>
        {
            Require(HomeConnectionPlan.Create(HomeRegistration.Absent,false,false,false,true) ==
                new HomeConnectionPlan(HomeConnectionState.Unavailable,false,false));
            Require(HomeConnectionPlan.Create(HomeRegistration.Review,true,true,false,true) ==
                new HomeConnectionPlan(HomeConnectionState.Review,false,false));
        })),
        ("VC095D 08 busy blocks recovery", () => Run(() =>
        {
            Require(HomeConnectionPlan.Create(HomeRegistration.Registered,false,false,true,true) ==
                new HomeConnectionPlan(HomeConnectionState.Recovery,false,false));
        }))
    ];
    private static Task Run(Action action) { action(); return Task.CompletedTask; }
    private static void Require(bool value)
    {
        if (!value) throw new InvalidOperationException("Unexpected presentation state.");
    }
}
