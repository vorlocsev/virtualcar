# Virtual Car development instructions

These instructions apply to coding agents working in this repository. See docs/CHAT_GITHUB_WORKFLOW_RU.md for the operational process.

## Source of truth
- Use GitHub source and CI results as the authority. The uploaded ZIPs from historical stages are archival, not the live source of truth.
- main is the reviewed baseline; development integrates verified branches. For a task, branch from development and open one focused PR into development. The existing development-to-main PR is a separate release gate.
- Treat emulator/ as the actual v0.3.6.6-derived J2534 emulator source on development; proxy/ is the tracing proxy. Do not confuse them.

## Changes
- Work in meaningful increments, normally 1 issue, 1 focused PR, 6-8 groups of relevant checks. Avoid iterative empty documentation-only PRs or hundreds of tiny regressions.
- Verify existing implementation and CI before writing code. Reuse the actual source files; do not regenerate complete repositories from ZIPs.
- Preserve existing B9FB replay. CEM A3, A6, B9F0 and other incomplete diagnostics must not receive invented positive responses.
- Keep read-only lab behavior. Do not add programming, security-access or immobilizer-bypass functionality.
- Every code change needs tests covering behavior, failure modes and regressions; mark hardware/VMware checks as not performed until evidence exists.

## Privacy and attribution
- Never commit donor VINs, private INI profiles, raw J2534 logs, credentials, proprietary binaries or ECU dumps.
- Synthetic fixtures must be labeled synthetic. Redaction must not be represented as a real vehicle-identification response.
- Keep externally researched CAN IDs model-year-specific; early P2 250 kbit/s HS mapping is not evidence for XC90 V8 2009 500 kbit/s.
- Third-party GPL code must not be copied without a license review; link and summarize external research independently.

## Chat response contract
- On 'далее', check issue/PR/CI status, continue the current highest-priority unblocked issue and produce a real repository change when justified.
- Report only: what changed, commit/PR, verified checks, unverified blockers, next step. Keep it concise and in Russian.
- No new downloadable ZIP unless needed for Windows/VMware manual testing or explicitly requested. Prefer versioned CI artifacts.
- Do not claim a build, PR merge, GitHub upload, test or VMware run without confirming it from the relevant tool output.
