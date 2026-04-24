#!/usr/bin/env python3
"""GLM StatusLine — Powerline status line for Claude Code with z.ai quota data."""

import json
import os
import sys
import http.client
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────

CACHE_PATH = Path.home() / ".claude" / "zai-usage-cache.json"
CACHE_TTL_OK = 60_000       # ms
CACHE_TTL_FAIL = 15_000     # ms
API_TIMEOUT = 2             # seconds
AUTOCOMPACT_BUFFER = 0.225

SUPPORTED_DOMAINS = ("api.z.ai", "open.bigmodel.cn", "dev.bigmodel.cn")

RESET = "\x1b[0m"

# ── T13: Theme dicts (V11) ────────────────────────────────────────────────

THEME_DARK = {
    "vim":     "\x1b[48;5;117m",  # Sky #89dceb
    "cwd":     "\x1b[48;5;111m",  # Blue #8aadf4
    "model":   "\x1b[48;5;183m",  # Mauve #c6a0f6
    "quota5":  "\x1b[48;5;147m",  # Lavender #b4befe
    "quota7":  "\x1b[48;5;116m",  # Sapphire #7dc4e4
    "mcp":     "\x1b[48;5;152m",  # Teal #8bd5ca
    "diff":    "\x1b[48;5;216m",  # Peach #fab387
    "fg":      "\x1b[38;5;17m",   # Base #1e2030
    "ctx_bg":  {"green": "\x1b[48;5;150m", "yellow": "\x1b[48;5;223m", "red": "\x1b[48;5;210m"},
    "bar":     {"filled": "\x1b[38;5;17m", "empty": "\x1b[38;5;60m"},
}

THEME_LIGHT = {
    "vim":     "\x1b[48;5;32m",   # Sky #04a5e5
    "cwd":     "\x1b[48;5;27m",   # Blue #1e66f5
    "model":   "\x1b[48;5;99m",   # Mauve #8839ef
    "quota5":  "\x1b[48;5;69m",   # Lavender #7287fd
    "quota7":  "\x1b[48;5;31m",   # Sapphire #209fb5
    "mcp":     "\x1b[48;5;30m",   # Teal #179299
    "diff":    "\x1b[48;5;208m",  # Peach #fe640b
    "fg":      "\x1b[38;5;231m",  # Base #eff1f5
    "ctx_bg":  {"green": "\x1b[48;5;70m", "yellow": "\x1b[48;5;172m", "red": "\x1b[48;5;161m"},
    "bar":     {"filled": "\x1b[38;5;231m", "empty": "\x1b[38;5;146m"},
}


def resolve_theme():
    """Read STATUSLINE_THEME env, return theme dict. V11: dark default."""
    val = os.environ.get("STATUSLINE_THEME", "").strip().lower()
    if val == "light":
        return THEME_LIGHT
    return THEME_DARK


# Nerd font icons
ICON_FOLDER = " "
ICON_BRANCH = " "
ICON_SPARKLE = " "
ICON_BRAIN = " "
ICON_CLOCK = " "
ICON_CALENDAR = " "
ICON_PLUG = " "
ICON_PLUS = " "
ICON_MINUS = " "
# Vim mode icons (V21)
ICON_VIM_NORMAL = " "
ICON_VIM_INSERT = " "
ICON_VIM_VISUAL = " "
ICON_VIM_REPLACE = " "
ICON_VIM_COMMAND = " "
# Powerline separator
SEPARATOR = ""

# V21: mode string → icon
VIM_ICONS = {
    "NORMAL": ICON_VIM_NORMAL,
    "INSERT": ICON_VIM_INSERT,
    "VISUAL": ICON_VIM_VISUAL,
    "REPLACE": ICON_VIM_REPLACE,
    "COMMAND": ICON_VIM_COMMAND,
}


# ── T2: Settings reader (V8) ──────────────────────────────────────────────

def read_env_from_settings():
    """Walk settings files per V8, return (base_url, auth_token) or (None, None)."""
    home = os.environ.get("HOME", "")
    cwd = os.getcwd()
    candidates = [
        os.path.join(cwd, ".claude", "settings.local.json"),
        os.path.join(cwd, ".claude", "settings.json"),
        os.path.join(home, ".claude", "settings.json"),
    ]
    for path in candidates:
        try:
            with open(path) as f:
                cfg = json.load(f)
            env = cfg.get("env", {})
            base = env.get("ANTHROPIC_BASE_URL")
            token = env.get("ANTHROPIC_AUTH_TOKEN")
            if isinstance(base, str) and isinstance(token, str):
                return base, token
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return None, None


# ── T3: API client (V4) ──────────────────────────────────────────────────

