# Evidence for host commands

Use this guide when reviewing an agent that runs commands through a host, VM,
container, remote shell, or terminal wrapper. A transport receipt, an observed
effect, and acceptance of the requested task are separate claims.

This is documentation guidance for implementers and reviewers. It adds no UAEK
runtime behavior, evidence schema, CLI option, retry gate, or `unknown` state.
Here, **unknown** is a descriptive outcome when available observations cannot
establish what happened. See the [verification framework](../../skills/verification-framework.md)
for the existing verification workflow and its indeterminate result.

## Separate the claims

| Evidence | What it establishes | What still needs checking |
| --- | --- | --- |
| Host receipt: return code, stdout, stderr, timeout or disconnect | What the host transport reported | Whether the intended process ran on the intended target and what it changed |
| Target observations: process identity, output, state readback | The specific effects observed at that time | Whether those effects satisfy the requested behavior and cleanup requirements |
| Acceptance result against explicit criteria | The behavior covered by those criteria | Other targets, untested failure paths, long-running reliability, and later versions |

An error or timeout can arrive after a command has already produced effects.
An exit code of zero also needs task-specific readback. Preserve conflicting
observations instead of replacing them with a single success flag.

## Establish the target and identity

Before a consequential command, match the intended target to an authoritative
inventory using an unambiguous identifier; a display name alone may be ambiguous.
Within the execution context, verify UID, primary GID, supplementary groups,
`HOME`, and working directory against the intended account. A correct username
alone does not establish a complete login identity.

Record the relevant tool/runtime versions and target identity in private evidence.
Use placeholders or sanitized summaries in shared reports. Keep each observation
associated with the target and session that produced it.

## Reconcile uncertain execution before retrying

After an error, disconnect, cancellation, or timeout, inspect the intended
postcondition and relevant process state through a bounded observation. Report
confirmed effects separately from unknown effects. A missing receipt is not
proof that nothing ran; absence of a partial output is not proof of rollback.

Do not blindly replay a mutation. First determine whether the requested effect
already occurred and whether the operation is safe to repeat. If that cannot be
established, retain the unknown outcome and stop dependent mutations. Any retry
requires the host's applicable authorization and a deliberate repeat-safety
decision. This guide does not provide automatic reconciliation or retry control.

## Preserve file evidence at the right layer

| Layer | Record | Limit |
| --- | --- | --- |
| Archived original | Hash of the exact saved report, log, source file, or fixture | Proves the saved bytes; a report hash does not verify its claims |
| Transfer | Completion receipt and complete expected-range coverage, where applicable | Proves the recorded transfer condition; does not supply an independent source digest |
| Content verification | Independently obtained source digest, destination digest, coverage and timing | Matching digests support the checked content only; identify unread or unverified regions |
| Metadata policy | File identity, size, timestamps and their before/after verification window; permitted differences | Content equality does not establish metadata equality or a stable source window |

Retain interrupted, incomplete, malformed, gap, overlap, and metadata-change
cases. Two fixtures can have identical content hashes and different metadata
that makes one a necessary negative case. Preserve earlier unknown or failed
stages even when a later verification succeeds.

## Suggested acceptance cases

These are review criteria, not tests executed by this document. Adapt them to an
authorized, isolated target; inspect any fixture or helper before using it.

| Case | Required observation |
| --- | --- |
| Intended account and target | Identity, groups, `HOME`, and working directory match expectations; ambiguous or mismatched targets are rejected before execution |
| Unicode and literal arguments | Non-ASCII text, spaces, quotes, newlines, empty strings, and shell metacharacters survive argument transport without unintended expansion or side effects |
| Deliberate command failure | The guest/process failure code and stderr remain distinguishable from transport failure; they are not replaced by wrapper success |
| Ctrl-C in a persistent terminal | The intended process stops, the session remains usable if required, and termination and cleanup are observed; sending Ctrl-C alone is insufficient |
| Timeout or lost receipt | Postcondition and process observations distinguish completed, failed, partial, and unknown outcomes; a mutation is not automatically repeated |
| Changed file during verification | The check detects or explicitly leaves unknown a changed identity/metadata window; byte equality alone does not pass the stability criterion |

## Report historical and current results separately

For each claim, state its criteria, evidence source, date, environment, outcome,
and scope limit. Label an archived result **historical, not rerun** when it was
only inspected. Label a suggested case **not executed** until current evidence
exists. Keep negative results and cleanup failures beside positive results.
Local fixtures, byte checks, and selected terminal probes establish only the
behavior they cover; they do not establish full host integration or model quality.

Reading an archive is not authorization to execute its scripts. Current
acceptance needs a reviewed procedure and current observations. Follow the
[evidence methodology](../methodology.md) when stating the strength of a result.
