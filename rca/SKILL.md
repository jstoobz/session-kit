---
name: rca
description: Generate investigation artifacts for handing off a root cause analysis to a teammate. Produces INVESTIGATION_SUMMARY.md (human quick-scan), INVESTIGATION_CONTEXT.md (Claude-droppable deep context), and an evidence/ directory with raw artifacts. Use when the user says "/rca", "root cause analysis", "investigation handoff", "share findings", or needs to package debugging results for another engineer to review with their own Claude session. Unlike /handoff (human-to-human), /rca is optimized for engineer + Claude consumption with full evidence preservation.
---

# RCA — Root Cause Analysis Handoff

Package an investigation into artifacts that let a teammate and their Claude pick up exactly where you left off — with full evidence, reasoning, and unexplored paths.

## Artifacts Produced

| File                       | Audience                   | Purpose                                                                           |
| -------------------------- | -------------------------- | --------------------------------------------------------------------------------- |
| `INVESTIGATION_SUMMARY.md` | Human (quick scan)         | 2-minute overview: what, why, confidence level, recommended action                |
| `INVESTIGATION_CONTEXT.md` | Human + Claude (deep dive) | Full investigation with preamble — drop the path, Claude walks through it         |
| `evidence/`                | Claude (raw artifacts)     | Query results, logs, stack traces, screenshots — organized by investigation phase |

## Process

1. **Create `evidence/` directory** — Persist raw artifacts from the session. Organize logically:

   ```
   evidence/
   ├── 01-initial-symptoms/     # What we observed that triggered the investigation
   ├── 02-hypothesis-testing/   # Queries, logs, metrics for each hypothesis
   ├── 03-root-cause/           # The evidence that confirmed/supports the finding
   └── 04-reproduction/         # Reproduction steps, test results, before/after
   ```

   Name files descriptively: `slow-checkout-query-plan.md`, `cpu-spike-grafana-mar12.png`, `deadlock-thread-dump.txt`. Include timestamps where relevant. Skip numbered directories that have no content — only create directories with actual evidence.

2. **Write `INVESTIGATION_SUMMARY.md`** — Human-first, quick scan format.

3. **Write `INVESTIGATION_CONTEXT.md`** — The crown jewel. Self-contained, no skill dependencies. Another engineer drops the path to this file into their Claude and it just works.

4. **Confirm outputs and offer adjustments.**

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

The preamble is critical — it makes this file work without any skill setup.

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

{What went wrong, when it started, what the observable symptoms are. Include metrics,
error messages, user reports — whatever triggered the investigation. Be specific enough
that someone unfamiliar can understand the severity.}

## Investigation Approach

{How this was investigated. What tools, queries, environments were used. This gives the
reader confidence in the methodology and helps them understand what data is available.}

### Tools & Access Used

- {e.g., "SSH into UAT app server for live process inspection"}
- {e.g., "Direct queries against the read model database via psql"}
- {e.g., "APM traces for the billing pipeline"}

## Findings

### Root Cause Analysis

{Detailed explanation of what we believe is happening and why. Walk through the causal
chain from trigger to symptom. Include code paths, module names, and line references
where applicable.}

**Confidence:** {low | medium | high} — {why this confidence level}

### Supporting Evidence

{For each piece of evidence, describe what it shows and why it matters. Reference files
in evidence/ for the raw data.}

1. **{Evidence title}** — {what it shows}
   - Source: `evidence/{path}`
   - Significance: {why this matters to the conclusion}

2. **{Evidence title}** — {what it shows}
   - Source: `evidence/{path}`
   - Significance: {why this matters}

### Reproduction

{Steps to reproduce, if applicable. Include any test code written to prove the hypothesis.
If reproduction wasn't possible, explain why and what was done instead.}

## Alternative Hypotheses

### Explored and Ruled Out

{Hypotheses that were investigated and dismissed, with evidence for why.}

| Hypothesis                    | Evidence Against      | Effort                    |
| ----------------------------- | --------------------- | ------------------------- |
| {What we thought it might be} | {Why we ruled it out} | {Brief — what we checked} |

### Considered but Not Explored

{Hypotheses worth investigating but not pursued in this session. Include reasoning for
why they were deprioritized and what investigating them would look like.}

- **{Hypothesis}** — {Why it's plausible, why we didn't pursue, what exploring it requires}

### Currently Still Investigating

{Active threads that don't have conclusions yet. Include current status and next step.}

- **{Thread}** — {Current status, what the next step is}

## Affected Components

{Key files, modules, services, databases involved. Specific enough for someone to navigate the codebase.}

| Component               | Role in Issue              | File/Module                               |
| ----------------------- | -------------------------- | ----------------------------------------- |
| {e.g., Payment service} | {e.g., Timeout under load} | {e.g., `src/services/payment_service.ts`} |

## Environment Details

{Relevant environment state: versions, config, feature flags, recent deploys — anything that could affect reproduction or fix verification.}

## Recommended Next Steps

1. {Actionable step with enough context to execute}
2. {Actionable step}

---

_Investigation context generated {date}. Evidence artifacts in `./evidence/`._
_Original investigation conducted by {user} in a Claude Code session._
```

## Rules

- **Evidence is non-negotiable** — If there are no raw artifacts, prompt the user: "What evidence should we persist? Paste query results, logs, screenshots, or tell me what to capture."
- **Self-contained** — The context file must work without any skills, tools, or prior context. Another engineer + a fresh Claude session is the target.
- **Confidence calibration** — Be honest about confidence levels. "Suspected" with medium confidence is more useful than a false "confirmed."
- **No Claude session artifacts** — Strip references to skills, prompts, session mechanics. The recipient doesn't need to know how we work.
- **Preserve raw evidence** — Summaries in the markdown, raw data in evidence/. Never throw away the originals.
- **Descriptive file names** — `evidence/oban-job-queue-depth-feb6.md` not `evidence/data1.txt`
- **Skip empty sections** — If nothing was ruled out, omit "Explored and Ruled Out." If nothing is still being investigated, omit that section.
- **Tell the recipient about their own persistence** — The preamble should note that their Claude session can create `INVESTIGATION_REVIEW/` alongside evidence/ to persist their own analysis. This is mentioned in the preamble's Claude instructions.
- Write to the current working directory unless the user specifies a different path