def build_api_urls(base_url):
    """Extract protocol+host, validate domain per V7, return API URLs or None."""
    try:
        parsed = urllib.parse.urlparse(base_url)
        domain = parsed.hostname
        if not any(d in (domain or "") for d in SUPPORTED_DOMAINS):
            return None
        base = f"{parsed.scheme}://{parsed.netloc}"
        return {
            "quota": f"{base}/api/monitor/usage/quota/limit",
            "model": f"{base}/api/monitor/usage/model-usage",
            "tool":  f"{base}/api/monitor/usage/tool-usage",
        }
    except Exception:
        return None


def api_get(url, token, params=None, timeout=API_TIMEOUT):
    """HTTPS GET with timeout. Returns parsed JSON or None on failure (V4)."""
    conn = None
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        if params:
            path += "?" + urllib.parse.urlencode(params)
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=timeout)
        conn.request("GET", path, headers={
            "Authorization": token,
            "Accept-Language": "en-US,en",
            "Content-Type": "application/json",
        })
        resp = conn.getresponse()
        if resp.status != 200:
            return None
        return json.loads(resp.read().decode())
    except Exception:
        return None
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


# ── T4: Cache (V5) ───────────────────────────────────────────────────────

def load_cache():
    """Load cache, return data dict or None."""
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text())
    except Exception:
        pass
    return None


def save_cache(data):
    """Save cache to disk."""
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data))
    except Exception:
        pass


def get_cached_or_none():
    """Return cached data if within TTL, else None."""
    cache = load_cache()
    if not cache or "timestamp" not in cache:
        return None
    age = _now_ms() - cache["timestamp"]
    ttl = CACHE_TTL_FAIL if cache.get("api_unavailable") else CACHE_TTL_OK
    return cache if age < ttl else None


# ── T5: Quota fetcher ────────────────────────────────────────────────────

def fetch_quotas(urls, token):
    """Fetch quota limit API → {token_5h: {pct, reset}, token_7d: {pct, reset}, mcp: pct}."""
    result = {
        "5h": {"pct": 0, "reset_ms": None},
        "7d": {"pct": 0, "reset_ms": None},
        "mcp": 0,
    }
    data = api_get(urls["quota"], token)
    if not data or not data.get("success"):
        return result
    limits = (data.get("data") or {}).get("limits") or []
    token_idx = 0
    for lim in limits:
        pct = round(lim.get("percentage", 0))
        if lim.get("type") == "TOKENS_LIMIT":
            entry = {"pct": pct, "reset_ms": lim.get("nextResetTime")}
            if token_idx == 0:
                result["5h"] = entry
            elif token_idx == 1:
                result["7d"] = entry
            token_idx += 1
        elif lim.get("type") == "TIME_LIMIT":
            result["mcp"] = pct
    return result


# ── T6: Context usage ────────────────────────────────────────────────────

def calc_context_pct(ctx):
    """Calculate context usage % from stdin context_window. Returns 0 if missing."""
    if not ctx:
        return 0
    native = ctx.get("used_percentage")
    if isinstance(native, (int, float)) and native > 0:
        return min(100, max(0, round(native)))
    size = ctx.get("context_window_size")
    if not size or size <= 0:
        return 0
    total = (ctx.get("total_input_tokens") or 0) + (ctx.get("total_output_tokens") or 0)
    buf = size * AUTOCOMPACT_BUFFER
    return min(100, round(((total + buf) / size) * 100))


# ── T7: Git branch ───────────────────────────────────────────────────────

def read_git_branch():
    """Read .git/HEAD → branch name, or empty string."""
    try:
        head = Path(os.getcwd()) / ".git" / "HEAD"
        content = head.read_text().strip()
        prefix = "ref: refs/heads/"
        if content.startswith(prefix):
            return content[len(prefix):]
    except Exception:
        pass
    return ""


# ── T8: Powerline renderer (V6) ──────────────────────────────────────────

def segment(icon, text, bg, fg):
    """Render a powerline segment: bg + fg icon + text."""
    return f"{bg}{fg} {icon} {text} "


def bg_to_fg(bg_code):
    """Convert bg escape code (48;5) to fg escape code (38;5)."""
    return bg_code.replace("48;5;", "38;5;")


def join_segments(*segs_with_bg):
    """Join segments with powerline separators.

    segs_with_bg: list of (rendered_segment_str, bg_code_for_separator)
    """
    parts = []
    for i, (seg, bg) in enumerate(segs_with_bg):
        if i > 0:
            prev_bg = segs_with_bg[i - 1][1]
            parts.append(f"{bg_to_fg(prev_bg)}{bg}{SEPARATOR}")
        parts.append(seg)
    if segs_with_bg:
        last_bg = segs_with_bg[-1][1]
        parts.append(f"{bg_to_fg(last_bg)}\x1b[48;5;0m{SEPARATOR}{RESET}")
    return "".join(parts)



# ── T9: Progress bar (V3) ────────────────────────────────────────────────

def progress_bar(pct, theme, width=10):
    """Colored progress bar per V3. Filled=Base, empty=Surface2."""
    filled = round((pct / 100) * width)
    empty = width - filled
    return f"{theme['bar']['filled']}{'●' * filled}{theme['bar']['empty']}{'○' * empty}"


