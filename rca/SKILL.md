---
name: rca
description: Generate investigation artifacts for handing off a root cause analysis to a teammate. Produces INVESTIGATION_SUMMARY.md (human quick-scan), INVESTIGATION_CONTEXT.md (Claude-droppable deep context), and an evidence/ directory with raw artifacts. Use when the user says "/rca", "root cause analysis", "investigation handoff", "share findings", or needs to package debugging results for another engineer to review with their own Claude session. Unlike /handoff (human-to-human), /rca is optimized for engineer + Claude consumption with full evidence preservation.
---

# RCA — Root Cause Analysis Handoff

Package an investigation into artifacts a teammate (and their Claude) can pick up cold: a quick-scan summary, a self-contained deep-context doc, and a phase-organized `evidence/` directory with raw queries / logs / measurements. Each artifact is one call to `sk write-artifact` — the binary handles checkin, the durable write, ledger append, and cwd mirror per file. Nested rel-paths like `rca/evidence/01-symptoms/cpu-spike.md` work out of the box.

## Artifacts Produced

| File                             | Audience                   | Purpose                                                                           |
| -------------------------------- | -------------------------- | --------------------------------------------------------------------------------- |
| `INVESTIGATION_SUMMARY.md`       | Human (quick scan)         | 2-minute overview: what, why, confidence, recommended action                      |
| `INVESTIGATION_CONTEXT.md`       | Human + Claude (deep dive) | Full investigation with preamble — drop the path, Claude walks through it         |
| `evidence/NN-phase/<file>`       | Claude (raw artifacts)     | Query results, logs, stack traces, screenshots — organized by investigation phase |

All three land under the active archive (`~/.stoobz/sessions/<project>/<sid>-active/`) and the cwd mirror (`./.stoobz/`). The ledger records every file individually with its full rel-path.

## Process

1. **Compose evidence first.** Walk the investigation chronologically. Each piece of evidence (query result, log excerpt, metric snapshot, stack trace) gets its own file under a numbered phase directory:

   ```
   rca/evidence/01-initial-symptoms/
   rca/evidence/02-hypothesis-testing/
   rca/evidence/03-root-cause/
   rca/evidence/04-reproduction/
   ```

   Skip phase directories with no content. Name files descriptively (`slow-checkout-query-plan.md`, `cpu-spike-grafana-2026-03-12.png`, `deadlock-thread-dump.txt`); include dates where they matter.

   For each evidence file, one `sk write-artifact` call. Text content: `--content-stdin`. Pre-existing files on disk (e.g., a screenshot the user pasted to `/tmp/spike.png`): `--content-file`.

