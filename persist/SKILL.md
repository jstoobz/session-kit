---
name: persist
description: Save a specific artifact from the current conversation to $SESSION_KIT_ROOT/sessions/ (default ~/.stoobz/) for future discovery via /index. Use when the user says "/persist", "save this", "keep this", "persist this", "stash this for later", or wants to capture a reference artifact (table, runbook, research doc, architecture notes, comparison, plan) without ending the session. The in-flight companion to /park.

triggers: ["/persist", "save this", "keep this", "persist this", "stash this for later"]
---

# Persist

Save a reference artifact from the current conversation. Durable write lands at `~/.stoobz/sessions/<project>/<sid>-active/<name>.md`; cwd mirror at `./.stoobz/<name>.md`. The in-flight companion to `/park`.

```
/park     → "save everything, I'm leaving"
/persist  → "save THIS thing, I'm still here"
/index    → finds both
```

## Process

1. **Identify the artifact.** Look at recent conversation context — table, comparison, findings, runbook, decision record, plan, raw tool output. If ambiguous, ask the user "What should I persist?" with the most likely candidates.

2. **Determine naming**:
   - `/persist` → auto-name from content (slugified heading or topic, max 50 chars, kebab-case)
   - `/persist <name>` → use the provided name as-is (slugify to kebab-case)
   - `/persist <name> <tag1> <tag2> ...` → name + explicit tags

   Resolve a final `NAME` (no extension) and `TAGS` (list, possibly empty).

3. **Check for cwd-mirror collision.** Read `./.stoobz/<NAME>.md`. If it exists, ask: "Overwrite `<NAME>.md` or save as `<NAME>-2.md`?" If the user picks the next-number suffix, advance `NAME` (try `-2`, `-3`, ... — pick the first non-existing). For cross-session collisions in the same project's archive (different session-id), the ledger preserves both; no overwrite ambiguity at the durable layer.

4. **Infer / accept tags** (2-5 items). Explicit tags from the command take priority; otherwise auto-detect from content:
   - Languages: elixir, python, javascript, typescript, ruby, go, rust, sql, powershell, bash
   - Frameworks: phoenix, ecto, oban, react, next, absinthe, liveview
   - Topics: debugging, performance, migration, refactor, investigation, auth, deployment, testing, infrastructure, playbook, runbook, architecture, comparison

5. **Compose `PERSIST_BODY`** as clean markdown. Preserve the artifact's natural structure (table, prose, code blocks). No footer; metadata belongs in headers.

6. **Single bash invocation** — interpolate `NAME` and the resolved `TAGS` list (already deduped to a CSV string). `sk write-artifact --tags` merges-dedupes the CSV into the manifest entry's `tags[]`; passing an empty string is a no-op:

   ```bash
   TAGS_CSV="alpha,beta,gamma"   # comma-joined from the resolved TAGS list; "" if none
   sk write-artifact --skill persist --artifact "$NAME.md" \
     --content-stdin --tags "$TAGS_CSV" <<< "$PERSIST_BODY"
   ```

7. **Confirm to operator** — print the resolved name, archive path, tags (now durably attached to the manifest entry, mergeable with later `/park` auto-detection), and the post-`/park` find hint:

   ```
   Persisted to .stoobz/<NAME>.md
     Tags:  <comma-separated>   (merged into manifest tags[])
     Note:  Archived to ~/.stoobz/sessions/ when you /park
     Find:  /index <tag-or-name>
   ```

   (The actual archive path is printed by `sk write-artifact`; the tags / find hint come from Claude on top.)

## Examples

```
User: [produces a deployment-methods comparison table]
User: /persist

→ NAME=deployment-methods, TAGS=[windows, deployment, comparison]
→ sk write-artifact --skill persist --artifact deployment-methods.md \
    --content-stdin --tags "windows,deployment,comparison" <<< "$PERSIST_BODY"
→ Persisted to .stoobz/deployment-methods.md
    Tags:  windows, deployment, comparison   (merged into manifest tags[])
    Note:  Archived to ~/.stoobz/sessions/ when you /park
```

```
User: /persist auth-flow-notes auth architecture

→ NAME=auth-flow-notes, TAGS=[auth, architecture]
→ sk write-artifact --skill persist --artifact auth-flow-notes.md \
    --content-stdin --tags "auth,architecture" <<< "$PERSIST_BODY"
```

```
User: /persist deploy-runbook playbook deployment
(prior ./.stoobz/deploy-runbook.md exists)

→ Ask: "Overwrite deploy-runbook.md or save as deploy-runbook-2.md?"
→ User: "save as -2"
→ sk write-artifact --skill persist --artifact deploy-runbook-2.md \
    --content-stdin --tags "playbook,deployment" <<< "$PERSIST_BODY"
```

## Exit Codes

`sk write-artifact` returns:

| Code | Meaning | Caller behavior |
|------|---------|-----------------|
| `0` | Durable write + mirror both succeeded | Done |
| `1` | Durability failure | Surface error; do not claim success |
| `2` | Durable write succeeded; cwd mirror failed | Mention the warning; archive is authoritative |
| `3` | Usage error (bad args, absolute path, `..` in name) | Fix the resolved name |

## Rules

- **One artifact per call** — to persist multiple things, call `/persist` multiple times.
- **Always markdown** — output is always a `.md` file; format content cleanly.
- **Don't over-format** — preserve the artifact's natural structure; don't wrap a table in unnecessary headings.
- **Infer from context** — when called without a name, look at what was just discussed / produced and pick the right content and name.
- **Tags are cheap** — 2-5 tags; better to over-tag. They flow into the manifest entry's `tags[]` array via `sk write-artifact --tags`, merge-deduped with anything already there. Both `/persist` (explicit tags) and `/park` (auto-detected from TLDR content via `sk park-finalize --tags`) merge into the same `tags[]` field, so a session that runs several `/persist` calls before `/park` accumulates the union of every tag set — discoverable via `/index <tag>`.
- **No session ceremony** — this isn't `/park`. No TLDR, no relay doc, no prompt lab. Just save the thing.
- The canonical write location is `<active-archive>/<NAME>.md`; `cwd/.stoobz/<NAME>.md` is the best-effort mirror.
- The ledger entry's `name` is `<NAME>.md`.

## See also

- [checkin/SKILL.md](../checkin/SKILL.md), [write-artifact-protocol.md](../write-artifact-protocol.md)
- `sk write-artifact --help`
- ADR-0005 (Skills as thin orchestrators of versioned scripts)
