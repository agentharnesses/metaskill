#!/usr/bin/env python3
"""Progressive disclosure explorer for Agent Harnesses."""

import argparse
import json
import sys
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = SCRIPT_DIR / "sessions"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    meta: dict = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, text[end + 3:].strip()


def should_skip(entry: Path, parent: Path) -> bool:
    name = entry.name
    if name.startswith("."):
        return True
    if name == "HARNESS.md":
        return True
    if entry.is_file() and name == parent.name.upper() + ".md":
        return True
    return False


_detector_cache: dict[str, dict[str, str]] = {}


def load_leaf_detectors(directory: Path) -> dict[str, str] | None:
    """Walk up from directory to find the nearest .leaf-detectors config.

    Each non-blank, non-comment line must be ``leaf_type=relative_path``.
    The relative path is checked for existence inside the directory being
    classified, not the directory containing the config.
    Returns the parsed rules dict, or None if no config file was found.
    Results are cached by config file path.
    """
    current = directory.resolve()
    while True:
        config_path = current / ".leaf-detectors"
        key = str(config_path)
        if key in _detector_cache:
            return _detector_cache[key]
        if config_path.exists():
            rules: dict[str, str] = {}
            try:
                for line in config_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, _, v = line.partition("=")
                        rules[k.strip()] = v.strip()
            except OSError:
                pass
            _detector_cache[key] = rules
            return rules
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def detect_leaf_type(directory: Path) -> str | None:
    """Return the leaf type for a directory, or None if it's a plain group.

    Priority order:
    1. Explicit: .harnessleaf — first non-empty line is the type name.
    2. Config: nearest .leaf-detectors ancestor — first matching rule wins.
    Directories with no matching rule are plain groups; there is no fallback scan.
    """
    leaf_file = directory / ".harnessleaf"
    if leaf_file.exists():
        try:
            for line in leaf_file.read_text(encoding="utf-8").splitlines():
                content = line.strip()
                if content:
                    return content
        except OSError:
            pass

    detectors = load_leaf_detectors(directory)
    if detectors is not None:
        for leaf_type, pattern in detectors.items():
            if (directory / pattern).exists():
                return leaf_type
    return None


def classify(entry: Path) -> str:
    if entry.is_dir():
        return detect_leaf_type(entry) or "group"
    if entry.is_file():
        return "file"
    return ""


def file_type(path: Path, root: Path) -> str:
    parts = path.relative_to(root).parts
    return parts[0] if len(parts) > 1 else root.name


def get_description(path: Path, kind: str) -> str | None:
    if kind == "group":
        target = path / (path.name.upper() + ".md")
    elif path.is_dir():
        target = path / (kind.upper() + ".md")
    else:
        target = path

    if not target.exists():
        return None
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
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


def peek(directory: Path, root: Path) -> list[dict]:
    try:
        entries = sorted(
            directory.iterdir(),
            key=lambda e: (e.is_file(), e.name.lower()),
        )
    except OSError:
        return []

    items = []
    idx = 1
    for entry in entries:
        if should_skip(entry, directory):
            continue
        if entry.resolve() == SESSIONS_DIR.resolve():
            continue
        kind = classify(entry)
        if not kind:
            continue
        item_type = file_type(entry, root) if kind == "file" else kind
        description = get_description(entry, kind)
        item: dict = {
            "id": idx,
            "type": item_type,
            "name": entry.name,
            "path": str(entry),
        }
        if description:
            item["description"] = description
        items.append(item)
        idx += 1

    return items


# ── Session management ──────────────────────────────────────────────────────

def _session_file(session_id: str) -> Path:
    SESSIONS_DIR.mkdir(exist_ok=True)
    return SESSIONS_DIR / f"harness_{session_id}.json"


def _save_session(session_id: str, state: dict) -> None:
    _session_file(session_id).write_text(json.dumps(state))


def _load_session(session_id: str) -> dict:
    p = _session_file(session_id)
    if not p.exists():
        print(json.dumps({"error": f"Session not found: {session_id}"}))
        sys.exit(1)
    return json.loads(p.read_text())


def _delete_session(session_id: str) -> None:
    p = _session_file(session_id)
    if p.exists():
        p.unlink()


def _get_context(directory: Path) -> str | None:
    summary = directory / (directory.name.upper() + ".md")
    if not summary.exists():
        return None
    try:
        text = summary.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    _, body = parse_frontmatter(text)
    return body[:400] if body else None


def _advance_queue(state: dict) -> list[dict]:
    """Pop directories from the queue and peek until we get items or exhaust."""
    root = Path(state["root"])
    while state["queue"]:
        entry = state["queue"].pop(0)
        next_dir = Path(entry["path"])
        state["depth"] = entry["depth"]
        state["current_path"] = str(next_dir)
        state["current_context"] = _get_context(next_dir)
        items = peek(next_dir, root)
        state["current_items"] = items
        if items:
            return items
    state["current_items"] = []
    return []


