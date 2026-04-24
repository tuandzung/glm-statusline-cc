# SPEC — GLM StatusLine (Python)

## §G — Goal
Python powerline status line for Claude Code. Dual data source: stdin JSON (context, model, lines) + z.ai monitor API (quotas, MCP). Nerd font icons. 60s cache. Color-coded context bar.

## §C — Constraints
- Python 3, stdlib only (json, sys, os, datetime, http.client, urllib.parse, pathlib)
- Read JSON from stdin (Claude Code session context) + call z.ai API for quota data
- ANSI 256-color codes for segment fg/bg
- Color theme: Catppuccin Macchiato (dark, default) or Catppuccin Latte (light). Select via env var `STATUSLINE_THEME` (values: `dark`|`light`). Missing/invalid → dark.
- Powerline separator `` (U+E0B0) between segments
- Context progress bar: green < 50%, yellow 50–80%, light red > 80%
- Null/missing → `--`, never crash
- File cache at `~/.claude/zai-usage-cache.json`, TTL 60s success / 15s failure
- API timeout 2s, fail gracefully
- refreshInterval: 60 in settings.json
- Claude Code plugin format: `.claude-plugin/plugin.json` manifest
- Plugin uses `${CLAUDE_PLUGIN_ROOT}/statusline.py` for path resolution
- Marketplace manifest: `.claude-plugin/marketplace.json` for distribution via GitHub

## §I — Interfaces
| id | surface | notes |
|----|---------|-------|
| I.stdin | Claude Code statusLine JSON | model, workspace, context_window, cost |
| I.api-quota | `GET {baseDomain}/api/monitor/usage/quota/limit` | Auth: `Authorization: {token}` |
| I.api-model | `GET {baseDomain}/api/monitor/usage/model-usage?startTime=...&endTime=...` | Auth: same |
| I.api-tool | `GET {baseDomain}/api/monitor/usage/tool-usage?startTime=...&endTime=...` | Auth: same |
| I.settings | `~/.claude/settings.json` → env.ANTHROPIC_BASE_URL, env.ANTHROPIC_AUTH_TOKEN | also check project-level .claude/settings.json |
| I.git | Read `.git/HEAD` from cwd, parse `ref: refs/heads/` prefix | returns empty string if detached/not a git repo |
| I.plugin-manifest | `.claude-plugin/plugin.json` | name, version, description, author, repository, license |
| I.marketplace-manifest | `.claude-plugin/marketplace.json` | lists plugin with github source for marketplace distribution |
| I.plugin-install | `claude plugin install glm-statusline@marketplace` or `claude --plugin-dir ./` | user installs plugin, then sets statusLine.command |
| I.plugin-skill | `skills/install-statusline/SKILL.md` | YAML frontmatter: description + allowed-tools (Read, Write, Bash). Body: agent configure instructions |

### I.stdin — JSON shape
```
{
  "model": { "id": str, "display_name": str },
  "workspace": { "current_dir": str },
  "context_window": { "used_percentage": float?, "context_window_size": int?, "total_input_tokens": int?, "total_output_tokens": int? },
  "cost": { "total_lines_added": int?, "total_lines_removed": int? }
}
```

### I.api-quota — Response shape
```json
{
  "code": 200, "success": true,
  "data": {
    "limits": [
      { "type": "TOKENS_LIMIT", "unit": 5, "number": N, "percentage": float, "nextResetTime": ms_timestamp?, "usageDetails": [...] },
      { "type": "TOKENS_LIMIT", "unit": 168, ... },
      { "type": "TIME_LIMIT", "percentage": float, ... }
    ]
  }
}
```
- unit values are **unstable** across API versions. Match by position: 1st TOKENS_LIMIT = short window, 2nd = long window. Never hardcode unit=N.
- `TIME_LIMIT` = MCP usage percentage

### I.api-tool — Response shape
```json
{
  "data": { "list": [{ "toolName": str, "usageCount": int }] }
}
```

