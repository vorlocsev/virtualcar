# Mandatory CAN bus isolation for P2 CEM D2 fixtures

Research checkpoint: 2026-11-04, Virtual Car Draft PR #39.
Read-only transport behavior only, not SectorV/VDASH client acceptance.

## Evidence and known limitation

For the studied Volvo P2 diagnostic routes, CEM target 0x40 corresponds
to the low-speed CAN side (125 kbit/s) and CEM target 0x50 to the
high-speed CAN side (500 kbit/s). These are diagnostic addresses, not
model-year flags or proof of the CEM-L/CEM-H hardware variant.

The published 2005 XC70 DiCE B9FB example is **not** an authenticated
XC90 V8 MY2009 B9FB fixture. The default virtualcar.ini therefore
keeps B9FBFrameCount=0. The native emulator cannot claim SectorV/VDASH
accepts the identity or discovers actual ECU inventory without a
separate authorized client run.

## Actual code correction

Previously the six base D2 slots (40/50 x B9FB/B9F0/B9FC) could emit
a configured fixture on a channel with the WRONG baud if
[P2] StrictRouting=0. That option was historically used for broad
transport development, but it can make an impossible on-bus response
look like a real CEM.

The current process_d2() requires channel.baud == fixture.baud
for *every* D2 slot, including the six legacy slots and optional
D2_Node entries. An incorrect speed returns no ECU RX, records
unsupported_bus in the optional backend evidence, and never silently
reassigns the fixture to another bus. An absent fixture remains silent,
regardless of baud.

The old INI setting StrictRouting=0 is deprecated and ignored. The
reported effective flag is always 1. ReplaySpacingMs is independent
and still controls delivery pacing, not bus identity.

## Eight C host regression cases

Each fixture uses a synthetic read-only **negative** B9 response.
The test asserts silence on the opposite bus and exactly one frame
on the configured bus, while deliberately forcing the historical
global strict-routing variable to zero:

1. LS 0x40 B9FB, 125k allowed, 500k denied.
2. LS 0x40 B9F0, 125k allowed, 500k denied.
3. HS 0x50 B9FB, 500k allowed, 125k denied.
4. HS 0x50 B9F0, 500k allowed, 125k denied.
5. LS 0x40 B9FC, 125k allowed, 500k denied.
6. HS 0x50 B9FC, 500k allowed, 125k denied.
7. An unconfigured target 0x60 cannot inherit a CEM response.
8. Unsupported opcode B9FD cannot inherit a B9FB/F0/FC response.

The host C regression is executed by the GitHub emulator workflow
before cross-compiling the Windows x86 DLL. The existing isolated
Windows x86 native routes tests remain separate.

## Scope

This changes only the conditions under which *already configured
and validated* frames may be emitted. It does **not** reconstruct the
OEM FB schema, invent hardware/software part numbers, enable
security access, implement ECU programming, or create an XC90 V8
MY2009 donor profile.

If real authorized read-only SectorV/VDASH logs eventually establish
a different valid route for a specific vehicle, that route must be
modeled as a separately reviewed profile, not by disabling bus
isolation for all CEM responses.
