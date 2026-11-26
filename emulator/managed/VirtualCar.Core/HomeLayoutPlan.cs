namespace VirtualCar.Core;

// Dimensions are effective pixels (DIP), not physical display pixels.
public readonly record struct HomeLayoutPlan(bool TwoColumns, double LeftWeight, double RightWeight, double Gap)
{
    public const double WideThreshold = 880;
    public static HomeLayoutPlan ForWidth(double width, bool hasDetails = true) =>
        hasDetails && double.IsFinite(width) && width >= WideThreshold
            ? new(true, 0.44, 0.56, 16)
            : new(false, 1, 0, 0);
}

public enum HomeRegistration { Absent, Registered, Review }
public enum HomeConnectionState { Ready, Unavailable, Owned, Other, Review, Recovery }

public readonly record struct HomeConnectionPlan(HomeConnectionState State, bool CanEnable, bool CanDisable)
{
    public static HomeConnectionPlan Create(HomeRegistration registration, bool validCandidate, bool owned, bool busy, bool recoverable = false)
    {
        var state = registration switch
        {
            HomeRegistration.Absent => validCandidate ? HomeConnectionState.Ready : HomeConnectionState.Unavailable,
            HomeRegistration.Registered => validCandidate && owned ? HomeConnectionState.Owned :
                recoverable ? HomeConnectionState.Recovery : HomeConnectionState.Other,
            _ => HomeConnectionState.Review
        };
        return new(state, !busy && state == HomeConnectionState.Ready, !busy && state is (HomeConnectionState.Owned or HomeConnectionState.Recovery));
    }
}