2. **Compose `SUMMARY_BODY`** (human quick scan) in the [INVESTIGATION_SUMMARY.md Format](#investigation_summarymd-format) below.

3. **Compose `CONTEXT_BODY`** (self-contained deep dive) in the [INVESTIGATION_CONTEXT.md Format](#investigation_contextmd-format) below. The preamble is critical — it must work without skills, tools, or prior context. Reference evidence files by their rel-path under `evidence/`.

4. **Write all artifacts.** One bash invocation block; one `sk write-artifact` call per file:

   ```bash
   sk write-artifact --skill rca --artifact INVESTIGATION_SUMMARY.md --content-stdin <<< "$SUMMARY_BODY"
   sk write-artifact --skill rca --artifact INVESTIGATION_CONTEXT.md --content-stdin <<< "$CONTEXT_BODY"

   # Per-file evidence — repeat for each. Text content composed by Claude:
   sk write-artifact --skill rca \
     --artifact "evidence/01-initial-symptoms/cpu-spike-summary.md" \
     --content-stdin <<< "$EVIDENCE_BODY_1"

   # Pre-existing file (e.g., a screenshot or log file the user already saved):
   sk write-artifact --skill rca \
     --artifact "evidence/02-hypothesis-testing/deadlock-thread-dump.txt" \
     --content-file /path/to/raw/thread-dump.txt
   ```

5. **Confirm outputs and offer adjustments.** Print the full archive paths and surface any mirror warnings (`sk write-artifact` exit code `2` on a per-file mirror failure — durable writes are still good).

## INVESTIGATION_SUMMARY.md Format

```markdown
# Investigation: {Descriptive title}

**Date:** {YYYY-MM-DD}
**Investigator:** {user}
**Ticket:** {Jira ticket if applicable}
**Environment:** {prod/UAT/QA/local}
**Status:** {investigating | suspected | confirmed | fix-in-progress}
**Confidence:** {low | medium | high}

---

## Symptoms

{What was observed — concrete data points, not "things were slow"}

## Root Cause

{1-3 sentences. State whether confirmed or suspected. Include the mechanism.}

## Evidence

{3-5 bullet points of the most compelling evidence. Reference evidence/ files.}

## Impact

{Who/what is affected and how severely}

## Recommended Action

1. {Immediate action with rationale}
2. {Follow-up action}

## Open Questions

- {Anything unresolved that the next person should investigate}

---

_Investigation summary generated {date} — see INVESTIGATION_CONTEXT.md for full analysis._
```

## INVESTIGATION_CONTEXT.md Format

The preamble makes this file work without any skill setup.

```markdown
# Investigation Context: {Descriptive title}

> **For the engineer reading this:** This is a complete investigation package. You can
> drop the path to this file into a Claude session and ask it to walk you through the
> findings, challenge assumptions, explore alternative explanations, or help you verify
> the conclusions. All evidence is in the `evidence/` directory alongside this file.
>
> **For Claude:** You are reviewing a structured investigation conducted by another
> engineer and their Claude session. Your role is to help the current engineer understand
> the analysis, answer questions about methodology and evidence, identify gaps or
> alternative explanations the original investigator may have missed, and assist with
> verification or next steps. Reference the evidence/ directory for raw data. Do not
> accept conclusions uncritically — examine the evidence and reasoning independently.
>
> **Persistence:** As you work through this investigation with the engineer, persist your
> own findings, questions, and analysis in an `INVESTIGATION_REVIEW/` directory alongside
> `evidence/`. This preserves your independent analysis as a complementary artifact.

**Date:** {YYYY-MM-DD}
**Investigator:** {user}
**Ticket:** {Jira ticket if applicable}
**Environment:** {prod/UAT/QA/local}
**Branch:** {git branch if applicable}

---

## Problem Statement

{What went wrong, when it started, observable symptoms. Include metrics, error messages,
user reports. Be specific enough that someone unfamiliar can understand the severity.}

## Investigation Approach

{How this was investigated. Tools, queries, environments. Gives the reader confidence in
the methodology and a map of what data is available.}

### Tools & Access Used

- {e.g., "SSH into UAT app server for live process inspection"}
- {e.g., "Direct queries against the read model database via psql"}
- {e.g., "APM traces for the billing pipeline"}

## Findings

### Root Cause Analysis

{Detailed explanation of what's happening and why. Walk the causal chain from trigger to
symptom. Include code paths, module names, line references where applicable.}

**Confidence:** {low | medium | high} — {why this confidence level}

### Supporting Evidence

1. **{Evidence title}** — {what it shows}
   - Source: `evidence/{path}`
   - Significance: {why this matters to the conclusion}

### Reproduction

{Steps to reproduce, if applicable. Include any test code written to prove the hypothesis.
If reproduction wasn't possible, explain why and what was done instead.}

## Alternative Hypotheses

### Explored and Ruled Out

| Hypothesis                    | Evidence Against      | Effort                    |
| ----------------------------- | --------------------- | ------------------------- |
| {What we thought it might be} | {Why we ruled it out} | {Brief — what we checked} |

### Considered but Not Explored

- **{Hypothesis}** — {Why it's plausible, why we didn't pursue, what exploring it requires}

### Currently Still Investigating

- **{Thread}** — {Current status, what the next step is}

## Affected Components

| Component               | Role in Issue              | File/Module                               |
| ----------------------- | -------------------------- | ----------------------------------------- |
| {e.g., Payment service} | {e.g., Timeout under load} | {e.g., `src/services/payment_service.ts`} |

## Environment Details

{Versions, config, feature flags, recent deploys — anything that could affect reproduction
or fix verification.}

## Recommended Next Steps

1. {Actionable step with enough context to execute}

---

_Investigation context generated {date}. Evidence artifacts in `./.stoobz/evidence/`._
_Original investigation conducted by {user} in a Claude Code session._
```

## Exit Codes

`sk write-artifact` returns per-call:

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Durable write + mirror both succeeded | Continue to next file |
| `1` | Durability failure on this file | Surface error; do not claim success for any later files in the same RCA batch unless you can recover |
| `2` | Durable write succeeded; cwd mirror failed | Mention the warning; archive is authoritative; continue |
| `3` | Usage error (bad rel-path, missing content source) | Fix and retry the offending call |

## Rules

- **Evidence is non-negotiable** — if there are no raw artifacts to capture, prompt the user: "What evidence should we persist? Paste query results, logs, screenshots, or tell me what to capture."
- **Self-contained** — the context file must work without any skills, tools, or prior context. Another engineer + a fresh Claude session is the target.
- **Confidence calibration** — be honest about confidence levels. "Suspected" with medium confidence beats a false "confirmed."
- **No Claude session artifacts** — strip references to skills, prompts, session mechanics.
- **Preserve raw evidence** — summaries in the markdown, raw data in evidence/. Never throw away originals.
- **Descriptive file names** — `evidence/oban-job-queue-depth-2026-02-06.md` not `evidence/data1.txt`.
- **Skip empty sections** — no "Explored and Ruled Out" if nothing was ruled out.
- **Tell the recipient about their own persistence** — the preamble notes that the receiving Claude can create `INVESTIGATION_REVIEW/` alongside `evidence/` to persist its own analysis.
- The canonical write location is `<active-archive>/...`; `cwd/.stoobz/...` is the best-effort mirror.
- Ledger entries carry the full rel-path (`evidence/01-symptoms/foo.md`), not the leaf name.

## See also

- [checkin/SKILL.md](../checkin/SKILL.md), [write-artifact-protocol.md](../write-artifact-protocol.md)
- `sk write-artifact --help`
- [ADR-0005](~/.stoobz/kb/adr/0005-skills-as-thin-orchestrators-of-versioned-scripts.md)
