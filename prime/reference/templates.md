# Prime — Output Templates

The file templates Phase 4 of [../SKILL.md](../SKILL.md) writes. Load this file when
creating skill or context files.

## SKILL.md structure (for each expert skill)

```markdown
---
name: {skill-name}
description: {what it covers and when to use it}
---

# {Skill Title}

## Technology Stack
{Key technologies with versions — correct common assumptions}

## Architecture Overview
{The "big picture" that requires reading multiple files to understand}
{Non-obvious patterns, integration points, architectural decisions}

## Key Patterns
{How things are done in this codebase — with code examples}
{Decision trees: "if you need to do X, look in Y"}

## Domain Vocabulary
{Business terms and their technical meaning}

## Adding Features Checklist
{Step-by-step for common tasks in this layer}

## Key Gotchas
{Traps for developers unfamiliar with the codebase}

## Key Files
{Map of important files and their purpose}

## References
{Links to references/ files for detailed patterns and examples}
```

## Feature context

```markdown
Load the following expert contexts for {repo} feature development:

/{skill-1} — {brief description}
/{skill-2} — {brief description}

Use these together when implementing features spanning {layers}.

## Key Reminders
{Critical gotchas and patterns to keep top of mind}
```

## Debug context

```markdown
Load the following expert contexts for {repo} debugging:

/{skill-1} — {brief description}
/{skill-2} — {brief description}

## Investigation Approach
{Symptom → cause → location mapping}
{Key files for debugging table}
```

## Reference files

Move detailed code examples, integration patterns, and extensive configuration docs into
`references/*.md`. Keep each generated SKILL.md under 300 lines.