def context_bg(pct, theme):
    """Return bg color for context segment based on pct (V3)."""
    if pct > 80:
        return theme["ctx_bg"]["red"]
    elif pct >= 50:
        return theme["ctx_bg"]["yellow"]
    return theme["ctx_bg"]["green"]


# ── T10: Countdown formatter ─────────────────────────────────────────────

def format_countdown(ms_timestamp):
    """ms timestamp → 'Xh Xm' or 'Xm' or '--'."""
    if not ms_timestamp:
        return "--"
    diff = ms_timestamp - _now_ms()
    if diff <= 0:
        return "0m"
    hours = int(diff // 3_600_000)
    minutes = int((diff % 3_600_000) // 60_000)
    if hours > 0 and minutes > 0:
        return f"{hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h"
    return f"{minutes}m"


# ── T11: Assemble ────────────────────────────────────────────────────────

def build_output(session, quotas, theme):
    """Assemble all segments into final powerline line."""
    fg = theme["fg"]
    segments = []

    # Vim mode (V21) — icon only, hidden if null/missing
    vim_mode = _safe(lambda: session["vim_mode"])
    vim_icon = VIM_ICONS.get(vim_mode) if vim_mode else None
    if vim_icon:
        segments.append((segment(vim_icon, "", theme["vim"], fg), theme["vim"]))

    # CWD + git
    cwd = _safe(lambda: Path(session["workspace"]["current_dir"]).name) or os.path.basename(os.getcwd())
    branch = read_git_branch()
    cwd_text = f"{cwd} {ICON_BRANCH} {branch}" if branch else cwd
    segments.append((segment(ICON_FOLDER, cwd_text, theme["cwd"], fg), theme["cwd"]))

    # Model
    model = _safe(lambda: session["model"]["display_name"]) or "--"
    segments.append((segment(ICON_SPARKLE, model, theme["model"], fg), theme["model"]))

    # Context
    ctx = session.get("context_window")
    ctx_pct = calc_context_pct(ctx)
    bar = progress_bar(ctx_pct, theme)
    ctx_bg_c = context_bg(ctx_pct, theme)
    segments.append((f"{ctx_bg_c}{fg} {ICON_BRAIN} {bar} {fg}{ctx_pct}% ", ctx_bg_c))

    # 5h quota
    q5 = quotas.get("5h", {})
    q5_pct = q5.get("pct", 0)
    q5_reset = format_countdown(q5.get("reset_ms"))
    segments.append((segment(ICON_CLOCK, f"{q5_pct}% {q5_reset}", theme["quota5"], fg), theme["quota5"]))

    # 7d quota
    q7 = quotas.get("7d", {})
    q7_pct = q7.get("pct", 0)
    q7_reset = format_countdown(q7.get("reset_ms"))
    segments.append((segment(ICON_CALENDAR, f"{q7_pct}% {q7_reset}", theme["quota7"], fg), theme["quota7"]))

    # MCP
    mcp = quotas.get("mcp", 0)
    segments.append((segment(ICON_PLUG, f"{mcp}%", theme["mcp"], fg), theme["mcp"]))

    # Lines diff
    cost = session.get("cost") or {}
    added = cost.get("total_lines_added") or 0
    removed = cost.get("total_lines_removed") or 0
    segments.append((segment(f"{ICON_PLUS}/{ICON_MINUS}", f"+{added}/-{removed}", theme["diff"], fg), theme["diff"]))

    return join_segments(*segments)


# ── Main (T1) ────────────────────────────────────────────────────────────

def _now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _safe(fn):
    try:
        return fn()
    except (KeyError, TypeError, IndexError):
        return None


def main():
    # Read stdin (V1)
    session = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            session = json.loads(raw)
    except Exception:
        pass

    # Read env (V8)
    base_url, token = read_env_from_settings()
    urls = build_api_urls(base_url) if base_url else None

    # Try cache first (V5)
    quotas = None
    cached = get_cached_or_none()
    if cached and "quotas" in cached:
        quotas = cached["quotas"]

    # Fetch from API if no cache
    api_unavailable = False
    if quotas is None and urls and token:
        quotas = fetch_quotas(urls, token)
        if quotas:
            save_cache({"quotas": quotas, "timestamp": _now_ms()})
        else:
            api_unavailable = True
            save_cache({"quotas": {"5h": {"pct": 0, "reset_ms": None}, "7d": {"pct": 0, "reset_ms": None}, "mcp": 0}, "timestamp": _now_ms(), "api_unavailable": True})

    if quotas is None:
        quotas = {"5h": {"pct": 0, "reset_ms": None}, "7d": {"pct": 0, "reset_ms": None}, "mcp": 0}

    # Build and print (V11)
    theme = resolve_theme()
    output = build_output(session, quotas, theme)
    print(output)


if __name__ == "__main__":
    main()
