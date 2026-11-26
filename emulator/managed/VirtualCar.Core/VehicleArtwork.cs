using System.Text;

namespace VirtualCar.Core;

public sealed record VehicleArtworkInfo(string Key, string CaptionEn, string CaptionRu,
    string Author, int Width, int Height);

public static class VehicleArtwork
{
    // These are reference photographs, not verified images of the owner's car.
    private static readonly VehicleArtworkInfo V8 = new("xc90-v8",
        "XC90 V8 reference · 2006–2008 generation", "XC90 V8 · пример модели 2006–2008",
        "OSX", 960, 538);
    private static readonly VehicleArtworkInfo P2 = new("p2-reference",
        "P2 platform illustration · XC90 photographed in 2009",
        "Пример платформы P2 · XC90, фото 2009 года", "M 93", 960, 701);

    public static VehicleArtworkInfo? ForVehicle(string id) => id switch
    {
        LocalVehicleData.Id => V8,
        "p2" or "p2-vin-demo" => P2,
        _ => null
    };

    public static byte[] Load(string root, string vehicleId)
    {
        if (!Path.IsPathFullyQualified(root)) throw new InvalidDataException();
        var info = ForVehicle(vehicleId) ?? throw new InvalidDataException("No model artwork.");
        string folder = Path.Combine(Path.GetFullPath(root), "artwork");
        var raw = VehicleStatePackages.ReadFile(Path.Combine(folder, info.Key + ".jpg"), 1024 * 1024);
        string sha = Encoding.ASCII.GetString(VehicleStatePackages.ReadFile(
            Path.Combine(folder, info.Key + ".sha256"), 128)).Trim();
        if (!AcceptanceReportReader.IsHash(sha, 64) ||
            !NativeEcmScenarioApply.Digest(raw).Equals(sha, StringComparison.OrdinalIgnoreCase) ||
            !HasExpectedFrame(raw, info.Width, info.Height))
            throw new InvalidDataException("Artwork failed local integrity checks.");
        return raw;
    }

    // Bounded pre-decode JPEG header check. The platform decoder validates the actual image.
    public static bool HasExpectedFrame(ReadOnlySpan<byte> bytes, int width, int height)
    {
        if (bytes.Length < 16 || bytes.Length > 1024 * 1024 ||
            width is < 1 or > 960 || height is < 1 or > 960 ||
            bytes[0] != 0xff || bytes[1] != 0xd8 || bytes[^2] != 0xff || bytes[^1] != 0xd9)
            return false;
        int offset = 2;
        bool found = false;
        while (offset < bytes.Length - 2)
        {
            if (bytes[offset++] != 0xff) return false;
            while (offset < bytes.Length && bytes[offset] == 0xff) offset++;
            if (offset >= bytes.Length) return false;
            byte marker = bytes[offset++];
            if (marker is 0x00 or 0x01 or >= 0xd0 and <= 0xd9) return false;
            if (offset + 2 > bytes.Length) return false;
            int length = (bytes[offset] << 8) | bytes[offset + 1];
            if (length < 2 || length > bytes.Length - offset) return false;
            if (marker is 0xc0 or 0xc1 or 0xc2)
            {
                if (found || length < 11 || bytes[offset + 2] != 8) return false;
                int h = (bytes[offset + 3] << 8) | bytes[offset + 4];
                int w = (bytes[offset + 5] << 8) | bytes[offset + 6];
                int components = bytes[offset + 7];
                if (w != width || h != height || components != 3 || length != 8 + 3 * components)
                    return false;
                found = true;
            }
            else if (marker == 0xda)
                return found && length >= 6 && offset + length < bytes.Length - 2;
            else if (marker is >= 0xc0 and <= 0xcf && marker is not (0xc4 or 0xcc))
                return false;
            offset += length;
        }
        return false;
    }
}
