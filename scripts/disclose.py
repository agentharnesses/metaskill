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
