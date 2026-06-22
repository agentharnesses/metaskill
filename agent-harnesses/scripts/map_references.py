#!/usr/bin/env python3
"""Print a visual tree of all spec files in an Agent Harness."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.disclose import peek, parse_frontmatter
from scripts.reverse_disclose import spec_files_in

_ANSI_BOLD_RED = "\033[1;31m"
_ANSI_YELLOW   = "\033[33m"
_ANSI_CYAN     = "\033[36m"
_ANSI_GREEN    = "\033[32m"
_ANSI_RESET    = "\033[0m"

_KIND_COLOR = {
    "harness": _ANSI_BOLD_RED,
    "routing": _ANSI_YELLOW,
    "skill":   _ANSI_CYAN,
    "ref":     _ANSI_GREEN,
}

_SKIP_DIRS = {"node_modules", "__pycache__", "dist", "build", ".venv", "venv"}


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
    color = _KIND_COLOR.get(kind, "")
    return f"{color}{label}{_ANSI_RESET}"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 3] + "..."


def format_lines(node: dict, prefix: str = "", is_last: bool = True, depth: int = 0) -> list[str]:
    lines: list[str] = []

    if depth == 0:
        lines.append(f"{node['name']}/")
        child_prefix = ""
    else:
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{node['name']}/")
        child_prefix = prefix + ("    " if is_last else "│   ")

    all_items = [("spec", s) for s in node["specs"]] + [("child", c) for c in node["children"]]

    for i, (kind, item) in enumerate(all_items):
        item_is_last = (i == len(all_items) - 1)
        item_connector = "└── " if item_is_last else "├── "

        if kind == "spec":
            badge = _badge(item["kind"])
            name = item["name"]
            desc = item.get("description", "")
            suffix = f"  — {_truncate(desc, 60)}" if desc else ""
            lines.append(f"{child_prefix}{item_connector}{badge}  {name}{suffix}")
        else:
            lines.extend(format_lines(item, child_prefix, item_is_last, depth + 1))

        if depth == 0 and not item_is_last:
            lines.append("│")

    return lines


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

    existing_paths = {s["path"] for s in specs}
    child_nodes = []
    for item in peek(directory, root):
        child_path = Path(item["path"])
        if child_path.is_dir():
            if child_path.name in _SKIP_DIRS:
                continue
            child_node = build_tree(child_path, root)
            if child_node is not None:
                child_nodes.append(child_node)
        elif child_path.is_file() and item["name"].endswith(".md"):
            if item["path"] in existing_paths:
                continue
            routing_name = directory.name.upper() + ".md"
            is_routing = item["name"] == routing_name or item["name"] == "SKILLS.md"
            kind = "routing" if is_routing else "ref"
            node_spec: dict = {
                "kind": kind,
                "path": item["path"],
                "name": item["name"],
            }
            if item.get("description"):
                node_spec["description"] = item["description"]
            specs.append(node_spec)
            existing_paths.add(item["path"])

    if not specs and not child_nodes:
        return None

    return {
        "name": directory.name,
        "path": directory,
        "specs": specs,
        "children": child_nodes,
    }


def cmd_run(harness_root: str) -> None:
    root = Path(harness_root).resolve()
    if not root.exists():
        print(f"error: path not found: {harness_root}", file=sys.stderr)
        sys.exit(1)

    node = build_tree(root, root)
    if node is None:
        print(f"error: no spec files found under {harness_root}", file=sys.stderr)
        sys.exit(1)

    print("\n".join(format_lines(node)))


def main() -> None:
    p = argparse.ArgumentParser(
        description="Print a visual tree of all spec files in an Agent Harness"
    )
    p.add_argument(
        "harness_root",
        nargs="?",
        default=".",
        help="Path to harness root (default: current directory)",
    )
    args = p.parse_args()
    cmd_run(args.harness_root)


if __name__ == "__main__":
    main()
