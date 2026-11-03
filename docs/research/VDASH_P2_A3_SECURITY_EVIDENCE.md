# P2 CEM A3/E3: security-service evidence and conservative observation contract

Date: 2026-11-03. Research PR #39, branch
research/vdash-functional-keepalive. **Read-only static/offline evidence.**
No VMware, physical DiCE/J2534 or live SectorV session during this stage.

## Distinguish sources and clients

| Evidence | Supported observation | Does not establish |
| --- | --- | --- |
| Historical private SectorV MY2005 PR30, summarized in docs/research/p2-public-capture-followup.md | After a completed 13-frame target 50 B9FB/VIN matcher, the client enters a Hardware step. Native text/backend identifies a subsequent D2 A3 request on the target 50/500k and later target 40/125k routes; no reply, about 5 seconds wait on each client Hardware route | The exact E3 response body, correct credential, an ECU accepted state, or behavior of MY2009 XC90 V8 |
| waal70, The CAN network on a Volvo, part three, 2015-12-02 | A3 is listed as D2 "Security Access Mode"; B9 is "Read Data Block By Offset"; C8+n length rule for CAN D2 request | Exact A3 byte-level reply or use by all model years |
| Matthews Volvo Site, Vida CEM swapping, page 404, post dated 2025-10-14 | Author describes some early CEM security-mode operations returning E3 with mode echo; a subsequent protected operation was denied | Verified XC90 V8 MY2009 fixture, universal authorization meaning or accepted normal-mode predicate |
| Matthews Volvo Site, Corrupt CEM Non Start Investigation, January 2025 | Forum participants report seeing E3 02 while a following protected read was rejected | Guaranteed access, valid key material, or protocol specification |
| Current native source emulator/src/p2core/p2_cem_router.c | A3 is only classified; response remains NEED_EVIDENCE. The separate E3 02 helper is explicitly a candidate-prefix reader | ECU response generation, PIN/security validation or working authentication |

Public references:
- https://waal70blog.wordpress.com/2015/12/02/the-can-network-on-a-volvo-part-three-message-interpretation/
- https://www.matthewsvolvosite.com/forums/viewtopic.php?p=668272
- https://www.matthewsvolvosite.com/forums/viewtopic.php?t=105847&start=10

## Technical correction: A3 is not an "identify hardware" opcode

In SectorV the *client phase* is called Hardware. In the D2 service
catalogue A3 is **Security Access Mode**. The adjacent timing evidence
shows that the client sends A3 during its Hardware phase. These two
statements do not imply that A3 is a generic read-hardware-number
operation. Inferring a hardware identity from A3 or a bare E3 echo
would be an unsupported jump.

B9FB (read vehicle block) and A3 (access-related service) are
distinct. Delivering a B9FB response can cause SectorV to advance to
its next phase, yet the client's acceptance of all B9FB semantics,
the A3 credentials, the expected E3 record and the exact condition
for continuing to enumerate ECUs remain unverified.

## Contract hardening applied to the existing C classifier

The *observed SectorV A3 shape* is represented only by an eight-byte
CAN payload whose first D2 byte is CF. CF declares seven significant
bytes following it. A CB or CA header indicates a shorter service
request and cannot carry the full observed six-byte A3 tail merely
because the right bytes appear in CAN padding. Exact length eight
also excludes impossible nine-byte classic CAN payloads.

Code: emulator/src/p2core/p2_cem_router.c, matched_full_shape predicate.

The ordinary A3_OTHER classification is retained when a recognized
D2 CEM request does not match the full observed shape. It remains
NEED_EVIDENCE and does not send a reply. Existing B9FB/B9F0/B9FC
replay/fixture handling is unchanged.

Eight native C checks in emulator/tests/virtualcar_test.c:
1. Exact target 50/HS500 request classified as an observed shape.
2. Exact target 40/LS125 bytes classified as an observed shape, but not claimed a valid real session.
3. CB with trailing lookalike bytes is NOT a full shape.
4. CA with trailing lookalike bytes is NOT a full shape.
5. Mutated A3 operand is NOT a full match.
6. Truncated CF request is NOT a full match; oversized input has a secondary assertion.
7. Exact bytes on wrong bus remain ROUTE_MISMATCH.
8. Same bytes on a foreign CAN identifier are NOT D2 CEM.
The test block also asserts the E3 02 *prefix helper* recognizes a
prefix and requires both bytes. No test claims E3 means authorized.

## Explicit prohibitions and next evidence needed

Do not implement an A3/E3 responder by guessing challenge values,
security PINs, mode transitions, or access confirmation. Do not use
internet anecdotes as substitute for consented, authenticated
XC90 V8 MY2009 captures. No secret extraction, key search,
protected-memory access or ECU write/programming is in this stage.

A future legitimate read-only recording would need a single-run,
source-timestamped client/J2534 observation of post-B9FB A3 and the
unmodified E3 or negative reply, including capture completeness and
vehicle provenance. Without such a record, the accepted response
predicate is unknown; CPU-only CI success proves only the classifier.


## Follow-up: distinguish A3/A6 unsupported bus from missing response (same date)

The native response handler emulator/src/virtualcar.c initially returned the
same backend reason, unimplemented_probe, for a complete D2 CEM A3/A6 on
*either* bitrate. This collapses two different questions:

- **Recognized request on the expected P2 route:** CEM target 0x50 on
  500000 baud, or target 0x40 on 125000 baud. The classification remains
  unimplemented_probe/no_response because there is no validated positive
  response fixture.
- **Recognized request on a mismatched P2 route:** target 0x40 on 500000
  baud, or target 0x50 on 125000 baud. The classification is now
  unsupported_bus/no_response, even though the J2534 WriteMsgs call
  itself can still succeed.

This changes only the fixed-literal diagnostic backend reason. It does not
change J2534 write return codes, emit or modify a CAN response, perform
security access or claim any ECU authorization. Do not interpret
unsupported_bus as proof a *physical* Volvo/DiCE would reject the same
route: it is the explicitly configured Virtual Car P2 routing model.

Eight native C regression cases call actual PassThruConnect,
PassThruWriteMsgs and PassThruReadMsgs on separate 500k/125k channels for
A3 and A6 on both targets. They assert exactly one terminal backend event
with the expected reason, no response_generated event, and zero RX. The
pre-existing classifier synthetic tests are also updated to distinguish
unsupported_bus from unimplemented_probe when target 40 is sent over 500k.

No primary SectorV Hardware success predicate or authenticated A3/E3 reply
was found in currently available local GitHub sources and project files.
Existing sanitized PR30 notes remain the only direct client observation:
B9FB matching, then a Hardware A3 no-reply phase. Do not reclassify these
two observations as the same failure or synthesize an E3 answer.
