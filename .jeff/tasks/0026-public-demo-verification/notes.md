# Operation plan

## Decision

- Category: operation
- Complexity: complex
- Audit required: yes — installer/register state, detector execution, portable-path custody, reviewer separation, and cleanup all cross evidence-sensitive boundaries.
- Requires approval: false. Every mutation is confined to a newly created isolated `HOME` and portable case root.
- Approach: use the repository's supported installer and harness as-is, bind all evidence to one exact candidate, exercise the complete public demo once with one deliberate restart, independently verify the reviewer and gate receipts, then remove only the isolated managed installation.

## Ordered slices

1. Establish the exact candidate and its green prerequisite evidence.
2. Create hermetic user and case roots from the checked-in demo CSV, then install/register the candidate in the supported harness.
3. Exercise the complete gated workflow, including independent review and one restart/resume boundary.
4. Inspect portable outputs and receipts, then uninstall isolated managed state and prove the case remains usable.

## Preconditions

1. Task 27 has a terminal successful result for the same candidate revision/digest that will be installed.
2. The candidate-targeted checks and full repository suite have recorded exit status zero for that exact revision/digest.
3. The checked-in demo CSV, supported installer/uninstaller, supported harness, and candidate package are locally available; no network acquisition is needed.
4. Fresh, non-overlapping temporary paths are available for `HOME` and the portable case, and the ambient user installation is captured read-only for a later no-change comparison.

## Runbook

1. Read task 27's terminal record, identify the exact candidate revision/digest, and match it to zero-exit candidate-targeted and full-suite receipts. Stop on absence or mismatch.
2. Create fresh isolated `HOME` and case roots, copy the checked-in demo CSV into the case using a relative case path, and record the two roots only in the external operation log.
3. With isolated `HOME`, run the supported candidate installer/registration path; ask the supported harness to enumerate/resolve the installed Anomaly dispatcher and independent data-reviewer manifest.
4. Invoke the installed Anomaly skill and drive create, source registration, preparation/profile, recommendation, and Gate A. Supply explicit Gate A approval in its own user turn and verify the turn ends before detector work begins.
5. Run the prescribed detectors and create the draft/replay state. Record durable state, accepted attempt identifiers, detector outputs, and draft hash.
6. Stop the harness after detector execution or draft creation, start one fresh harness session against the same isolated `HOME` and case, and resume from the authoritative next action. Verify accepted attempt identifiers and artifacts are reused rather than repeated.
7. Run P5/P6 in a distinct fresh reviewer context. Capture reviewer context/session identity and its attestation of the exact draft hash. Then request Gate B, supply explicit Gate B approval in its own user turn, and verify neither orchestrator output, reviewer output, nor silence closes either gate.
8. Complete report and chart generation. Inspect durable state and attempt evidence, Gate A/Gate B receipts, reviewer attestation, report, charts, and the recorded artifact references.
9. Verify all case references are relative and resolve beneath the portable case; scan case artifacts for the absolute case-root prefix and credential material, requiring no matches.
10. Run the supported uninstall against isolated `HOME` only. Confirm the dispatcher/reviewer registration and isolated managed files are gone, the ambient installation snapshot is unchanged, and the retained case can still be opened with its state, report, and charts resolving.

## Recovery boundary

Retain the portable case and external operation log for diagnosis, but stop immediately on a prerequisite mismatch, a write outside the isolated `HOME` or case root, a gate closed without its explicit user approval turn, repeated accepted work after restart, reviewer-context/hash mismatch, or cleanup targeting non-isolated state. Recovery may remove only the newly created isolated `HOME`; it must not rewrite the candidate, ambient harness state, or retained case.

## Approval boundary

No approval boundary: all mutations must remain inside the isolated HOME and portable case roots; stop before any external or shared mutation.

## Deterministic postconditions and verification seams

1. **P1 — Candidate bound:** task 27 is successful and both candidate-targeted and full-suite receipts report exit zero for the installed revision/digest.
   **V1:** Read task 27's terminal record and the two suite receipts independently; compare their revision/digest fields byte-for-byte with the installed candidate identity and require zero exit statuses.
2. **P2 — Isolated registration:** the supported harness resolves both the Anomaly dispatcher and reviewer manifest from isolated `HOME`, while the ambient installation remains unchanged.
   **V2:** Enumerate/resolve both components with the supported harness under isolated `HOME`, then compare the pre/post read-only ambient installation inventories byte-for-byte.
3. **P3 — Complete gated output:** the case records create through detectors, draft/replay, Gate A, independent review, Gate B, report, and charts; each gate has an explicit user-approval receipt and ended its turn before downstream work.
   **V3:** Walk the durable state/event/attempt records in order and cross-check both gate receipts, report, and chart paths; require no detector event before Gate A approval and no final-output event before Gate B approval.
4. **P4 — Durable resume:** exactly one harness restart occurred after detector execution or draft creation, and the fresh session advanced from the authoritative next action without rerunning accepted work.
   **V4:** Compare the pre-stop and post-resume durable snapshots: accepted attempt IDs, hashes, and artifact references must be identical, the harness session identity must change once, and the first new event must be the recorded next action.
5. **P5 — Independent reviewer:** P5/P6 ran in a fresh context distinct from the orchestrator and produced a pre-Gate-B attestation whose draft hash equals the reviewed draft hash.
   **V5:** Compare orchestrator and reviewer context/session identities for inequality, compare attested and durable draft hashes byte-for-byte, and verify attestation ordering precedes the Gate B approval receipt.
6. **P6 — Portable, clean evidence:** every recorded case artifact path is relative, resolves beneath the case root, exists, and no case artifact contains the absolute case-root prefix or credential material.
   **V6:** Resolve each recorded relative path against the case root with containment checks, require each target to exist, then byte-scan all retained case artifacts for the exact absolute-root string and credential/token/private-key patterns with zero matches.
7. **P7 — Bounded cleanup:** isolated managed installation state is absent after uninstall, ambient state is unchanged, and the retained portable case remains readable with its state, report, and charts intact.
   **V7:** Enumerate isolated harness registrations/files and require the installed components to be absent; compare ambient inventories byte-for-byte; reopen the retained case and resolve/read its state, report, and every chart.

## Acceptance-criterion disposition

1. **Install/register candidate:** covered by runbook 1–3; verified by P1–P2/V1–V2.
2. **Complete installed workflow:** covered by runbook 4–8; verified by P3/V3.
3. **Gate ownership and turn endings:** covered by runbook 4 and 7; verified by P3/V3.
4. **Restart and authoritative resume:** covered by runbook 5–6; verified by P4/V4.
5. **Fresh reviewer and draft-hash attestation:** covered by runbook 7; verified by P5/V5.
6. **Relative paths, receipts, outputs, and secret/path hygiene:** covered by runbook 8–9; verified by P6/V6.
7. **Exact-candidate green suite and case-preserving cleanup:** covered by runbook 1 and 10; verified by P1 and P7/V1 and V7.
