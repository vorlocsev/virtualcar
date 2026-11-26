using System.Security.Cryptography;

namespace VirtualCar.Core;

public sealed record BuiltInVehicle(string Id, string NameEn, string NameRu, string DescriptionEn,
    string DescriptionRu, string Vin, bool HistoricalDemo);

public static class BuiltInVehicles
{
    private static readonly IReadOnlyList<BuiltInVehicle> Catalog = Array.AsReadOnly(new BuiltInVehicle[]
    {
        new("p2", "Volvo P2", "Volvo P2",
            "Read-only platform demonstration. VIN replay unavailable.", "Демонстрация платформы. Воспроизведение VIN недоступно.",
            "YV1CZ0002A0000001", false),
        new("obd", "Generic diagnostic vehicle", "Универсальный автомобиль",
            "Synthetic engine and body-controller routes.", "Синтетические маршруты двигателя и кузовного блока.",
            "YV1CZ0002A0000001", false),
        new("p2-vin-demo", "Volvo P2 · VIN demo", "Volvo P2 · демо VIN",
            "Historical donor layout with synthetic VIN; not a verified XC90 V8 profile.",
            "Исторический демонстрационный образец с синтетическим VIN; не проверенный профиль XC90 V8.",
            "YV1CZ0002A0000001", true)
    });
    public static IReadOnlyList<BuiltInVehicle> All => Catalog;

    public static byte[] ReadProfile(string id)
    {
        if (!Catalog.Any(p => p.Id == id)) throw new ArgumentException("Unknown built-in vehicle.");
        using var stream = typeof(BuiltInVehicles).Assembly.GetManifestResourceStream("VirtualCar.Profiles." + id + ".ini")
            ?? throw new InvalidDataException("Embedded profile unavailable.");
        if (stream.Length is < 1 or > 1024 * 1024) throw new InvalidDataException();
        byte[] bytes = new byte[(int)stream.Length];
        stream.ReadExactly(bytes);
        return bytes;
    }

    public static string ProfileSha(string id) => Convert.ToHexString(SHA256.HashData(ReadProfile(id)));

    // The distribution contains a separate immutable native package per profile.
    // A changed profile must not be silently overwritten or presented as built-in.
    public static bool MatchesProfile(string id, ReadOnlySpan<byte> candidate) =>
        candidate.SequenceEqual(ReadProfile(id));

    public static string PackageLibrary(string root, string id)
    {
        if (!Path.IsPathFullyQualified(root) || !Catalog.Any(p => p.Id == id)) throw new InvalidDataException();
        return Path.Combine(Path.GetFullPath(root), "vehicle-data", id, "VirtualCarJ2534.dll");
    }

    public static bool IsNativePathSupported(string path) =>
        Path.IsPathFullyQualified(path) && path.Length < 240 &&
        path.All(c => c is >= ' ' and <= '~') && !path.StartsWith(@"\\", StringComparison.Ordinal);
}
