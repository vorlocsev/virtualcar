# Direct B9FB to B9F0 transport binding in one native J2534 epoch

Research checkpoint: 2026-11-04. Scope: Virtual Car, Draft PR #39.
This is read-only diagnostic-transport evidence, not genuine CEM identity.

## The gap

Previously a client-capture report counted positive B9F0 replies separately
from the independent B9FB to first-next-B9F0 chronology. A source could
contain a valid B9FB, an intervening unrelated application request, and a
positive B9F0 response, yet aggregate positive counts could appear to
support a direct handoff.

The native channel chronology requires one native PID scope, channel,
target, 500/125k bus, and clock agreement for the **first later** B9F0
request. A separate B9F0 auditor already verifies positive D2 framing,
CAN response route, service echo, RX windows and transport completeness.
The missing gate was a conservative binding between those conclusions.

## Binding rule

New summary field:
capture-summary.json.b9fb_to_b9f0_same_epoch_positive_binding

A positive direct binding requires all of the following:

1. Exactly one P2 native epoch, closed by PassThruClose.
2. Clean independent chronology/followup/B9F0 parsing and channel context.
3. Exactly one positive completed B9FB transport.
4. First later application TX is B9F0 on the same native channel,
   target and baud, with independently agreeing clock gap.
5. Exactly one B9F0 request in that epoch, without a competing attempt.
6. Independent B9F0 RX validates one positive, complete, correctly routed
   transport with the same target as that direct request.
7. Negative B9, incomplete RX, changed target, intervening A3, multiple
   epochs, repeated B9FB and multiple B9F0 remain unverified.
8. Even with a later positive P3 reply, no native log proves ECU inventory,
   VIN acceptance or vehicle identity inside SectorV or VDASH.

The client-boundary report includes the fixed fields
direct_b9fb_b9f0_positive_transport_bound and
direct_b9fb_b9f0_binding_status. It refuses to proceed to a supposed
direct native P3/ECU-list handoff merely because an unrelated B9F0
elsewhere in the same file completed positively.

## Evidence hierarchy

A positive native D2 reply only proves what the virtual J2534 layer
said it delivered. It does not prove that SectorV or VDASH parsed,
trusted, displayed or acted on that data. A source PID label, an
operator UI report and matching VIN-looking strings do not authenticate
a genuine XC90 V8 MY2009 CEM.

The fixture can still be synthetic, redacted or donor-derived. This
gate validates session order and transport, NOT Volvo D2 application
checksums, B9FB/B9F0 field semantics or hardware identifiers.

## Test coverage

Eight offline synthetic regression groups: direct positive single
epoch; negative B9F0; partial B9F0; intervening A3 followed by positive
B9F0; two competing B9F0 requests; repeated completed B9FB;
multiple or unclosed native epochs; and intentionally changed B9F0
target in the independent audit.

The Windows native-routes job runs the same binding on a log made by
the compiled Windows x86 J2534 DLL in an isolated synthetic process.
Only sanitized reports are uploaded.

An authorized real SectorV/VDASH read-only session is still necessary
before making any client acceptance or XC90 identity claim.
