# P0-VIN-07 checkpoint: exact-Git-blob combined Python regression verification

Date: 2026-11-08
Repo: `vorlocsev/virtualcar`
Branch: `fix/p0-vida-bootstrap-getscript-window-boundaries`
Research PR: #197 (Draft, stacked on Draft #192)
Verified PR HEAD before checkpoint: `c70034f89ceff10921c629bddfd5eb5491094c03`
Environment: isolated local Python **3.13.5** on Linux. **Not** Windows VMware CI.

## Completed checks (eight groups)

1. **Exact source bytes**: fetched the bootstrap classifier from GitHub and reconstructed it locally; Git blob SHA-1 exactly `297f5404fa010254f5c084aaa9a581de0769e7dc`: PASS.
2. **Exact bootstrap unit tests**: fetched matching GitHub test module; blob SHA-1 exactly `a955834dc2f74d5c261710415d48d90e48b17132`: PASS.
3. **Exact service catalog source**: copied the previously verified PR #192 classifier, Git blob SHA-1 exactly `c87b89672e4f9b4f847b965b1d31612ef3b31311`: PASS.
4. **Exact catalog tests**: matching source test blob SHA-1 exactly `bf1a7d76af5814de7c272f201f7ce5262c10085c`: PASS.
5. **Bootstrap regression execution**: actual `python -m unittest discover -s emulator/tests -p 'test_audit_vida_readvin_bootstrap_trace.py' -v`, **18/18 PASS**, 0 failures/errors.
6. **Combined regression execution**: actual `python -m unittest discover -s emulator/tests -p 'test_*.py' -v` over the **two present** modules, **27/27 PASS**, 0 failures/errors. The test suite is a bounded local subset, **not the entire repository**.
7. **Python source compilation**: `python -m compileall -q emulator/tools emulator/tests`: PASS.
8. **Safety evidence boundary**: synthetic cases assert TX echo not ECU RX, RX prefixes not accepted VIN, split GetScript windows do not join, report omits privacy tokens; reviewed flags remain false for real VIN and replay: PASS.

Execution timing for combined local suite: **Ran 27 tests in 0.010s; OK**.

## Source & CI gating

The four verified files above match the exact committed blob content. The only new runtime functionality is an offline log-classification correction. No changes to J2534 DLL, CEM replies or ECU protocol.

- **Windows self-hosted VMware owner-only CI:** NOT RUN for the current PR #197 HEAD. GitHub connector does not expose new `workflow_dispatch`; do not claim CI success.
- **Full C/Go/C++/.NET emulation suite:** NOT RUN in this local environment.
- **Original owner-private selected VIDA ReadVin XML ZIP and same-installation T111 CSV:** NOT TESTED.
- **Actual SectorV / VDASH VIN acceptance, target XC90 V8 MY2009, physical J2534:** UNVERIFIED.
- **Build artifact:** NOT PUBLISHED. **GitHub Release:** NOT PUBLISHED.

## Decision and next gate

Leave PR #197 **Draft**: the exact-source Python regression is green but Windows CI and original vehicle evidence remain open. Keep the stacked base PR #192 Draft too. Next owner-trusted Windows CI should validate an immutable reviewed head of this stack, then inspect same-installation original VIDA GetScript+T111 evidence offline. No claims of working virtual VIN or new release until proven by actual client acceptance.
