using System.Diagnostics;

namespace VirtualCar.Core;

/// <summary>Runs the explicitly selected, reviewed local Python preview only. No shell, network, export or provider registration.</summary>
public sealed class CemPreviewProcessTransport : ICemPreviewTransport
{
    private readonly string _python;
    private readonly string _script;
    private readonly string _data;

    public CemPreviewProcessTransport(string python, string script, string privateDirectory)
    {
        if (!Path.IsPathFullyQualified(python) || !Path.IsPathFullyQualified(script)
            || !Path.IsPathFullyQualified(privateDirectory)
            || Path.GetFileName(script) != "vc071_view.py"
            || !File.Exists(python) || !File.Exists(script) || !Directory.Exists(privateDirectory))
            throw new ArgumentException("Explicit local preview paths required.");
        _python = Path.GetFullPath(python);
        _script = Path.GetFullPath(script);
        _data = Path.GetFullPath(privateDirectory);
    }

    public async Task<byte[]> PreviewAsync(byte[] request, CancellationToken cancellationToken)
    {
        if (request.Length is < 1 or > 32768) throw new InvalidDataException("Preview request size.");
        cancellationToken.ThrowIfCancellationRequested();
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        deadline.CancelAfter(TimeSpan.FromSeconds(30));
        var token = deadline.Token;
        using var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = _python,
                WorkingDirectory = Path.GetDirectoryName(_script)!,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            }
        };
        foreach (var argument in new[] { "-E", "-s", "-B", _script, "--data", _data })
            process.StartInfo.ArgumentList.Add(argument);
        bool started = false;
        try
        {
            started = process.Start();
            if (!started) throw new InvalidOperationException();
            var output = ReadBoundedAsync(process.StandardOutput.BaseStream, CemPreviewClient.MaxResponseBytes, deadline);
            var errors = ReadBoundedAsync(process.StandardError.BaseStream, 8192, deadline);
            var write = WriteAsync(process, request, deadline);
            var exit = process.WaitForExitAsync(token);
            await Task.WhenAll(output, errors, write, exit).ConfigureAwait(false);
            if (process.ExitCode != 0 || (await errors.ConfigureAwait(false)).Length != 0)
                throw new InvalidDataException("Local preview rejected.");
            return await output.ConfigureAwait(false);
        }
        catch (Exception)
        {
            if (started)
            {
                try { if (!process.HasExited) process.Kill(entireProcessTree: true); }
                catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception or NotSupportedException) { }
                // Never wait indefinitely for a failed or timed-out child.
                try { await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(2)).ConfigureAwait(false); }
                catch (Exception ex) when (ex is InvalidOperationException or TimeoutException) { }
            }
            cancellationToken.ThrowIfCancellationRequested();
            throw new InvalidDataException("Local CEM preview failed.");
        }
    }

    private static async Task WriteAsync(Process process, byte[] request, CancellationTokenSource deadline)
    {
        try
        {
            await process.StandardInput.BaseStream.WriteAsync(request, deadline.Token).ConfigureAwait(false);
            process.StandardInput.Close();
        }
        catch { deadline.Cancel(); throw; }
    }

    private static async Task<byte[]> ReadBoundedAsync(Stream source, int cap, CancellationTokenSource deadline)
    {
        try
        {
            using var result = new MemoryStream();
            byte[] buffer = new byte[8192];
            while (true)
            {
                int n = await source.ReadAsync(buffer, deadline.Token).ConfigureAwait(false);
                if (n == 0) return result.ToArray();
                if (result.Length + n > cap) throw new InvalidDataException("Preview output limit.");
                result.Write(buffer, 0, n);
            }
        }
        catch { deadline.Cancel(); throw; }
    }
}
