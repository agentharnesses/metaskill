#!/usr/bin/env python3
"""Reverse disclosure: list spec-named files above a target in the harness hierarchy."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.disclose import detect_leaf_type


def find_root(target: Path) -> Path:
    """Walk up from target's parent to find the nearest ancestor with HARNESS.md."""
    current = target.parent
    while True:
        if (current / "HARNESS.md").exists():
            return current
        parent = current.parent
        if parent == current:
            return target.parent
        current = parent


def collect_ancestors(target: Path, root: Path) -> list[Path]:
    """List directories from target's parent up to root (inclusive, nearest first)."""
    root_resolved = root.resolve()
    current = target.parent
    ancestors: list[Path] = []
    while True:
        try:
            current.relative_to(root_resolved)
        except ValueError:
            break
        ancestors.append(current)
        if current.resolve() == root_resolved:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return ancestors


def spec_files_in(directory: Path, exclude: Path | None = None) -> list[dict]:
    """Return spec-named files that exist in directory, with their kind."""
    exclude_resolved = exclude.resolve() if exclude else None
    leaf_type = detect_leaf_type(directory)
    candidates = [
        ("harness", directory / "HARNESS.md"),
        ("routing", directory / (directory.name.upper() + ".md")),
    ]
    if leaf_type:
        candidates.append((leaf_type, directory / (leaf_type.upper() + ".md")))
    found = []
    seen_paths: set[Path] = set()
    for kind, path in candidates:
        resolved = path.resolve()
        if path.exists() and resolved != exclude_resolved and resolved not in seen_paths:
            found.append({"kind": kind, "path": str(path)})
            seen_paths.add(resolved)
    return found


def scan_ancestors(target: Path, root: Path) -> list[dict]:
    """Collect spec-named files from each ancestor directory."""
    references: list[dict] = []
    for ancestor in collect_ancestors(target, root):
        references.extend(spec_files_in(ancestor, exclude=target))
    return references


def cmd_run(target_path: str, root_path: str | None) -> None:
    target = Path(target_path).resolve()
    if not target.exists():
        print(json.dumps({"error": f"Target not found: {target_path}"}))
        sys.exit(1)

    if root_path:
        root = Path(root_path).resolve()
        if not root.exists():
            print(json.dumps({"error": f"Root not found: {root_path}"}))
            sys.exit(1)
    else:
        root = find_root(target)

    try:
        rel_target = str(target.relative_to(root))
    except ValueError:
        rel_target = str(target)

    result: dict = {
        "status": "complete",
        "target": rel_target,
        "root": str(root),
    }

    if target.is_file() and target.suffix.lower() == ".md":
        result["self"] = {"path": str(target)}

    result["references"] = scan_ancestors(target, root)
    print(json.dumps(result, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(
        description="List spec-named .md files above a target in the harness hierarchy"
    )
    p.add_argument("target_path", help="File or directory to look up")
    p.add_argument(
        "--root",
        metavar="PATH",
        help="Search root (default: nearest ancestor containing HARNESS.md)",
    )
    args = p.parse_args()
    cmd_run(args.target_path, args.root)


if __name__ == "__main__":
    main()
