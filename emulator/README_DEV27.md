# dev27: Integration of source v0.3.6.1 with Vehicle Core

Source origin: user-provided `SectorV-VirtualCar-v0.3.6.1-full-source.zip`.
**Do not substitute this DLL for the currently installed 0.3.6.6 without a separate VM validation.**

The full source archive contains a real J2534 implementation in `src/virtualcar.c`.
The new `src/p2core/` comes from our independently developed dev26 observation core.

The original D2 dispatcher processes B9FB/B9F0/B9FC only when a validated INI fixture exists. It does **not** respond to A3 or diagnostic ignition reference 6660. B9F0 fixtures are disabled in default INI (`FrameCount=0`), accounting for the no-RX result. B9FB can replay 13 frames when activated in the provided demo lab profile; this is a 2005-era historical excerpt with a synthetic VIN, NOT proven XC90 V8 MY2009 identity.

## What this integration changes
- Initializes a thread-serialized observational Vehicle Core at `PassThruOpen`.
- Tracks channels on `PassThruConnect` / `PassThruDisconnect`.
- Classifies outbound J2534 CAN D2 messages on `PassThruWriteMsgs` **before** existing dispatcher processing.
- Provides opt-in passive LS decode for `PassThruReadMsgs`; disabled by default.
- Does not change response frames, routing decisions, D2 timing, keys, VIN or programming policy.

## Build and tests
```
./build-cross.sh

gcc -std=c11 -O2 -Wall -Wextra -o /tmp/virtualcar_test \
  tests/virtualcar_test.c src/p2core/p2_cem_router.c \
  src/p2core/p2_ls_observer.c src/p2core/p2_vehicle_core.c \
  src/p2core/p2_j2534_bridge.c
/tmp/virtualcar_test
```

The ZIP omits the original uploaded executables and DLL. It includes no users' VIN or vehicle secrets.

The source v0.3.6.1 may not match the running v0.3.6.6 binary; compatibility must be verified independently. No real CEM A3 E3 response has been established. No on-vehicle tests performed.
