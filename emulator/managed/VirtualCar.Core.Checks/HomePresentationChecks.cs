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
        }))
    ];
    private static Task Run(Action action) { action(); return Task.CompletedTask; }
    private static void Require(bool value)
    {
        if (!value) throw new InvalidOperationException("Unexpected presentation state.");
    }
}
