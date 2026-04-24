# GLM StatusLine

Powerline status line for Claude Code. Dual data source: stdin JSON (context, model, lines) + z.ai monitor API (quotas, MCP). Catppuccin theme. Nerd font icons.

## Segments

```
[folder] proj main [sparkle] GLM-5.1 [brain] [●●●●○○○○] 80% [clock] 5h 30% 2h [calendar] 7d 12% 5d [plug] MCP 5% [+/-] +42/-18
```

| Segment | Info |
|---------|------|
| CWD + git | Project folder and branch |
| Model | Display name from Claude Code |
| Context | Usage % with progress bar (green/yellow/red) |
| 5h quota | Short-window token usage + reset countdown |
| 7d quota | Long-window token usage + reset countdown |
| MCP | Time-limit (MCP) usage % |
| Diff | Lines added/removed |

## Install

### Option 1: Plugin directory (recommended)

```bash
# Add to ~/.claude/settings.json
claude config set --global statusLine.command "python3 /path/to/glm-statusline-cc/statusline.py"
claude config set --global statusLine.refreshInterval 60
```

### Option 2: Plugin install via marketplace

```bash
# Add marketplace
claude plugin marketplace add tuandzung/glm-statusline-cc

# Install plugin
claude plugin install glm-statusline@glm-plugins
```

Then configure statusLine in `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "command": "python3 ${CLAUDE_PLUGIN_ROOT}/statusline.py",
    "refreshInterval": 60
  }
}
```

### Option 3: Agent install

Run `/glm-statusline:install-statusline` — the skill writes the config for you.

## Theme

Set `STATUSLINE_THEME` env var in your settings:

| Value | Theme |
|-------|-------|
| `dark` (default) | Catppuccin Macchiato |
| `light` | Catppuccin Latte |

```json
{
  "env": {
    "STATUSLINE_THEME": "dark"
  }
}
```

## Requirements

- Python 3 (stdlib only, no pip)
- Nerd font (e.g. JetBrains Mono Nerd Font)
- z.ai API credentials (ANTHROPIC_BASE_URL + AUTH_TOKEN) for quota segments

## License

MIT
