# RCA Artifact Formats

Format specifications for the two markdown artifacts `/rca` produces. The skill body in `../SKILL.md` references this file rather than inlining the templates.

## INVESTIGATION_SUMMARY.md Format

Human quick scan. Two-minute read.

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

Self-contained deep dive. The preamble makes this work without any skill setup — a teammate drops the file path into their own Claude session and walks the investigation cold.

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
