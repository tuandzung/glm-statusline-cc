---
description: Configure GLM StatusLine in Claude Code settings
allowed-tools:
  - Read
  - Write
  - Bash
---

# install-statusline

Configure GLM StatusLine in Claude Code settings.

## Instructions

Read `~/.claude/settings.json`. If missing, create it with `{}`.

Merge the following into the existing JSON (preserve all existing keys):

```json
{
  "statusLine": {
    "command": "python3 ${CLAUDE_PLUGIN_ROOT}/statusline.py",
    "refreshInterval": 60
  }
}
```

If running as a plugin (CLAUDE_PLUGIN_ROOT is set), use the template above.

If running standalone (no plugin), use the absolute path to `statusline.py` instead of `${CLAUDE_PLUGIN_ROOT}/statusline.py`. Ask the user for the path if unsure.

Write the merged result back to `~/.claude/settings.json`.

Confirm to the user what was written.
