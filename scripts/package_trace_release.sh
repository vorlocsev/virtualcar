#!/usr/bin/env bash
# Package only the independently buildable tracing/inspection tool.
# This script intentionally does NOT publish or include a vehicle emulator.
set -euo pipefail
cd "$(dirname "$0")/.."

app="SectorV-Trace-OneClick-v0.3.6.7-dev26.exe"
proxy="cmd/oneclick/assets/VirtualCarTrace32.dll"
out="_build/release"
archive="VirtualCar-Trace-OneClick-Windows-x86.zip"

# Gate 1: only release an already compiled Windows OneClick app.
test -s "$app"
# Gate 2: its source-built 32-bit tracing DLL must exist.
test -s "$proxy"
# Gates 3-4: reject PE32+ / x64 and other wrong target formats.
file "$app" | grep -q "PE32 executable"
file "$app" | grep -Eq 'Intel (i386|80386)'
file "$proxy" | grep -q "PE32 executable"
file "$proxy" | grep -Eq 'Intel (i386|80386)'
# Gate 5: all fourteen documented J2534 PassThru exports must be present.
test "$(objdump -p "$proxy" | grep -c 'PassThru')" -eq 14
# Gate 6: do not accidentally package local original/proprietary binaries.
test ! -e "VirtualCarJ2534.dll"
test ! -e "SectorV.exe"

mkdir -p "$out"
cp "$app" "$out/$app"
cat > "$out/README-TRACE-ONLY.txt" <<'EOF'
VIRTUAL CAR TRACE: EXPERIMENTAL RESEARCH TOOL, NOT A CAR EMULATOR

This Windows x86 OneClick program contains a source-built J2534 tracing
proxy and three research analyzers. It does NOT include an original
VirtualCarJ2534.dll, a diagnostic application, or verified Volvo ECU
responses. It requires a separately obtained, authorized original J2534
DLL and authorized target program to run its tracing workflow.

Do not use this package to assume a simulated XC90, validated CEM transport,
real PIN access, safe ECU programming, or physical-vehicle compatibility.
Do not upload real VIN, identifiers, credentials or private CAN traces.
Source and limitations: https://github.com/vorlocsev/virtualcar
EOF
cat > "$out/RELEASE-NOTES.md" <<'EOF'
Experimental Virtual Car Trace dev26 for Windows x86.

Contains the OneClick J2534 tracing proxy/analysis tool, NOT a complete
virtual XC90 or the missing original VirtualCarJ2534.dll. The tool is
intended for authorized, read-only diagnostic research. It requires a
separately obtained original J2534 DLL and application.

The GitHub Actions source build, C route/classifier tests, Go tests,
Win32 PE target checks and 14 J2534 export checks must succeed before
this prerelease is created. Windows GUI and physical vehicle acceptance
are not claimed. See README_RU.md and docs/PROVENANCE.md in the source tree.
EOF

(
  cd "$out"
  rm -f "$archive" SHA256SUMS.txt
  zip -q -9 "$archive" "$app" README-TRACE-ONLY.txt
  # Gate 7: verify that the self-contained release ZIP has exactly these files.
  diff -u <(printf '%s\n' "$app" "README-TRACE-ONLY.txt" | sort) \
          <(unzip -Z1 "$archive" | sort)
  unzip -tq "$archive"
  sha256sum "$archive" > SHA256SUMS.txt
  # Gate 8: verify release checksums instead of merely printing them.
  sha256sum -c SHA256SUMS.txt
)
echo "Eight offline trace packaging gates passed; not a vehicle emulator."