def _fork_sessions(state: dict) -> list[dict]:
    """Create one DFS sub-session per queued entry. Returns branch descriptors."""
    branches = []
    for entry in state["queue"]:
        branch_id = uuid.uuid4().hex[:8]
        branch_state: dict = {
            "root": state["root"],
            "mode": "dfs",
            "queue": [entry],
            "resources": [],
            "current_path": state["root"],
            "current_items": [],
            "current_context": None,
            "depth": 0,
            "parallel_width": -1,
        }
        _advance_queue(branch_state)
        _save_session(branch_id, branch_state)
        try:
            location = str(Path(entry["path"]).relative_to(state["root"]))
        except ValueError:
            location = entry["path"]
        branch_items = [
            {k: v for k, v in i.items() if k != "path"}
            for i in branch_state["current_items"]
        ]
        branches.append({"session": branch_id, "location": location, "items": branch_items})
    return branches


# ── Output helpers ──────────────────────────────────────────────────────────

def _print_exploring(session_id: str, state: dict, items: list[dict]) -> None:
    try:
        location = str(Path(state["current_path"]).relative_to(state["root"]))
    except ValueError:
        location = state["current_path"]

    out: dict = {
        "status": "exploring",
        "session": session_id,
        "location": location,
        "items": [{k: v for k, v in i.items() if k != "path"} for i in items],
        "queued": len(state["queue"]),
        "found": len(state["resources"]),
    }
    if state.get("current_context"):
        out["context"] = state["current_context"]
    print(json.dumps(out, indent=2))


def _print_complete(session_id: str, state: dict) -> None:
    resources = [{**r, "session": session_id} for r in state["resources"]]
    print(json.dumps({
        "status": "complete",
        "session": session_id,
        "resources": resources,
    }, indent=2))


def _print_parallelize(session_id: str, state: dict, branches: list[dict]) -> None:
    out: dict = {
        "status": "parallelize",
        "session": session_id,
        "hint": (
            "Explore each branch independently; run in parallel if your framework "
            "supports it, otherwise process sequentially."
        ),
        "branches": branches,
    }
    if state["resources"]:
        out["resources"] = [{**r, "session": session_id} for r in state["resources"]]
    print(json.dumps(out, indent=2))


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_start(harness_path: str, mode: str, max_parallel: int = 4) -> None:
    root = Path(harness_path).resolve()
    if not root.exists():
        print(json.dumps({"error": f"Path not found: {harness_path}"}))
        sys.exit(1)

    session_id = uuid.uuid4().hex[:8]
    items = peek(root, root)

    state: dict = {
        "root": str(root),
        "mode": mode,
        "queue": [],
        "resources": [],
        "current_path": str(root),
        "current_items": items,
        "current_context": None,
        "depth": 0,
        "parallel_width": max_parallel if mode == "hybrid" else -1,
    }

    _save_session(session_id, state)
    _print_exploring(session_id, state, items)


def cmd_select(session_id: str, selection: str) -> None:
    state = _load_session(session_id)

    selected_ids: set[int] = set()
    for part in selection.split(","):
        part = part.strip()
        if part.isdigit():
            selected_ids.add(int(part))

    by_id = {item["id"]: item for item in state["current_items"]}
    next_depth = state["depth"] + 1
    new_groups: list[dict] = []

    for sel_id in sorted(selected_ids):
        item = by_id.get(sel_id)
        if not item:
            continue
        if item["type"] == "group":
            new_groups.append({"path": item["path"], "depth": next_depth})
        else:
            resource: dict = {
                "type": item["type"],
                "name": item["name"],
                "path": item["path"],
            }
            if item.get("description"):
                resource["description"] = item["description"]
            state["resources"].append(resource)

    if state["mode"] == "dfs":
        state["queue"] = new_groups + state["queue"]
    else:
        state["queue"] = state["queue"] + new_groups  # bfs and hybrid

    # Hybrid parallelization trigger: fork once queue is wide enough to meet the target.
    # BFS keeps running until len(queue) >= parallel_width, so shallow harnesses get
    # explored deeper before splitting rather than forking too early.
    if (
        state["mode"] == "hybrid"
        and len(state["queue"]) >= state["parallel_width"]
    ):
        branches = _fork_sessions(state)
        _delete_session(session_id)
        _print_parallelize(session_id, state, branches)
        return

    items = _advance_queue(state)

    if not items:
        _delete_session(session_id)
        _print_complete(session_id, state)
        return

    _save_session(session_id, state)
    _print_exploring(session_id, state, items)


def cmd_cancel(session_id: str) -> None:
    _delete_session(session_id)
    print(json.dumps({"status": "cancelled", "session": session_id}))


# ── CLI entry point ─────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Harness progressive disclosure explorer")
    p.add_argument("harness_path", nargs="?", help="Path to harness root")
    p.add_argument("--mode", choices=["bfs", "dfs", "hybrid"], default="bfs")
    p.add_argument(
        "--max-parallel",
        type=int,
        default=4,
        metavar="N",
        help="Fork into parallel branches once the queue reaches N items (hybrid mode only)",
    )
    p.add_argument("--session", metavar="ID")
    p.add_argument("--select", metavar="IDS")
    p.add_argument("--cancel", action="store_true")
    args = p.parse_args()

    if args.session:
        if args.cancel:
            cmd_cancel(args.session)
        elif args.select is not None:
            cmd_select(args.session, args.select)
        else:
            print(json.dumps({"error": "Use --select or --cancel with --session"}))
            sys.exit(1)
    elif args.harness_path:
        cmd_start(args.harness_path, args.mode, args.max_parallel)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
