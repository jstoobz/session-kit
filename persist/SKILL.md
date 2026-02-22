---
name: persist
description: Save a specific artifact from the current conversation to $SESSION_KIT_ROOT/sessions/ (default ~/.stoobz/) for future discovery via /index. Use when the user says "/persist", "save this", "keep this", "persist this", "stash this for later", or wants to capture a reference artifact (table, runbook, research doc, architecture notes, comparison, plan) without ending the session. The in-flight companion to /park.
---

# Persist

Save a reference artifact from the current conversation to `./.stoobz/` during the session. Archived to `~/.stoobz/sessions/` when you `/park`. The in-flight companion to `/park`.

> **Archive root:** Resolve `$SESSION_KIT_ROOT` (default: `~/.stoobz`). All `~/.stoobz/` paths below use this root.

```
/park     → "save everything, I'm leaving"
/persist  → "save THIS thing, I'm still here"
/index    → finds both
```

## Process

1. **Identify the artifact** — Look at recent conversation context. What did the user just produce or want to keep? Could be:
   - A table, comparison matrix, findings summary
   - A research doc or brain dump distillation
   - A runbook, playbook, or how-to
   - Architecture notes or decision records
   - A plan, checklist, or investigation notes
   - Raw output from a tool or analysis

   If ambiguous, ask: "What should I persist?" with the most likely candidates.

2. **Determine naming:**
   - `/persist` → auto-name from content (slugified heading or topic, max 50 chars)
   - `/persist <name>` → use the provided name as-is
   - `/persist <name> <tag1> <tag2>` → name + explicit tags
   - Filename: `<name>.md` (always markdown, always kebab-case)

3. **Determine project:**
   - If in a git repo: `basename $(git rev-parse --show-toplevel)`
   - Otherwise: `basename $(pwd)`

4. **Determine tags:**
   - Explicit tags from the command take priority
   - Otherwise auto-detect 2-5 tags from the artifact content
   - Languages: elixir, python, javascript, typescript, ruby, go, rust, sql, powershell, bash
   - Frameworks: phoenix, ecto, oban, react, next, absinthe, liveview
   - Topics: debugging, performance, migration, refactor, investigation, auth, deployment, testing, infrastructure, playbook, runbook, architecture, comparison

5. **Write the artifact:**
   - Path: `./.stoobz/<name>.md`
   - If file already exists, ask: "Overwrite `<name>.md` or save as `<name>-2.md`?"
   - `mkdir -p .stoobz/` if needed
   - Extract/format the content as clean markdown
   - Add a small footer: `_Persisted from <project> session — <date>_`

6. **No manifest update** — Persisted artifacts are archived to `~/.stoobz/sessions/` and added to the manifest when you `/park`. This keeps the manifest consistent with the archive.

7. **Confirm:**

```
Persisted to ./.stoobz/<name>.md
  Tags:  playbook, deployment, docker
  Note:  Archived to ~/.stoobz/sessions/ when you /park
  Find:  /index <name>  (after parking)
```

## Examples

```
User: [produces a deployment methods comparison table]
User: /persist

→ Persisted to ./.stoobz/deployment-methods.md
  Tags:  windows, deployment, comparison
  Note:  Archived to ~/.stoobz/sessions/ when you /park
```

```
User: /persist auth-flow-notes auth architecture

→ Persisted to ./.stoobz/auth-flow-notes.md
  Tags:  auth, architecture
  Note:  Archived to ~/.stoobz/sessions/ when you /park
```

```
User: /persist deploy-runbook playbook deployment

→ Persisted to ./.stoobz/deploy-runbook.md
  Tags:  playbook, deployment
  Note:  Archived to ~/.stoobz/sessions/ when you /park
```

## Rules

- **One artifact per call** — To persist multiple things, call `/persist` multiple times.
- **Always markdown** — Output is always a `.md` file. Format content cleanly.
- **Don't over-format** — Preserve the artifact's natural structure. Don't wrap a table in unnecessary headings.
- **Infer from context** — When called without a name, look at what was just discussed/produced and pick the right content and name.
- **Tags are cheap** — 2-5 tags. Better to over-tag than under-tag. These power `/index` search.
- **Local first** — Files go in `./.stoobz/` during the session. `/park` archives them to `~/.stoobz/sessions/<project>/` alongside session artifacts.
- **Don't duplicate** — If the content already exists in `./.stoobz/` (same name), update in place.
- **No session ceremony** — This isn't `/park`. No TLDR, no relay doc, no prompt lab. Just save the thing.
