# VIDA 2015A: configuration source selection and the NoCommConnection boundary

**Scope:** static inspection only, 2026-11-07. Original files from the
owner's authorized VIDA 2015A diagnostic directory remain private and
are **not** committed. Original `Core.DLL` SHA-256:
`f7e73e59cd64923d6bb34e17883eccdc29fa7c47e0b22af86fc97a32e87e7f9e`.

## Source-verified configuration resolution chain

A distinct original `Core.DLL` call chain was followed through metadata
and bounded IL without executing a managed assembly:

| Original Core MethodDef | Direct role established statically |
| --- | --- |
| `0x06000248` `Settings..cctor` | Calls `get_useClientSettings`, passes result to `DiagApplication.set_UseLocalSettings` |
| `0x0600024D` `Settings.get_useClientSettings` | Reads `UseClientSettings` via `Settings.getValue` |
| `0x0600024B` `Settings.getValue` | Delegates to `Settings.getValueXml` |
| `0x0600024A` `Settings.getValueXml` | Calls `DiagApplication.GetValue` |
| `0x060000BC` `DiagApplication.GetValue` | Selects an XML node via `get_ConfigAsXml`; retrieves its `value` attribute |
| `0x060000BA` `DiagApplication.get_ConfigAsXml` | Uses `XmlDocument.Load` with `get_ConfigUrl` |
| `0x060000C5` `DiagApplication.get_ConfigUrl` | Selects local/server config URL based on `UseLocalSettings` |
| `0x060000C3` / `0x060000C4` | Server/local URL builders each use filename `diagnostic.config.xml` |
| `0x06000251` `Settings.get_DiagnosticConnection` | Reads `DiagnosticConnection` through this getter and compares known mode names |

The getter recognizes **four distinct strings** and maps them to
distinct internal values:
`J2534DiagnosticConnection=0`,
`DiCEDiagnosticConnection=1`,
`VirtualDiagnosticConnection=2`,
`NoCommConnection=3`; unmatched/absent becomes separate fallback 4.
These are *settings enum values*, not confirmed J2534 ProtocolIDs,
physical channels or proof of successful tool creation.

The owner's original `diagnostic.config.xml` reports
`UseClientSettings=false`, `UseLocalDatabase=false`,
`DiagnosticConnection=NoCommConnection`,
`VehType=p2x`, `ScriptPath=res/scripts/` and
`LogLevel=Trace`.
`components.config.xml` separately registers the `ScriptProvider`
against `DiagSwdlRepository` and sets `TraceScript=false`.
These two diagnostics settings govern different layers.

### Strong conditional conclusion, not a runtime assertion

If the **active** VIDA service actually loads the **same**
server-side configuration with `UseClientSettings=false`,
the source getters are wired to return the `NoCommConnection`
setting rather than the distinct `DiCEDiagnosticConnection` or
`J2534DiagnosticConnection` setting. This is an important
**possible explanation for an absence of communication in a VIDA
laboratory session**, but neither the original file nor the IL proves
the specific service did load this file, which running instance was
contacted, what communication tool the operator selected, or whether
a J2534 call was attempted.

Do not modify a VIDA installation's communication config to
test this hypothesis. A controlled, consented read-only session
can instead **observe** the effective configuration source and
the chosen tool at the application layer, separately from J2534 TX/RX.

## Independent initial VIN script selection is now much better bounded

The original `ValueObjects.DLL` resolves
`ScriptType.ReadVin=4`, `EcuIdentificationHighSpeed=19`,
and `EcuIdentificationLowSpeed=20`.
The `RunIdentifyVehicleScript` IL calls the ReadVin type with
an empty profile and then the **five-argument** ScriptProvider
GetScript path, which reaches `GetOneScriptFromDb` and
`GetFromDb` / stored procedure `GetScript`.
The early special disk checks refer to ECU-identification HS/LS
types 19/20, not ReadVin 4. The presence or absence of
`res/scripts/` in a partial Drive snapshot therefore must
**not** be reported as proof of a broken initial VIN flow.

See the merged
[original VIDA source audit](vida-2015a-carcom-gateway-source-boundary.md)
for original-file hashes, MethodDefs, metadata signatures and
the separate default-ECU/profile/gateway evidence.

## Next collection step: schema metadata, not private scripts

The authorized `DiagSwdlRepository` database itself was **not**
available as an SQL database during this analysis. Its attachment
in old installer logs does not prove runtime query success.
Before attempting a private read-only VIN session:

1. Check effective active VIDA config **without changing it**.
2. Via an authorized local SQL client, query only the **metadata**
   for the `GetScript` procedure and its parameter names/types.
   Do not execute a stored procedure until its effects are reviewed.
3. Verify metadata compatibility for Script, ScriptType,
   ScriptProfileMap and ScriptContent. Public **2014D** table
   layouts do not establish exact **2015A** contents.
4. Observe a genuine `GetScript` lookup with `ReadVin`
   type 4 and its retrieval outcome in one private diagnostic
   session. A lookup does not itself prove successful execution.
5. Separate loaded script, B9FB transport, returned identity,
   vehicle-profile resolution and ECU identification.
6. Do not upload SQL databases, XML scripts, VIN, scripts' original
   internal IDs, private logs, credentials or diagnostic payloads.
7. Do not run ECU programming, unlock/security challenge, PIN
   extraction or vehicle configuration changes.
8. Do not publish Virtual Car builds or infer a successful
   XC90 V8 MY2009 identification without a real accepted client
   session.

**Offline only; no new emulator responses or J2534 driver changes.**
