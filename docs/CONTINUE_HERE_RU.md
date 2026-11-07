# CONTINUE HERE: Virtual Car (для нового чата)

Updated: 2026-10-31. This file is the durable handoff; **always verify live GitHub state before acting**. It is not a substitute for reading the code, PRs or Actions.

## First action in a new chat

1. Open the private repository `https://github.com/vorlocsev/virtualcar` using the connected GitHub app.
2. Read this file, `AGENTS.md`, `docs/CHAT_GITHUB_WORKFLOW_RU.md`, `docs/ROADMAP.md`, and current `emulator/README_DEV28.md`.
3. Check `development` and `main` heads, open Issues and PRs, and GitHub Actions **at the current SHA**.
4. Continue the highest-priority unblocked task on a focused branch from `development`; open a PR into `development`.
5. Provide a short Russian report: change, PR/commit, actual test result, remaining blocker. Never invent completed tests.

## Project identity

- Virtual Car: **private** `vorlocsev/virtualcar`. Windows x86 J2534 virtual Volvo P2 car, target XC90 V8 MY2009, read-only, VMware diagnostic compatibility.
- **Separate** from `vorlocsev/dvinholm`; do not mix code, issue queues or release status.
- `emulator/`: original user-supplied VirtualCarJ2534 source v0.3.6.6, observation-only Vehicle Core integration, READ128 fix, GUI Control, profile/fixture tests.
- `proxy/`, `cmd/oneclick/`: older tracing/proxy diagnostic tools, **not** the vehicle emulator DLL.
- `research/dev23` to `dev25`: historical snapshots. `docs/research/`: early P2 CAN and SavvyCAN CSV research.

## Confirmed baseline (recheck current state)

- PR #2: `development` -> `main`, **draft**, gate for VMware tests. Do not merge automatically.
- Latest checked development SHA at time of handoff: `f73394aede2cf4078756d3b562c76efdb2c62e7f`; both CI workflows completed successfully on that SHA. This can change.
- Workflow optimization PR #3 merged to `development`: task PR template, AGENTS.md, independent CI path filters, cancellation of redundant builds, artifact versioning.
- dev28 READ128 regression tested in code; no proven end-to-end J2534 NumMsgs=128 call in the earlier VMware log.
- B9FB replay with private donor profile: prior user-provided log showed 3 successful requests, 13 frames each; preserve this behavior.
- B9FC donor profile has 21 configured frames but latest analyzed session did not request them.
- CEM A3, A6, B9F0 and P3 0x726 / 29-bit 0x18DA50F1 identification remain **unresolved**. Never synthesize a positive response without a trustworthy reference.
- Donor profile is for XC90 V8 2005, **not verified for MY2009**; no donor VIN, raw traces, private INI or proprietary diagnostic binaries in GitHub.
- Real Windows/VMware SectorV or VDASH acceptance of the newest DLL is not confirmed. Physical J2534 hardware tests postponed.
- dev30 SavvyCAN CSV analyzer reports stats without replaying private frames; 2002 S60 / 2003 V70 IDs are not confirmed for XC90 MY2009.

## Priority and workflow

1. P0: Real CEM identification and diagnostic transport. Determine whether missing response is routing, filtering, timing or lack of verified fixture. Use read-only logs and isolated emulator.
2. P0: Preserve B9FB and READ128; use 6-8 meaningful regression groups per stage.
3. P1: Model-year-gated CAN traffic / wake state model with synthetic tests; never mistake bus Awake for diagnostic normal mode.
4. P1: VMware validation and evidence, then review draft PR #2.
5. No release, no main merge, no fake VIN or positive ECU identity without explicit verified evidence and user approval.

## Chat behavior

- User often says `далее`: treat as continue coding in the GitHub repo, not a request for another plan.
- Work directly in GitHub using its connected tools, one focused PR at a time. Keep updates concise.
- Do not produce a new ZIP for every increment. Use CI artifacts for lab binaries; make standalone ZIP only on request or for manual VMware testing.
- Never claim code published, CI green, PR merged or Windows/VMware tested unless verified via tools.
- If a required private donor profile is absent from the new chat, **do not reconstruct or invent it**. Ask for reattachment only when essential.

## One-line user prompt for the next chat

`Продолжи Virtual Car по github.com/vorlocsev/virtualcar. Прочитай docs/CONTINUE_HERE_RU.md и AGENTS.md, проверь текущие PR и CI и продолжи приоритетную задачу в development.`
