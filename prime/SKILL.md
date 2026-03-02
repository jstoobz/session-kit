---
name: prime
description: Bootstrap a repository with expert skills and context files for productive Claude sessions. Analyzes codebase architecture, proposes domain-specific expert roles, creates SKILL.md files with references, and wires up feature/debug context loaders. Use when starting in a new repo ("/prime", "bootstrap this repo", "set up expert skills"), when skills are stale ("/prime --refresh"), or when the user wants to create expert roles for a codebase they'll work in repeatedly.
---

# Prime

Analyze a codebase and generate expert skills + context files that make every future session productive. Run once to set up, `--refresh` to keep current.

```
/prime            → first-time: analyze repo, create expert skills + contexts
/prime --refresh  → update stale skills based on what changed since last prime
```

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

## Session Check-In (silent — before main process)

On first invocation of any session-kit skill in this session, register the active session in the manifest. See [session-checkin.md](../session-checkin.md) for the full protocol. Summary:

1. Detect session ID from most recently modified `.jsonl` in `~/.claude/projects/$(pwd | tr '/' '-')/` (fallback: git root encoding). If detection fails, skip silently.
2. Read `$SESSION_KIT_ROOT/manifest.json` (create if missing).
3. If no entry with this `session_id` exists → create active registration (`status: "active"`, `session_id`, `return_to`, `started_at`, `last_activity`, `last_exchange`, `skills_used`, nulls for label/summary/archive_path).
4. If entry exists → update `last_activity`, `last_exchange`, append this skill to `skills_used`.
5. Write manifest. Proceed to main process. No output about check-in.

## How It Fits

```
First time:   /prime → /pickup → [work] → /park
Returning:    /pickup → [work] → /park
Stale repo:   /prime --refresh → /pickup → [work] → /park
```

`/prime` creates the permanent knowledge layer (expert skills). `/pickup` loads session-specific context. Different layers of the same system.

## Phase 1: Foundation

Establish the current state of the repo and any existing skills.

### 1a. CLAUDE.md Check

```
CLAUDE.md exists?
├── No → Run /init to generate it. Read the result as baseline.
├── Yes → Check staleness:
│   ├── Count commits since CLAUDE.md last modified
│   ├── If >10 commits behind → recommend update:
│   │   "CLAUDE.md is N commits stale. Quick refresh before proceeding?"
│   │   If user agrees → re-run /init to update, read result
│   │   If user declines → read existing CLAUDE.md as-is
│   └── If fresh → read as baseline
```

### 1b. Existing Skills Check

```
Scan .claude/skills/ for */SKILL.md files
├── No skills found → fresh setup, proceed to Phase 2
├── Skills found → report what exists:
│   "Found N existing expert skills: {list with descriptions}"
│   For each skill, check staleness:
│     git log --oneline --since="skill-mtime" -- <relevant-paths> | wc -l
│     "{skill-name} covers {paths} — {N} commits since last update"
│   Ask: "Create fresh skills or update existing ones?"
```

### 1c. Stack Detection

Identify the technology stack from project files:

| Marker | Stack |
|--------|-------|
| `package.json` | Node/React/Vue/Angular (check dependencies) |
| `*.csproj` / `*.sln` | .NET (check TargetFramework for version) |
| `mix.exs` | Elixir/Phoenix |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `Gemfile` | Ruby/Rails |
| `pyproject.toml` / `requirements.txt` | Python |
| `pom.xml` / `build.gradle` | Java/Kotlin |

Note hybrid stacks (e.g., .NET backend + React frontend).

## Phase 2: Deep Analysis

Launch parallel background agents to analyze each architectural layer. Use the Task tool with `subagent_type=Explore` and `run_in_background=true`.

**Agent assignment based on detected stack.** Examples:

| Stack | Agents to Launch |
|-------|-----------------|
| .NET + React | Backend (.NET patterns, controllers, services, data), Frontend (React patterns, components, state), Auth/Config (middleware, env config) |
| Elixir/Phoenix | Domain (contexts, schemas, queries), Web (controllers, views, channels), Infrastructure (config, deployment, telemetry) |
| React SPA | Components (patterns, state mgmt), API layer (services, hooks), Build/Config (webpack, env, CI) |
| Go microservice | Handlers (HTTP, gRPC), Domain (models, services), Infrastructure (config, deployment) |

**Each agent should analyze:**
- Key patterns and conventions (with file paths)
- How things are wired together (DI, routing, middleware)
- Non-obvious architectural decisions
- Common gotchas a developer would hit
- Domain vocabulary

**Launch 2-4 agents** — enough for coverage, not so many they're redundant. While agents run, read key files yourself to build understanding. Synthesize agent results when they complete.

