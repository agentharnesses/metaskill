#!/usr/bin/env python3
"""Print a visual tree of all spec files in an Agent Harness."""

import argparse
import sys
from pathlib import Path

from scripts.disclose import peek, parse_frontmatter
from scripts.reverse_disclose import spec_files_in

_ANSI_BOLD_RED = "\033[1;31m"
_ANSI_YELLOW   = "\033[33m"
_ANSI_CYAN     = "\033[36m"
_ANSI_RESET    = "\033[0m"

_KIND_COLOR = {
    "harness": _ANSI_BOLD_RED,
    "routing": _ANSI_YELLOW,
    "skill":   _ANSI_CYAN,
}

_BADGE_WIDTH = 9  # len("[harness]")


def get_spec_description(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta, body = parse_frontmatter(text)
    if meta.get("description"):
        return meta["description"]
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped[:150]
    return None


def _badge(kind: str) -> str:
    label = f"[{kind}]"
    padded = label.ljust(_BADGE_WIDTH)
    color = _KIND_COLOR.get(kind, "")
    return f"{color}{padded}{_ANSI_RESET}"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 3] + "..."


def build_tree(directory: Path, root: Path) -> dict | None:
    raw_specs = spec_files_in(directory)
    specs = []
    for s in raw_specs:
        path = Path(s["path"])
        node_spec: dict = {
            "kind": s["kind"],
            "path": s["path"],
            "name": path.name,
        }
        desc = get_spec_description(path)
        if desc:
            node_spec["description"] = desc
        specs.append(node_spec)

    child_nodes = []
    for item in peek(directory, root):
        if item["type"] not in ("group", "skill"):
            continue
        child_path = Path(item["path"])
        child_node = build_tree(child_path, root)
        if child_node is not None:
            child_nodes.append(child_node)

    if not specs and not child_nodes:
        return None

    return {
        "name": directory.name,
        "path": directory,
        "specs": specs,
        "children": child_nodes,
    }
