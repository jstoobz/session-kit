# Prime — Stack Lookup Tables

Lookup data for Phases 1d and 3 of [../SKILL.md](../SKILL.md). Load this file when
generating `.claudeignore` entries or proposing hooks.

## `.claudeignore` patterns by stack (Phase 1d)

| Stack | Patterns |
|-------|----------|
| Elixir/Phoenix | `deps/`, `_build/`, `priv/static/assets/`, `.elixir_ls/`, `*.beam` |
| Node/React/Vue/Angular | `node_modules/`, `dist/`, `.next/`, `build/`, `.nuxt/`, `coverage/` |
| Python | `__pycache__/`, `.venv/`, `venv/`, `*.pyc`, `.pytest_cache/`, `dist/`, `build/` |
| Rust | `target/` |
| Go | `vendor/` (only if directory exists) |
| Ruby/Rails | `vendor/bundle/` |
| .NET | `bin/`, `obj/`, `packages/` |
| Java/Kotlin | `target/`, `build/`, `.gradle/` |
| All stacks | `*.log`, `.DS_Store` |

## Suggested hooks by stack (Phase 3)

Include only hooks for linters/formatters that are present in the repo (check `mix.exs`,
`package.json`, `pyproject.toml`, etc. for the tool before suggesting it):

| Stack | Hook | Trigger | Command |
|-------|------|---------|---------|
| Elixir | Format enforcement | `PreToolUse: Bash(git commit *)` | `mix format` |
| Elixir (if `credo` in deps) | Style check | `PreToolUse: Bash(git commit *)` | `mix credo --strict` |
| Node/TS (if lint script exists) | Lint check | `PreToolUse: Bash(git commit *)` | `npm run lint` |
| Node/TS (if `prettier` in devDeps) | Format check | `PreToolUse: Bash(git commit *)` | `npx prettier --check .` |
| Python (if `ruff` present) | Lint check | `PreToolUse: Bash(git commit *)` | `ruff check .` |
| Python (if `black` present) | Format check | `PreToolUse: Bash(git commit *)` | `black --check .` |
| Rust | Format check | `PreToolUse: Bash(git commit *)` | `cargo fmt --check` |
| Ruby (if `.rubocop.yml` exists) | Style check | `PreToolUse: Bash(git commit *)` | `rubocop` |

## Hook format for `settings.json` (on approval, via `/update-config`)

```json
"hooks": {
  "PreToolUse": [{
    "matcher": "Bash(git commit *)",
    "hooks": [{ "type": "command", "command": "{command}" }]
  }]
}
```
