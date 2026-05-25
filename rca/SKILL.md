---
name: rca
description: Generate investigation artifacts for handing off a root cause analysis to a teammate. Produces INVESTIGATION_SUMMARY.md (human quick-scan), INVESTIGATION_CONTEXT.md (Claude-droppable deep context), and an evidence/ directory with raw artifacts. Use when the user says "/rca", "root cause analysis", "investigation handoff", "share findings", or needs to package debugging results for another engineer to review with their own Claude session. Unlike /handoff (human-to-human), /rca is optimized for engineer + Claude consumption with full evidence preservation.
---

# RCA — Root Cause Analysis Handoff

Package an investigation into artifacts a teammate (and their Claude) can pick up cold: a quick-scan summary, a self-contained deep-context doc, and a phase-organized `evidence/` directory with raw queries / logs / measurements. Each artifact is one call to `sk write-artifact` — the binary handles checkin, the durable write, ledger append, and cwd mirror per file. Nested rel-paths like `evidence/01-symptoms/cpu-spike.md` work out of the box.

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
   evidence/01-initial-symptoms/
   evidence/02-hypothesis-testing/
   evidence/03-root-cause/
   evidence/04-reproduction/
   ```

   Skip phase directories with no content. Name files descriptively (`slow-checkout-query-plan.md`, `cpu-spike-grafana-2026-03-12.png`, `deadlock-thread-dump.txt`); include dates where they matter.

   For each evidence file, one `sk write-artifact` call. Text content: `--content-stdin`. Pre-existing files on disk (e.g., a screenshot the user pasted to `/tmp/spike.png`): `--content-file`.

2. **Compose `$SUMMARY_BODY`** (human quick scan) using the [INVESTIGATION_SUMMARY.md format](reference/formats.md#investigation_summarymd-format).

3. **Compose `$CONTEXT_BODY`** (self-contained deep dive) using the [INVESTIGATION_CONTEXT.md format](reference/formats.md#investigation_contextmd-format). The preamble is critical — it must work without skills, tools, or prior context. Reference evidence files by their rel-path under `evidence/`.

4. **Write all artifacts.** One bash invocation block; one `sk write-artifact` call per file:

   ```bash
   sk write-artifact --skill rca --artifact INVESTIGATION_SUMMARY.md --content-stdin <<< "$SUMMARY_BODY"
   sk write-artifact --skill rca --artifact INVESTIGATION_CONTEXT.md --content-stdin <<< "$CONTEXT_BODY"

   # Per-file evidence — repeat for each. Text content composed by Claude:
   sk write-artifact --skill rca \
     --artifact "evidence/01-initial-symptoms/cpu-spike-summary.md" \
     --content-stdin <<< "$EVIDENCE_BODY_1"

   # Pre-existing file (e.g., a screenshot or log the user already saved):
   sk write-artifact --skill rca \
     --artifact "evidence/02-hypothesis-testing/deadlock-thread-dump.txt" \
     --content-file /path/to/raw/thread-dump.txt
   ```

5. **Confirm outputs and offer adjustments.** Print the full archive paths and surface any mirror warnings (`sk write-artifact` exit code `2` on a per-file mirror failure — durable writes are still good).

## Formats reference

The two markdown templates (SUMMARY + CONTEXT) live in [reference/formats.md](reference/formats.md). Load that file when composing `$SUMMARY_BODY` or `$CONTEXT_BODY`.

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

- [reference/formats.md](reference/formats.md) — SUMMARY + CONTEXT format specs
- [checkin/SKILL.md](../checkin/SKILL.md), [write-artifact-protocol.md](../write-artifact-protocol.md)
- `sk write-artifact --help`
- ADR-0005 (Skills as thin orchestrators of versioned scripts)
