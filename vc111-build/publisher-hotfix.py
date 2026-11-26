"""VC112: patch only the verified VC110 extracted prototype. No registry/VIDA access."""
import hashlib
from pathlib import Path
import sys

def checked(root, path, sha):
    p=root/path
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:
        raise ValueError("Unexpected source: "+path)
    return p,raw.decode("utf-8")

def replace(s,a,b):
    if s.count(a)!=1:
        raise ValueError("Missing or ambiguous anchor: "+a[:80])
    return s.replace(a,b,1)

def patch(root):
    p,s=checked(root,"winui/LivePublisher.cs","20f9b86d2c49768992604ce156884d4355678b5ad3f1b7bb9e73faa2721240e8")
    _,w=checked(root,"vc109/winui/LiveControlWindow.cs","e39cf73b916fc6e41e64c47669993977e135a2374ec3f6eb34c27d2516b1cf95")
    g,t=checked(root,"acceptance/prepare_all.py","0a418b77cced754b910ae674ad5e7f8f63b01af2c02be80e22c60f4cc8bbfc2b")
    s=replace(s,"    private bool failed, ending;",'''    private bool failed, ending;
    private string diagnostic = "";
    private static bool IsTransientWrite(Exception ex)
    {
        if (ex is not IOException && ex is not UnauthorizedAccessException) return false;
        uint hr = unchecked((uint)ex.HResult);
        return hr == 0x80070020u || hr == 0x80070021u || hr == 0x80070005u;
    }
    private static string Describe(Exception ex) =>
        $"{ex.GetType().Name} (0x{unchecked((uint)ex.HResult):X8}): {ex.Message}";
'''.rstrip())
    s=replace(s,"public (VehicleSnapshot? Snapshot, bool Failed) Read()", "public (VehicleSnapshot? Snapshot, bool Failed, string Diagnostic) Read()")
    s=replace(s,"return (Fresh() ? published : null, failed);", "return (Fresh() ? published : null, failed, diagnostic);")
    s=replace(s,"    private async Task RunAsync()\n    {\n        try","    private async Task RunAsync()\n    {\n        int consecutive = 0;\n        int total = 0;\n        try")
    s=replace(s,'''                session.Publish(next);
                lock (gate) { if (!ending) { published = next; publishedAt = sampledAt; } }''','''                try { session.Publish(next); }
                catch (Exception ex) when (IsTransientWrite(ex))
                {
                    consecutive++;
                    if (total < int.MaxValue) total++;
                    lock (gate)
                    {
                        published = null;
                        diagnostic = $"Publication retry {consecutive}/20: " + Describe(ex);
                    }
                    if (consecutive >= 20) throw;
                    // Sample again on the next iteration; never re-stamp an old snapshot.
                    await Task.Delay(Random.Shared.Next(53, 147), stop.Token).ConfigureAwait(false);
                    continue;
                }
                lock (gate)
                {
                    if (!ending)
                    {
                        published = next;
                        publishedAt = sampledAt;
                        if (consecutive != 0) diagnostic = $"Publication recovered; skipped {total} snapshot(s).";
                    }
                }
                consecutive = 0;''')
    s=replace(s,"catch (Exception) { lock (gate) { failed = true; published = null; } }","catch (Exception ex) { lock (gate) { failed = true; published = null; diagnostic = Describe(ex); } }")
    a='            status.Text = message + (notice.Length == 0 ? "" : "\\n" + notice);'
    b='''            string publisherDiagnostic = state?.Diagnostic ?? "";
            status.Text = message + (publisherDiagnostic.Length == 0 ? "" : "\\n" + publisherDiagnostic)
                + (notice.Length == 0 ? "" : "\\n" + notice);'''
    assert w.count(a)==1
    # The original generated-window comparison must still run before changing it.
    anchor="    window.write_bytes(result)"
    t=replace(t,anchor,
        "    hotfix_old = "+repr(a.encode())+"\n"
        "    hotfix_new = "+repr(b.encode())+"\n"
        "    if result.count(hotfix_old) != 1: raise ValueError('VC112 UI anchor mismatch')\n"
        "    window.write_bytes(result.replace(hotfix_old,hotfix_new,1))\n"
        "    print('VC112_PUBLICATION_HOTFIX=STAGED')")
    p.write_bytes(s.encode("utf-8"))
    g.write_bytes(t.encode("utf-8"))

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: publisher-hotfix.py EXTRACTED_PROTO")
    patch(Path(sys.argv[1]))
    print("VC112_HOTFIX_SOURCE=PASS")
