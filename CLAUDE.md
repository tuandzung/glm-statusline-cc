# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What

Python powerline status line plugin for Claude Code. Dual data source: stdin JSON (context, model, lines, vim mode) + z.ai monitor API (quotas, MCP). Catppuccin theme, nerd font icons, 60s cache.

Single-file implementation: `statusline.py`. Stdlib only — no pip deps.

## Cavekit Workflow

This repo uses Cavekit spec-driven development. All workflow goes through SPEC.md:

- `/spec new|amend|bug` — mutate spec
- `/build [--all|§T.n|--next]` — implement tasks, flip status `.` → `~` → `x`
- `/check [--all|§V|§I|§T]` — drift report (read-only)
- `/ck:backprop` — bug → §B entry + §V invariant + code fix

SPEC.md uses caveman encoding (symbols, terse prose). Read FORMAT.md for the format spec.

## Commands

```bash
# Run statusline (pipe stdin JSON)
echo '{"model":{"display_name":"GLM-5.1"},"workspace":{"current_dir":"/tmp"},"context_window":{"used_percentage":45},"cost":{"total_lines_added":10,"total_lines_removed":2}}' | python3 statusline.py

# Run tests
python3 test_v10_separator.py
python3 test_v11_theme.py
python3 test_v12_ctx_catppuccin.py
```

No build step. No linter configured.

## Plugin Structure

```
.claude-plugin/
  plugin.json          # name, version, description, author
  marketplace.json     # marketplace listing (github source)
skills/
  install-statusline/SKILL.md  # /glm-statusline:install-statusline agent skill
```

Plugin version lives in `.claude-plugin/plugin.json`. When bumping, also update the cached path in `~/.claude/settings.json` statusLine.command and SKILL.md's base directory reference.

## Key Invariants (from §V)

- V1: Exit 0 always. Errors → `--` for that segment.
- V5: Cache at `~/.claude/zai-usage-cache.json`. TTL 60s success, 15s failure.
- V7: Supported domains: api.z.ai, open.bigmodel.cn, dev.bigmodel.cn.
- V9: TOKENS_LIMIT matched by position (1st=short, 2nd=long), never hardcoded unit values.
- V10: Powerline separator fg=prev segment bg, bg=next segment bg.
- V11: Theme from STATUSLINE_THEME env. `dark`→Macchiato, `light`→Latte.
- V18: No U+2009 thin space in output.
- V22: Vim mode accessed via `session["vim"]["mode"]` (nested), not `session["vim_mode"]`.

## Settings Path Resolution (V8)

Walk order: project `.claude/settings.local.json` → project `.claude/settings.json` → `~/.claude/settings.json`. First with both `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` wins.

## Commit Style

Conventional Commits. Terse. Caveman style per `/caveman:caveman-commit`.
