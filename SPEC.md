# SPEC — GLM StatusLine (Python)

## §G — Goal
Python powerline status line for Claude Code. Dual data source: stdin JSON (context, model, lines) + z.ai monitor API (quotas, MCP). Nerd font icons. 60s cache. Color-coded context bar.

## §C — Constraints
- Python 3, stdlib only (json, sys, os, datetime, http.client, urllib.parse, pathlib)
- Read JSON from stdin (Claude Code session context) + call z.ai API for quota data
- ANSI 256-color codes for segment fg/bg
- Powerline separator `` (U+E0B0) between segments
- Context progress bar: green < 50%, yellow 50–80%, light red > 80%
- Null/missing → `--`, never crash
- File cache at `~/.claude/zai-usage-cache.json`, TTL 60s success / 15s failure
- API timeout 2s, fail gracefully
- refreshInterval: 60 in settings.json

## §I — Interfaces
| id | surface | notes |
|----|---------|-------|
| I.stdin | Claude Code statusLine JSON | model, workspace, context_window, cost |
| I.api-quota | `GET {baseDomain}/api/monitor/usage/quota/limit` | Auth: `Authorization: {token}` |
| I.api-model | `GET {baseDomain}/api/monitor/usage/model-usage?startTime=...&endTime=...` | Auth: same |
| I.api-tool | `GET {baseDomain}/api/monitor/usage/tool-usage?startTime=...&endTime=...` | Auth: same |
| I.settings | `~/.claude/settings.json` → env.ANTHROPIC_BASE_URL, env.ANTHROPIC_AUTH_TOKEN | also check project-level .claude/settings.json |
| I.git | Read `.git/HEAD` from cwd | fallback: `git rev-parse --abbrev-ref HEAD` |

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
- **V3**: Context bar gradient: `<50%` green (#008700), `50–80%` yellow (#afaf00), `>80%` light red (#ff6b6b). Bar: `█` filled + `░` empty, width 10.
- **V4**: API calls have 2s timeout. On failure → use cache or show `--`.
- **V5**: Cache file `~/.claude/zai-usage-cache.json`. TTL 60s success, 15s failure.
- **V6**: Each segment: nerd font icon + value. Segments separated by powerline `` with bg color transition.
- **V7**: `ANTHROPIC_BASE_URL` → extract protocol+host → build API URLs. Supported domains: api.z.ai, open.bigmodel.cn, dev.bigmodel.cn.
- **V8**: Read settings from: project `.claude/settings.local.json` → project `.claude/settings.json` → `~/.claude/settings.json`. First with both ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN wins.
- **V9**: ∀ TOKENS_LIMIT parsing → match by position (1st=short, 2nd=long), not hardcoded unit values. API unit schema may change.
- **V10**: Powerline separator: fg = next segment bg. ∀ adjacent segments (A,B): `A.bg + B.bg + `.

## §T — Tasks
| id | status | desc | deps |
|----|--------|------|------|
| T1 | x | Scaffold: `#!/usr/bin/env python3`, read stdin JSON, main(), print output | I.stdin |
| T2 | x | Read env: walk settings files per V8, extract ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN | V8 |
| T3 | x | API client: `api_get(url, token, params, timeout=2)` using http.client | V4 |
| T4 | x | Cache: load/save `~/.claude/zai-usage-cache.json`, TTL check per V5 | V5 |
| T5 | x | Fetch quota: GET /api/monitor/usage/quota/limit → parse 5h (1st TOKENS_LIMIT), 7d (2nd TOKENS_LIMIT), MCP (TIME_LIMIT) | I.api-quota,V9,T4 |
| T6 | x | Context usage: from stdin `used_percentage`, fallback calc from total_tokens / context_window_size | I.stdin |
| T7 | x | Git branch: read `.git/HEAD`, parse `ref: refs/heads/` prefix | I.git |
| T8 | x | Powerline renderer: `segment(icon, text, bg, fg)` + `separator(prev_bg, next_bg)` | V6 |
| T9 | x | Progress bar: `bar(pct, width=10)` with color per V3 | V3 |
| T10 | x | Countdown formatter: ms timestamp → "Xh Xm" or "Xm" | V5 |
| T11 | x | Assemble segments: cwd+git, model, context+bar, 5h-quota, 7d-quota, mcp, lines +/- | T5–T10 |
| T12 | x | Wire settings.json: statusLine.command → `python3 /path/to/statusline.py`, refreshInterval=60 | I.settings |

## §S — Segment layout (left → right)
```
[ ] proj  main  [ ] GLM-5.1  [  ] [████████░░] 80%  [ ] 5h 30% ↺2h  [ ] 7d 12% ↺5d  [󰌟] MCP 5%  [ ] +42/-18
```

Nerd font icons:
- ` ` U+E5FF — folder (cwd)
- `󰊢` U+E725 — git branch
- ` ` U+F4B8 — sparkles (model)
- ` ` U+F5DC — brain (context)
- ` ` U+F017 — clock (5h quota)
- ` ` U+F073 — calendar (7d quota)
- `󰌟` U+E31F — plug (MCP)
- ` ` U+F457 — plus / ` ` U+F458 — minus (lines diff)

Segment bg colors:
- cwd: #5f5faf | model: #0087af | context: dynamic (V3) | 5h: #875faf | 7d: #005f87 | mcp: #5f8700 | diff: #875f5f
- All fg: #eeeeee (white)

## §B — Bugs
| id | date | cause | fix |
|----|------|-------|-----|
| B1 | 2026-04-23 | API unit values changed (5→3, 168→6), code hardcoded old values → quota 0% | V9 |
| B2 | 2026-04-23 | Powerline separator fg=white instead of next-bg → broken visual transition | V10 |
