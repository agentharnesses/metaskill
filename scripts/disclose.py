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


def classify(entry: Path) -> str:
    if entry.is_dir():
        return "skill" if (entry / "SKILL.md").exists() else "group"
    if entry.is_file():
        return "file"
    return ""


def file_type(path: Path, root: Path) -> str:
    parts = path.relative_to(root).parts
    return parts[0] if len(parts) > 1 else root.name


def get_description(path: Path, kind: str) -> str | None:
    if kind == "skill":
        target = path / "SKILL.md"
    elif kind == "group":
        target = path / (path.name.upper() + ".md")
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
        next_dir = Path(state["queue"].pop(0))
        state["current_path"] = str(next_dir)
        state["current_context"] = _get_context(next_dir)
        items = peek(next_dir, root)
        state["current_items"] = items
        if items:
            return items
    state["current_items"] = []
    return []


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
    print(json.dumps({
        "status": "complete",
        "session": session_id,
        "resources": state["resources"],
    }, indent=2))


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_start(harness_path: str, mode: str) -> None:
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
    new_groups: list[str] = []

    for sel_id in sorted(selected_ids):
        item = by_id.get(sel_id)
        if not item:
            continue
        if item["type"] == "group":
            new_groups.append(item["path"])
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
        state["queue"] = state["queue"] + new_groups

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
    p.add_argument("--mode", choices=["bfs", "dfs"], default="bfs")
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
        cmd_start(args.harness_path, args.mode)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