## Phase 3: Skill Boundary Proposal (Approval Gate)

Based on analysis, propose expert roles to the user. Present:

```
Based on the analysis, I recommend N expert skills:

1. {repo}-expert — {what it covers: architecture, domain vocab, key patterns}
2. {repo}-{layer}-expert — {what it covers: specific layer patterns}
3. {repo}-auth-expert — {if auth is complex enough to warrant its own skill}

And 2 context files:
- {repo}-feature-context — loads all experts for feature development
- {repo}-debug-context — loads relevant experts + debugging decision tree

Does this look right, or should I adjust the boundaries?
```

**Guidelines for proposing skills:**

- **1 skill = 1 mental model.** Each skill should represent a distinct area of expertise that a developer would think of as a unit.
- **Minimum 2, maximum 5 expert skills.** 1 is too broad, 6+ is fragmented.
- **Always propose feature + debug contexts.** These are the primary entry points.
- **Name pattern:** `{repo}-expert` for main, `{repo}-{layer}-expert` for specialized.
- **Don't create a skill for something Claude already knows well** (e.g., generic React patterns). Only for project-specific knowledge.

**Wait for user approval before proceeding.**

## Phase 4: Creation

Write the skill files following progressive disclosure:

### SKILL.md Structure (for each expert skill)

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

### Context Files

Feature context:
```markdown
Load the following expert contexts for {repo} feature development:

/{skill-1} — {brief description}
/{skill-2} — {brief description}

Use these together when implementing features spanning {layers}.

## Key Reminders
{Critical gotchas and patterns to keep top of mind}
```

Debug context:
```markdown
Load the following expert contexts for {repo} debugging:

/{skill-1} — {brief description}
/{skill-2} — {brief description}

## Investigation Approach
{Symptom → cause → location mapping}
{Key files for debugging table}
```

### Reference Files

Move detailed code examples, integration patterns, and extensive configuration docs into `references/*.md`. Keep SKILL.md under 300 lines.

## Phase 5: Placement

### Detect Existing Structure

```
Check .claude/skills/ for symlinks:
├── Symlinks found → detect source:
│   readlink on any symlink → extract the skill-hosting repo path
│   Ask: "Skills are symlinked from {path}. Create there?"
│   ├── Yes → create in detected path, run link script if present
│   └── No → create directly in .claude/skills/
├── No symlinks → create directly in:
│   .claude/skills/{skill-name}/SKILL.md
│   .claude/commands/contexts/{context-name}.md
```

### Post-Creation

- Verify all files are readable through their final paths
- Summary: what was created, where it lives, usage instructions

```
Created N expert skills and 2 contexts:

Skills:
  .claude/skills/{skill-1}/SKILL.md + references/
  .claude/skills/{skill-2}/SKILL.md

Contexts:
  .claude/commands/contexts/{repo}-feature-context.md
  .claude/commands/contexts/{repo}-debug-context.md

Usage:
  /prime --refresh     to update when the codebase evolves
  /{skill-1}           to load specific expert knowledge
  /contexts/{repo}-feature-context  for full-stack feature work
  /contexts/{repo}-debug-context    for debugging
```

## Refresh Mode (`--refresh`)

When called with `--refresh`:

1. **Skip Phase 1a** (don't re-run /init unless CLAUDE.md is very stale)
2. **Run Phase 1b** — check existing skills against git activity
3. **Targeted Phase 2** — only launch agents for layers with significant changes:
   ```
   For each existing skill:
     git diff --stat $(stat -f %Sm SKILL.md) -- <covered-paths>
     If >20 files changed or >5 commits → re-analyze that layer
     Otherwise → skip, skill is current
   ```
4. **Phase 3** — propose updates as diffs, not full rewrites:
   ```
   {skill-name}: 2 new sections, 1 updated section
   - Added: New background job pattern (CMSWebsite/Jobs/NewJob.cs)
   - Updated: Controller patterns (new base class added)
   - Unchanged: Domain vocabulary, Auth flow
   ```
5. **Phase 4** — update only changed sections, preserve unchanged content
6. **Phase 5** — verify placement (should already be wired)

## Rules

- **One question at a time** during approval gates. Don't overwhelm.
- **Use parallel agents aggressively** in Phase 2 — this is the expensive step, parallelize it.
- **Don't create skills for generic knowledge** — only project-specific patterns Claude wouldn't know.
- **Progressive disclosure** — SKILL.md stays lean (<300 lines), details in references/.
- **Respect existing work** — in refresh mode, update surgically. Don't rewrite what's still accurate.
- **Name skills after the repo** — `{repo}-expert`, not generic names like `backend-expert`.
- **Always create both contexts** — feature and debug are the minimum useful set.
