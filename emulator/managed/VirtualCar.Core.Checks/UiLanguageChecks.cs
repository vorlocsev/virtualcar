using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class UiLanguageChecks
{
    internal static (string Name, Func<Task> Test)[] All =>
    [
        ("VC076 missing file defaults to English", () => Check((store, path) =>
            Require(store.Load() == UiLanguage.English && !File.Exists(path)))),
        ("VC076 Russian survives reopening", () => Check((store, path) =>
            Require(store.TrySave(UiLanguage.Russian) && new UiLanguageSettings(path).Load() == UiLanguage.Russian))),
        ("VC076 English replaces Russian", () => Check((store, path) =>
            Require(store.TrySave(UiLanguage.Russian) && store.TrySave(UiLanguage.English) &&
                new UiLanguageSettings(path).Load() == UiLanguage.English &&
                File.ReadAllBytes(path).AsSpan().SequenceEqual("VC076-LANGUAGE-1\nEN\n"u8)))),
        ("VC076 malformed version and content fall back", () => Check((store, path) =>
        {
            foreach (string bad in new[] { "", "RU", "VC076-LANGUAGE-2\nRU\n", "VC076-LANGUAGE-1\nru\n",
                "VC076-LANGUAGE-1\nRU\nextra" })
            {
                File.WriteAllText(path, bad);
                Require(store.Load() == UiLanguage.English);
                Require(File.ReadAllText(path) == bad);
            }
        })),
        ("VC076 oversized content falls back", () => Check((store, path) =>
        {
            File.WriteAllBytes(path, new byte[4096]);
            Require(store.Load() == UiLanguage.English && new FileInfo(path).Length == 4096);
        })),
        ("VC076 invalid language cannot overwrite", () => Check((store, path) =>
        {
            Require(store.TrySave(UiLanguage.Russian));
            Require(!store.TrySave((UiLanguage)999) && store.Load() == UiLanguage.Russian);
        })),
        ("VC076 unavailable destination is nonfatal", () => Check((store, path) =>
        {
            Directory.CreateDirectory(path);
            Require(store.Load() == UiLanguage.English && !store.TrySave(UiLanguage.Russian));
            Require(Directory.Exists(path) && !Directory.EnumerateFiles(Path.GetDirectoryName(path)!).Any());
        })),
        ("VC076 repeated saves leave no temporary files", () => Check((store, path) =>
        {
            for (int i = 0; i < 12; i++)
                Require(store.TrySave(i % 2 == 0 ? UiLanguage.English : UiLanguage.Russian));
            Require(store.Load() == UiLanguage.Russian);
            Require(Directory.EnumerateFileSystemEntries(Path.GetDirectoryName(path)!).Single() == path);
        }))
    ];

    private static Task Check(Action<UiLanguageSettings, string> test)
    {
        string directory = Path.Combine(Path.GetTempPath(), "VirtualCar-VC076-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            string path = Path.Combine(directory, "language.v1");
            test(new UiLanguageSettings(path), path);
            return Task.CompletedTask;
        }
        finally { Directory.Delete(directory, recursive: true); }
    }

    private static void Require(bool ok)
    {
        if (!ok) throw new InvalidOperationException("Language settings check failed.");
    }
}
