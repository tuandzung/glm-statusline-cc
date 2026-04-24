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

# Segment bg colors (256-color)
BG_CWD     = "\x1b[48;5;61m"   # #5f5faf
BG_MODEL   = "\x1b[48;5;31m"   # #0087af
BG_QUOTA5  = "\x1b[48;5;97m"   # #875faf
BG_QUOTA7  = "\x1b[48;5;24m"   # #005f87
BG_MCP     = "\x1b[48;5;64m"   # #5f8700
BG_DIFF    = "\x1b[48;5;95m"   # #875f5f
FG_WHITE   = "\x1b[38;5;254m"  # #eeeeee

# Dynamic context bg colors
BG_GREEN   = "\x1b[48;5;22m"   # #008700
BG_YELLOW  = "\x1b[48;5;142m"  # #afaf00 (dark yellow for bg readability)
BG_RED     = "\x1b[48;5;210m"  # light red

# Bar colors (fg)
FG_BAR_GREEN  = "\x1b[38;5;76m"
FG_BAR_YELLOW = "\x1b[38;5;226m"
FG_BAR_RED    = "\x1b[38;5;210m"
FG_BAR_EMPTY  = "\x1b[38;5;245m"

# Nerd font icons
ICON_FOLDER  = ""
ICON_BRANCH  = ""
ICON_SPARKLE = ""
ICON_BRAIN   = ""
ICON_CLOCK   = ""
ICON_CALENDAR = ""
ICON_PLUG    = ""
ICON_PLUS    = ""
ICON_MINUS   = ""

# Powerline separator
SEPARATOR = ""


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

def segment(icon, text, bg, fg=FG_WHITE):
    """Render a powerline segment: bg + fg icon + text."""
    return f"{bg}{fg} {icon} {text} "


def join_segments(*segs_with_bg):
    """Join segments with powerline separators.

    segs_with_bg: list of (rendered_segment_str, bg_code_for_separator)
    """
    parts = []
    for i, (seg, bg) in enumerate(segs_with_bg):
        if i > 0:
            prev_bg = segs_with_bg[i - 1][1]
            parts.append(f"{prev_bg}{bg}{SEPARATOR}")
        parts.append(seg)
    if segs_with_bg:
        last_bg = segs_with_bg[-1][1]
        parts.append(f"{last_bg}\x1b[38;5;0m{SEPARATOR}{RESET}")
    return "".join(parts)



# ── T9: Progress bar (V3) ────────────────────────────────────────────────

def progress_bar(pct, width=10):
    """Colored progress bar per V3."""
    filled = round((pct / 100) * width)
    empty = width - filled
    if pct > 80:
        color = FG_BAR_RED
    elif pct >= 50:
        color = FG_BAR_YELLOW
    else:
        color = FG_BAR_GREEN
    bar = f"{color}{'█' * filled}{FG_BAR_EMPTY}{'░' * empty}"
    return bar


def context_bg(pct):
    """Return bg color for context segment based on pct (V3)."""
    if pct > 80:
        return BG_RED
    elif pct >= 50:
        return BG_YELLOW
    return BG_GREEN


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

def build_output(session, quotas):
    """Assemble all segments into final powerline line."""
    # CWD + git
    cwd = _safe(lambda: Path(session["workspace"]["current_dir"]).name) or os.path.basename(os.getcwd())
    branch = read_git_branch()
    cwd_text = f"{cwd} {ICON_BRANCH} {branch}" if branch else cwd
    seg_cwd = (segment(ICON_FOLDER, cwd_text, BG_CWD), BG_CWD)

    # Model
    model = _safe(lambda: session["model"]["display_name"]) or "--"
    seg_model = (segment(ICON_SPARKLE, model, BG_MODEL), BG_MODEL)

    # Context
    ctx = session.get("context_window")
    ctx_pct = calc_context_pct(ctx)
    bar = progress_bar(ctx_pct)
    ctx_bg = context_bg(ctx_pct)
    seg_ctx = (f"{ctx_bg}{FG_WHITE} {ICON_BRAIN} {bar} {FG_WHITE}{ctx_pct}% ", ctx_bg)

    # 5h quota
    q5 = quotas.get("5h", {})
    q5_pct = q5.get("pct", 0)
    q5_reset = format_countdown(q5.get("reset_ms"))
    seg_5h = (segment(ICON_CLOCK, f"{q5_pct}% {q5_reset}", BG_QUOTA5), BG_QUOTA5)

    # 7d quota
    q7 = quotas.get("7d", {})
    q7_pct = q7.get("pct", 0)
    q7_reset = format_countdown(q7.get("reset_ms"))
    seg_7d = (segment(ICON_CALENDAR, f"{q7_pct}% {q7_reset}", BG_QUOTA7), BG_QUOTA7)

    # MCP
    mcp = quotas.get("mcp", 0)
    seg_mcp = (segment(ICON_PLUG, f"{mcp}%", BG_MCP), BG_MCP)

    # Lines diff
    cost = session.get("cost") or {}
    added = cost.get("total_lines_added") or 0
    removed = cost.get("total_lines_removed") or 0
    seg_diff = (segment(f"{ICON_PLUS}/{ICON_MINUS}", f"+{added}/-{removed}", BG_DIFF), BG_DIFF)

    return join_segments(seg_cwd, seg_model, seg_ctx, seg_5h, seg_7d, seg_mcp, seg_diff)


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

    # Build and print
    output = build_output(session, quotas)
    print(output)


if __name__ == "__main__":
    main()
