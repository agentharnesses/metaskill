#!/usr/bin/env python3
"""Print the harness tree and full descriptions of all spec files."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.map_references import build_tree, format_lines


def _collect_specs(node: dict, root: Path) -> list[dict]:
    result = []
    for spec in node["specs"]:
        result.append({**spec, "rel": str(Path(spec["path"]).relative_to(root))})
    for child in node["children"]:
        result.extend(_collect_specs(child, root))
    return result


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

    specs = _collect_specs(node, root)
    if specs:
        print()
        print("─" * 60)
        for spec in specs:
            print(f"\n[{spec['kind']}]  {spec['rel']}")
            if spec.get("description"):
                print(f"  {spec['description']}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Print the harness tree and all spec file descriptions"
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