## §V — Invariants
- **V1**: Script exits 0 always. Errors → display `--` for that segment, never crash.
- **V2**: Null/missing fields → `--`. No KeyError, no unhandled exception.
- **V3**: Context segment bg gradient: `<50%` Green (#a6da95), `50–80%` Yellow (#eed49f), `>80%` Red (#ed8796). Bar: `●` filled + `○` empty, width 10. Bar filled = theme Base, bar empty = theme Surface2.
- **V4**: API calls have 2s timeout. On failure → use cache or show `--`.
- **V5**: Cache file `~/.claude/zai-usage-cache.json`. TTL 60s success, 15s failure.
- **V6**: Each segment: nerd font icon + value. Segments separated by powerline `` with bg color transition.
- **V7**: `ANTHROPIC_BASE_URL` → extract protocol+host → build API URLs. Supported domains: api.z.ai, open.bigmodel.cn, dev.bigmodel.cn.
- **V8**: Read settings from: project `.claude/settings.local.json` → project `.claude/settings.json` → `~/.claude/settings.json`. First with both ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN wins.
- **V9**: ∀ TOKENS_LIMIT parsing → match by position (1st=short, 2nd=long), not hardcoded unit values. API unit schema may change.
- **V10**: Powerline separator `` (U+E0B0): fg = prev segment bg color, bg = next segment bg color. ∀ adjacent segments (A,B): separator fg = A.bg number, bg = B.bg number.
- **V11**: Theme resolved at startup from `STATUSLINE_THEME` env var. `dark` → Macchiato, `light` → Latte. Missing/invalid → dark. No runtime switching.
- **V12**: ∀ theme ctx_bg.{green,yellow,red} color numbers must match theme's Catppuccin accent 256 codes (dark: 150/223/210, light: 70/172/161). No arbitrary ANSI picks for context bg.
- **V13**: `.claude-plugin/plugin.json` exists with `name`, `version`, `description` fields. Valid JSON.
- **V14**: `statusline.py` at plugin root. `statusLine.command` refs `${CLAUDE_PLUGIN_ROOT}/statusline.py`. No hardcoded paths.
- **V15**: `.claude-plugin/marketplace.json` lists plugin with `source.source: "github"` pointing to this repo.
- **V16**: README has setup instructions: install command + settings.json config for statusLine.command.
- **V17**: `skills/install-statusline/SKILL.md` exists. Instructs agent to write `statusLine.command` + `refreshInterval` to `~/.claude/settings.json`.
- **V18**: ∀ segments → icon padded with thin space (U+2009) each side: ` {icon} {text}`. Separator between icon+text. No trailing space before segment end.
- **V19**: ∀ `ICON_*` constants → trailing space appended. Normalizes variable-width nerd font glyphs to consistent visual width.
- **V20**: `SKILL.md` ! have YAML frontmatter with `description` and `allowed-tools` fields. `allowed-tools` lists Read, Write, Bash.

## §T — Tasks
| id | status | desc | deps |
|----|--------|------|------|
| T1 | x | Scaffold: `#!/usr/bin/env python3`, read stdin JSON, main(), print output | I.stdin |
| T2 | x | Read env: walk settings files per V8, extract ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN | V8 |
| T3 | x | API client: `api_get(url, token, params, timeout=2)` using http.client | V4 |
| T4 | x | Cache: load/save `~/.claude/zai-usage-cache.json`, TTL check per V5 | V5 |
| T5 | x | Fetch quota: GET /api/monitor/usage/quota/limit → parse 5h (1st TOKENS_LIMIT), 7d (2nd TOKENS_LIMIT), MCP (TIME_LIMIT) | I.api-quota,V9,T4 |
| T6 | x | Context usage: from stdin `used_percentage`, fallback calc from total_tokens / context_window_size | I.stdin |
| T7 | x | Git branch: read `.git/HEAD`, parse `ref: refs/heads/` prefix, empty on detached | I.git |
| T8 | x | Powerline renderer: `segment(icon, text, bg, fg)` + `separator(prev_bg, next_bg)` | V6 |
| T9 | x | Progress bar: `bar(pct, width=10)` with color per V3 | V3 |
| T10 | x | Countdown formatter: ms timestamp → "Xh Xm" or "Xm" | V5 |
| T11 | x | Assemble segments: cwd+git, model, context+bar, 5h-quota, 7d-quota, mcp, lines +/- | T5–T10 |
| T12 | x | Wire settings.json: statusLine.command → `python3 /path/to/statusline.py`, refreshInterval=60 | I.settings |
| T13 | x | Theme switcher: read STATUSLINE_THEME env, select Macchiato/Latte color dicts, pass to renderer | V11 |
| T14 | x | Create `.claude-plugin/plugin.json` with name, version, description, author, repository, license | V13,I.plugin-manifest |
| T15 | x | Create `.claude-plugin/marketplace.json` with github source entry | V15,I.marketplace-manifest |
| T16 | x | Write README: install command, settings.json config, theme env var, screenshot placeholder | V16,I.plugin-install |
| T17 | x | Create `skills/install-statusline/SKILL.md` with agent install instructions | V17,I.plugin-skill |
| T18 | x | Thin space (U+2009) padding around icons in `segment()`. Change ` {icon} {text} ` → ` {icon} {text} `. Update context segment too. | V18 |
| T19 | x | Append trailing space to all `ICON_*` constants in statusline.py. Normalize variable-width glyph rendering. | V19 |
| T20 | x | Bump plugin.json version 1.0.0 → 1.0.1 | V13 |
| T21 | x | Add YAML frontmatter (description, allowed-tools) to SKILL.md | V20,I.plugin-skill |

## §S — Segment layout (left → right)
```
[ ] proj  main  [ ] GLM-5.1  [  ] [●●●●○○○○] 80%  [ ] 5h 30% ↺2h  [ ] 7d 12% ↺5d  [󰌟] MCP 5%  [ ] +42/-18
```

Nerd font icons:
- ` ` U+E5FF — folder (cwd)
- `󰊢` U+E725 — git branch
- ` ` U+F4B8 — sparkles (model)
- `` U+E28C — brain (context)
- ` ` U+F017 — clock (5h quota)
- ` ` U+F073 — calendar (7d quota)
- `󰌟` U+E31F — plug (MCP)
- ` ` U+F457 — plus / ` ` U+F458 — minus (lines diff)

Segment bg colors (Catppuccin accent):
| segment | Dark (Macchiato) | Light (Latte) |
|---------|-------------------|----------------|
| cwd | Blue #8aadf4 (256:111) | Blue #1e66f5 (256:27) |
| model | Mauve #c6a0f6 (256:183) | Mauve #8839ef (256:99) |
| context | dynamic (V3, accent bg) | dynamic (V3, accent bg) |
| 5h | Lavender #b4befe (256:147) | Lavender #7287fd (256:69) |
| 7d | Sapphire #7dc4e4 (256:116) | Sapphire #209fb5 (256:31) |
| mcp | Teal #8bd5ca (256:152) | Teal #179299 (256:30) |
| diff | Peach #fab387 (256:216) | Peach #fe640b (256:208) |

Dark fg: Base #1e2030 (256:17). Light fg: Base #eff1f5 (256:231).
Dark bar fills: Base 17 (filled), Surface2 60 (empty). Light bar fills: Base 231 (filled), Surface2 146 (empty).
Dark context bg: Green 150, Yellow 223, Red 210. Light context bg: Green 70, Yellow 172, Red 161.

## §B — Bugs
| id | date | cause | fix |
|----|------|-------|-----|
| B1 | 2026-04-23 | API unit values changed (5→3, 168→6), code hardcoded old values → quota 0% | V9 |
| B2 | 2026-04-23 | Powerline separator fg=white instead of next-bg → broken visual transition | V10 |
| B3 | 2026-04-24 | V10 stated wrong direction: fg=next-bg instead of fg=prev-bg. Code used bg escape (48;5) not fg (38;5) for separator → inherited FG_WHITE | V10 |
| B4 | 2026-04-24 | Context bg used arbitrary ANSI colors (28/142/160) not Catppuccin accent → looked generic | V12 |
