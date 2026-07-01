#!/usr/bin/env python3
"""Idempotent HA configuration.yaml patcher.

Sets `recorder.commit_interval` to a target value without touching any
other keys, users' comments, or unrelated recorder options. Creates a
timestamped backup before modifying. Safe to re-run — no-ops when the
target value is already present.

Runs before rpi_monitor when config_patcher.enabled=true in options.json.
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime

CONFIG_PATH = "/homeassistant/configuration.yaml"
OPTIONS_PATH = "/data/options.json"


def log(msg: str) -> None:
    print(f"[config_patcher] {msg}", flush=True)


def load_options() -> dict:
    with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def read_config() -> str:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def write_config(text: str) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(text)


def backup_config() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = f"{CONFIG_PATH}.bak.{stamp}"
    shutil.copy2(CONFIG_PATH, dst)
    return dst


def patch_commit_interval(text: str, target: int) -> tuple[str, str]:
    """Return (new_text, action) where action is 'noop'|'updated'|'added'.

    Handles three cases:
      1. `recorder:` block exists with `commit_interval: N` line → update if != target
      2. `recorder:` block exists without commit_interval → insert line right after
      3. no `recorder:` block at all → append a new block at end of file
    """
    lines = text.splitlines(keepends=False)

    # Locate a top-level `recorder:` (start of line, no indent, followed by :)
    recorder_line = None
    for i, ln in enumerate(lines):
        # Match "recorder:" (allow inline comment). Skip commented-out lines.
        stripped = ln.lstrip()
        if stripped.startswith("#"):
            continue
        if re.match(r"^recorder\s*:\s*(#.*)?$", ln):
            recorder_line = i
            break

    if recorder_line is None:
        # Case 3: append block at end
        block = [
            "",
            "# Added by rpi_health_monitor config_patcher — reduces SD write amplification",
            "recorder:",
            f"  commit_interval: {target}",
            "",
        ]
        new_text = text
        if not new_text.endswith("\n"):
            new_text += "\n"
        new_text += "\n".join(block) + "\n"
        return new_text, "added"

    # Determine block extent: contiguous indented lines after `recorder:` heading
    block_end = len(lines)
    for j in range(recorder_line + 1, len(lines)):
        ln = lines[j]
        if ln.strip() == "":
            continue
        # A line that is not indented ends the block
        if not (ln.startswith(" ") or ln.startswith("\t")):
            block_end = j
            break

    # Look for existing commit_interval line within the block
    ci_pattern = re.compile(r"^(\s+)commit_interval\s*:\s*([^\s#]+)(.*)$")
    for j in range(recorder_line + 1, block_end):
        m = ci_pattern.match(lines[j])
        if m:
            current = m.group(2).strip()
            if current == str(target):
                return text, "noop"
            indent = m.group(1)
            trailer = m.group(3)
            lines[j] = f"{indent}commit_interval: {target}{trailer}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), "updated"

    # No commit_interval in block → insert right after heading with proper indent
    # Detect indent from first indented line inside block; fallback to two spaces
    indent = "  "
    for j in range(recorder_line + 1, block_end):
        ln = lines[j]
        if ln.strip():
            m = re.match(r"^(\s+)", ln)
            if m:
                indent = m.group(1)
            break
    lines.insert(recorder_line + 1, f"{indent}commit_interval: {target}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), "added"


def main() -> int:
    if not os.path.exists(OPTIONS_PATH):
        log("no options.json — skipping")
        return 0
    opts = load_options()
    patcher = opts.get("config_patcher") or {}
    if not patcher.get("enabled"):
        log("config_patcher.enabled=false — skipping")
        return 0

    target = int(patcher.get("recorder_commit_interval", 60))
    log(f"target recorder.commit_interval = {target}")

    if not os.path.exists(CONFIG_PATH):
        log(f"{CONFIG_PATH} not found — is /homeassistant mapped rw? aborting")
        return 1

    original = read_config()
    new_text, action = patch_commit_interval(original, target)

    if action == "noop":
        log(f"already at {target} — nothing to do")
        return 0

    backup = backup_config()
    log(f"backed up to {backup}")
    write_config(new_text)
    log(f"configuration.yaml {action}: recorder.commit_interval = {target}")
    log("HA restart required to apply — POST /api/services/homeassistant/restart")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log(f"ERROR: {exc}")
        # Never fail the container — the monitor is the primary job
        sys.exit(0)
