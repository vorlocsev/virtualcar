namespace VirtualCar.Core;

// Dimensions are effective pixels (DIP), not physical display pixels.
public readonly record struct HomeLayoutPlan(bool TwoColumns, double LeftWeight, double RightWeight, double Gap)
{
    public const double WideThreshold = 880;
    public static HomeLayoutPlan ForWidth(double width) =>
        double.IsFinite(width) && width >= WideThreshold
            ? new(true, 0.44, 0.56, 16)
            : new(false, 1, 0, 0);
}
