using System.Security;

namespace VirtualCar.Core;

public enum UiLanguage { English, Russian }

// Only the UI language is stored. No profile, private paths or diagnostic data.
public sealed class UiLanguageSettings
{
    private readonly string _path;
    public UiLanguageSettings(string path)
    {
        if (!Path.IsPathFullyQualified(path)) throw new ArgumentException("Absolute path required.", nameof(path));
        _path = Path.GetFullPath(path);
    }

    public UiLanguage Load()
    {
        try
        {
            using var file = new FileStream(_path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            Span<byte> bytes = stackalloc byte[65];
            int length = file.ReadAtLeast(bytes, bytes.Length, throwIfEndOfStream: false);
            return bytes[..length].SequenceEqual("VC076-LANGUAGE-1\nRU\n"u8)
                ? UiLanguage.Russian : UiLanguage.English;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or SecurityException)
        {
            return UiLanguage.English;
        }
    }

    public bool TrySave(UiLanguage language)
    {
        if (language is not (UiLanguage.English or UiLanguage.Russian)) return false;
        var directory = Path.GetDirectoryName(_path)!;
        string? temporary = null;
        try
        {
            Directory.CreateDirectory(directory);
            string candidate = Path.Combine(directory, $".language-{Guid.NewGuid():N}.tmp");
            using (var stream = new FileStream(candidate, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                temporary = candidate;
                stream.Write(language == UiLanguage.Russian ? "VC076-LANGUAGE-1\nRU\n"u8 : "VC076-LANGUAGE-1\nEN\n"u8);
                stream.Flush(flushToDisk: true);
            }
            File.Move(temporary, _path, overwrite: true);
            return true;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or SecurityException)
        {
            return false;
        }
        finally
        {
            if (temporary is not null)
            {
                try { File.Delete(temporary); }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or SecurityException) { }
            }
        }
    }
}
