using System.Buffers.Binary;
using System.Globalization;
using System.Text;

namespace VirtualCar.Core;

public enum NativeTraceDirection { Tx, Rx }

public sealed record NativeTraceRow(uint Pid, string Host, NativeTraceDirection Direction,
    uint? Channel, uint? Protocol, uint? Flags, uint? Baud, uint? TimeUs, uint? CanId,
    string DataHex, bool PossibleTruncation);

public sealed record NativeTraceSnapshot(IReadOnlyList<NativeTraceRow> Rows, bool TailOnly);

/// <summary>Bounded log snapshot, not a wire capture. Only application TX and delivered RX.</summary>
public static class NativeCanTrace
{
    public const int MaxBytes = 512 * 1024;
    public const int MaxRows = 500;
    // Existing native DLL filename; not a user-facing adapter name.
    public const string LegacyLogFile = "SectorVVirtualCar.log";
    private const string TxContext = "TX context channel/protocol/flags/baud/time-us (BE)";
    private const string RxContext = "RX context channel/protocol/status/baud/time-us (BE)";
    private const string TxMessage = "TX (app request)";
    private const string RxMessage = "PassThruReadMsgs -> delivered";
    private sealed record Context(NativeTraceDirection Direction, uint Channel, uint Protocol,
        uint Flags, uint Baud, uint TimeUs);

    public static NativeTraceSnapshot ReadFile(string path)
    {
        if (!Path.IsPathFullyQualified(path) || !Path.GetExtension(path).Equals(".log", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Explicit local log required.");
        string full = Path.GetFullPath(path);
        if (OperatingSystem.IsWindows() && (full.StartsWith(@"\\", StringComparison.Ordinal) ||
            new DriveInfo(Path.GetPathRoot(full)!).DriveType != DriveType.Fixed))
            throw new InvalidDataException("Local fixed drive required.");
        for (FileSystemInfo? item = new FileInfo(full); item is not null;
            item = item is FileInfo file ? file.Directory : ((DirectoryInfo)item).Parent)
            if ((item.Attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Reparse point not allowed.");
        using var stream = File.Open(full, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        long length = stream.Length;
        int size = (int)Math.Min(length, MaxBytes);
        stream.Position = length - size;
        byte[] bytes = new byte[size];
        int read = stream.ReadAtLeast(bytes, size, false);
        if (read != size) throw new IOException("Log changed while reading.");
        return Parse(bytes, length > size);
    }

    public static NativeTraceSnapshot Parse(ReadOnlySpan<byte> bytes, bool tailOnly = false)
    {
        if (bytes.Length > MaxBytes) throw new InvalidDataException("Trace snapshot too large.");
        var rows = new Queue<NativeTraceRow>();
        var pending = new Dictionary<(uint, string), Context>();
        string[] lines = Encoding.Latin1.GetString(bytes).Split('\n');
        // When starting mid-file, discard the first fragment; the last element
        // is always ignored because it is either empty or an incomplete record.
        for (int i = tailOnly ? 1 : 0; i < lines.Length - 1; i++)
        {
            string line = lines[i].TrimEnd('\r');
            if (!Prefix(line, out uint pid, out string host, out string message))
            {
                pending.Clear();
                continue;
            }
            var key = (pid, host);
            bool txMeta = Match(message, TxContext, out string meta);
            bool rxMeta = !txMeta && Match(message, RxContext, out meta);
            if (txMeta || rxMeta)
            {
                pending.Remove(key);
                if (Hex(meta, 20, out byte[] data) && data.Length == 20)
                {
                    if (pending.Count >= 256) pending.Clear();
                    pending[key] = new(txMeta ? NativeTraceDirection.Tx : NativeTraceDirection.Rx,
                        Word(data, 0), Word(data, 4), Word(data, 8), Word(data, 12), Word(data, 16));
                }
                continue;
            }
            pending.Remove(key, out Context? context);
            bool tx = Match(message, TxMessage, out string payload);
            bool rx = !tx && Match(message, RxMessage, out payload);
            if ((!tx && !rx) || !Hex(payload, 52, out byte[] raw) || raw.Length < 4) continue;
            var direction = tx ? NativeTraceDirection.Tx : NativeTraceDirection.Rx;
            if (context?.Direction != direction) context = null;
            // Do not infer CAN ID from bytes without confirmed CAN/ISO15765 context.
            uint? canId = null;
            if (context?.Protocol is 5 or 6)
            {
                uint id = Word(raw, 0);
                if (id <= 0x1FFFFFFF) canId = id;
            }
            if (rows.Count == MaxRows) rows.Dequeue();
            byte[] shown = canId.HasValue ? raw[4..] : raw;
            rows.Enqueue(new(pid, host, direction, context?.Channel, context?.Protocol, context?.Flags,
                context?.Baud, context?.TimeUs, canId,
                string.Join(" ", shown.Select(b => b.ToString("X2", CultureInfo.InvariantCulture))),
                raw.Length == 52));
        }
        return new(rows.ToArray(), tailOnly);
    }

    private static uint Word(byte[] data, int offset) =>
        BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));

    private static bool Prefix(string line, out uint pid, out string host, out string message)
    {
        pid = 0; host = message = "";
        if (line.Length is < 17 or > 320 || !line.StartsWith("[PID=", StringComparison.Ordinal) ||
            line[13] != ' ' || !uint.TryParse(line.AsSpan(5, 8), NumberStyles.AllowHexSpecifier,
                CultureInfo.InvariantCulture, out pid)) return false;
        int end = line.IndexOf("] ", 14, StringComparison.Ordinal);
        if (end < 15 || end - 14 > 47) return false;
        host = line[14..end];
        if (host.Any(c => c < ' ' || c == '\u007f')) return false;
        message = line[(end + 2)..];
        return true;
    }

    private static bool Match(string message, string label, out string data)
    {
        data = "";
        if (!message.StartsWith(label + " ", StringComparison.Ordinal)) return false;
        data = message[(label.Length + 1)..];
        return true;
    }

    private static bool Hex(string text, int max, out byte[] bytes)
    {
        bytes = [];
        string[] tokens = text.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (tokens.Length is < 1 || tokens.Length > max) return false;
        var result = new byte[tokens.Length];
        for (int i = 0; i < tokens.Length; i++)
            if (tokens[i].Length != 2 || !byte.TryParse(tokens[i], NumberStyles.AllowHexSpecifier,
                CultureInfo.InvariantCulture, out result[i])) return false;
        bytes = result;
        return true;
    }
}
