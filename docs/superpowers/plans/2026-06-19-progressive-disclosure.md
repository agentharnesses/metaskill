# Progressive Disclosure Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/disclose.py`, a session-based CLI that lets an LLM agent progressively explore an Agent Harness by peeking directories, selecting relevant items by index, and accumulating a list of resource paths.

**Architecture:** A single Python script with no external dependencies. Module-level constants (patchable for tests) drive session storage at `sessions/` relative to the metaskill root. State is a JSON file per session; all commands are one-shot invocations that print JSON and exit.

**Tech Stack:** Python 3.10+, stdlib only (`pathlib`, `json`, `argparse`, `uuid`). Tests use `pytest` with `tmp_path` and `monkeypatch` fixtures.

## Global Constraints

- Python 3.10+ (uses `str | None` union syntax)
- No third-party dependencies — stdlib only
- All output is JSON printed to stdout; errors are `{"error": "..."}` with exit code 1
- Session files live at `sessions/harness_<8-char-hex>.json` inside the metaskill root
- `sessions/` directory is gitignored; a `.gitkeep` preserves the directory in git
- `SESSIONS_DIR` is a module-level `Path` constant in `disclose.py` so tests can monkeypatch it

---

### Task 1: Project scaffolding

**Files:**
- Create: `sessions/.gitkeep`
- Create: `.gitignore`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: nothing consumed by other tasks — pure scaffolding

- [ ] **Step 1: Create `sessions/` with a `.gitkeep`**

```bash
mkdir -p /path/to/metaskill/sessions
touch /path/to/metaskill/sessions/.gitkeep
```

Or create the file directly with empty content at `sessions/.gitkeep`.

- [ ] **Step 2: Create `.gitignore`**

```
sessions/*
!sessions/.gitkeep
```

- [ ] **Step 3: Create `tests/__init__.py`**

Empty file — makes `tests/` a package so pytest discovers it.

- [ ] **Step 4: Verify structure**

```bash
find . -not -path './.git/*' | sort
```

Expected output includes:
```
./.gitignore
./README.md
./sessions/.gitkeep
./tests/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore sessions/.gitkeep tests/__init__.py
git commit -m "chore: scaffold sessions dir, gitignore, and test package"
```

---

### Task 2: Core parsing and peek logic

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/disclose.py` (core functions only — no CLI yet)
- Create: `tests/test_disclose_core.py`

**Interfaces:**
- Produces (consumed by Task 3):
  - `parse_frontmatter(text: str) -> tuple[dict, str]`
  - `should_skip(entry: Path, parent: Path) -> bool`
  - `classify(entry: Path) -> str`  — returns `"skill"`, `"group"`, or `"file"`, or `""` for unknowns
  - `file_type(path: Path, root: Path) -> str`
  - `get_description(path: Path, kind: str) -> str | None`
  - `peek(directory: Path, root: Path) -> list[dict]`
    - Each dict: `{"id": int, "type": str, "name": str, "path": str}` plus optional `"description": str`
    - Dirs sorted before files; within each group sorted by name (case-insensitive)

- [ ] **Step 1: Write failing tests**

Create `tests/test_disclose_core.py`:

```python
import pytest
from pathlib import Path
from scripts.disclose import (
    parse_frontmatter,
    should_skip,
    classify,
    file_type,
    get_description,
    peek,
)


def test_parse_frontmatter_with_description():
    text = "---\nname: foo\ndescription: A test skill\n---\nBody content"
    meta, body = parse_frontmatter(text)
    assert meta["description"] == "A test skill"
    assert body == "Body content"


def test_parse_frontmatter_quoted_value():
    text = '---\ndescription: "Quoted value"\n---\n'
    meta, _ = parse_frontmatter(text)
    assert meta["description"] == "Quoted value"


def test_parse_frontmatter_no_frontmatter():
    text = "Just body content"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == "Just body content"


def test_parse_frontmatter_incomplete():
    text = "---\nname: foo\n"
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_should_skip_hidden(tmp_path):
    f = tmp_path / ".hidden"
    f.touch()
    assert should_skip(f, tmp_path) is True


def test_should_skip_harness_md(tmp_path):
    f = tmp_path / "HARNESS.md"
    f.touch()
    assert should_skip(f, tmp_path) is True


def test_should_skip_own_summary(tmp_path):
    # When peeking a dir named "skills", SKILLS.md inside it is skipped
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skills_md = skills_dir / "SKILLS.md"
    skills_md.touch()
    assert should_skip(skills_md, skills_dir) is True


def test_should_not_skip_regular_file(tmp_path):
    f = tmp_path / "schema.md"
    f.touch()
    assert should_skip(f, tmp_path) is False


def test_should_not_skip_regular_dir(tmp_path):
    d = tmp_path / "myskill"
    d.mkdir()
    assert should_skip(d, tmp_path) is False


def test_classify_skill(tmp_path):
    d = tmp_path / "myskill"
    d.mkdir()
    (d / "SKILL.md").touch()
    assert classify(d) == "skill"


def test_classify_group(tmp_path):
    d = tmp_path / "mygroup"
    d.mkdir()
    assert classify(d) == "group"


def test_classify_file(tmp_path):
    f = tmp_path / "ref.md"
    f.touch()
    assert classify(f) == "file"


def test_file_type_in_subfolder(tmp_path):
    f = tmp_path / "references" / "schema.md"
    f.parent.mkdir()
    f.touch()
    assert file_type(f, tmp_path) == "references"


def test_file_type_at_root(tmp_path):
    f = tmp_path / "readme.md"
    f.touch()
    assert file_type(f, tmp_path) == tmp_path.name


def test_get_description_from_frontmatter(tmp_path):
    skill_dir = tmp_path / "myskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\ndescription: Does the thing\n---\nBody")
    assert get_description(skill_dir, "skill") == "Does the thing"


def test_get_description_fallback_to_body(tmp_path):
    skill_dir = tmp_path / "myskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: foo\n---\n# Heading\nFirst real line")
    assert get_description(skill_dir, "skill") == "First real line"


def test_get_description_missing_file(tmp_path):
    d = tmp_path / "ghost"
    d.mkdir()
    assert get_description(d, "skill") is None


def test_peek_mixed_directory(tmp_path):
    root = tmp_path

    # A skill dir
    skill = root / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: My skill\n---\n")

    # A group dir
    group = root / "subgroup"
    group.mkdir()
    (group / "SUBGROUP.md").write_text("---\ndescription: A subgroup\n---\n")

    # A reference file
    ref = root / "notes.md"
    ref.write_text("---\ndescription: Some notes\n---\n")

    # Should be skipped
    (root / "HARNESS.md").touch()
    (root / ".hidden").touch()

    items = peek(root, root)

    types = [i["type"] for i in items]
    names = [i["name"] for i in items]

    assert "skill" in types
    assert "group" in types
    assert "my-skill" in names
    assert "subgroup" in names
    assert "notes.md" in names
    assert "HARNESS.md" not in names
    assert ".hidden" not in names


def test_peek_items_have_ids(tmp_path):
    (tmp_path / "a-skill").mkdir()
    ((tmp_path / "a-skill") / "SKILL.md").touch()
    items = peek(tmp_path, tmp_path)
    assert items[0]["id"] == 1


def test_peek_dirs_before_files(tmp_path):
    (tmp_path / "aardvark.md").touch()
    d = tmp_path / "zebra"
    d.mkdir()
    (d / "SKILL.md").touch()
    items = peek(tmp_path, tmp_path)
    assert items[0]["type"] == "skill"
    assert items[1]["name"] == "aardvark.md"


def test_peek_skips_own_summary(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "SKILLS.md").write_text("---\ndescription: routing\n---\n")
    (skills_dir / "real-skill").mkdir()
    ((skills_dir / "real-skill") / "SKILL.md").touch()
    items = peek(skills_dir, tmp_path)
    names = [i["name"] for i in items]
    assert "SKILLS.md" not in names
    assert "real-skill" in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/metaskill && python -m pytest tests/test_disclose_core.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or `ImportError` — `scripts.disclose` doesn't exist yet.

- [ ] **Step 3: Create `scripts/__init__.py`**

Empty file.

- [ ] **Step 4: Implement `scripts/disclose.py` (core functions)**

```python
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
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:150]
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_disclose_core.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/disclose.py tests/test_disclose_core.py
git commit -m "feat: add core peek and parsing logic for disclose.py"
```

---

### Task 3: Session management, traversal, and CLI commands

**Files:**
- Modify: `scripts/disclose.py` — append session, traversal, and CLI code
- Create: `tests/test_disclose_cli.py`

**Interfaces:**
- Consumes from Task 2: `peek(directory, root)`, `parse_frontmatter`, `classify`, `get_description`
- Produces: executable CLI — `python scripts/disclose.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_disclose_cli.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch
import scripts.disclose as disclose


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    sd = tmp_path / "sessions"
    sd.mkdir()
    monkeypatch.setattr(disclose, "SESSIONS_DIR", sd)
    return sd


@pytest.fixture
def simple_harness(tmp_path):
    """A minimal harness: one skill, one reference file."""
    skills = tmp_path / "skills"
    skills.mkdir()
    skill = skills / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\ndescription: Does something useful\n---\n")

    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "guide.md").write_text("---\ndescription: Usage guide\n---\n")

    return tmp_path


@pytest.fixture
def nested_harness(tmp_path):
    """A harness with a group containing two skills."""
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "SKILLS.md").write_text("---\ndescription: All skills\n---\nRouting info here.")

    group = skills / "database"
    group.mkdir()
    (group / "DATABASE.md").write_text("---\ndescription: DB skills\n---\nDatabase routing.")

    for name in ("query", "migrate"):
        s = group / name
        s.mkdir()
        (s / "SKILL.md").write_text(f"---\ndescription: {name.title()} skill\n---\n")

    return tmp_path


def test_cmd_start_returns_exploring(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "exploring"
    assert "session" in out
    assert out["location"] == "."
    assert len(out["items"]) == 2


def test_cmd_start_creates_session_file(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    out = json.loads(capsys.readouterr().out)
    sid = out["session"]
    assert (sessions_dir / f"harness_{sid}.json").exists()


def test_cmd_start_invalid_path(sessions_dir, capsys):
    with pytest.raises(SystemExit):
        disclose.cmd_start("/nonexistent/path", "bfs")
    out = json.loads(capsys.readouterr().out)
    assert "error" in out


def test_cmd_select_skill_goes_to_resources(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Find the skills group item id
    skills_item = next(i for i in start_out["items"] if i["name"] == "skills")

    disclose.cmd_select(sid, str(skills_item["id"]))
    select_out = json.loads(capsys.readouterr().out)

    # Now peeking inside skills/ — select my-skill
    assert select_out["status"] == "exploring"
    skill_item = next(i for i in select_out["items"] if i["name"] == "my-skill")

    disclose.cmd_select(sid, str(skill_item["id"]))
    final_out = json.loads(capsys.readouterr().out)

    # references group is still in queue, so not complete yet
    # Select nothing to exhaust
    if final_out["status"] == "exploring":
        disclose.cmd_select(sid, "")
        final_out = json.loads(capsys.readouterr().out)

    assert final_out["status"] == "complete"
    resource_names = [r["name"] for r in final_out["resources"]]
    assert "my-skill" in resource_names


def test_cmd_select_empty_exhausts_queue(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    disclose.cmd_select(sid, "")
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "complete"
    assert out["resources"] == []


def test_cmd_select_session_deleted_on_complete(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    disclose.cmd_select(sid, "")
    capsys.readouterr()

    assert not (sessions_dir / f"harness_{sid}.json").exists()


def test_bfs_explores_breadth_first(nested_harness, sessions_dir, capsys):
    """In BFS, after selecting a group, other same-level items are explored first."""
    refs = nested_harness / "references"
    refs.mkdir()

    disclose.cmd_start(str(nested_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Select both top-level groups (skills and references)
    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    out = json.loads(capsys.readouterr().out)

    # BFS: should be exploring skills/ next (first selected)
    assert out["location"] == "skills"


def test_dfs_explores_depth_first(nested_harness, sessions_dir, capsys):
    """In DFS, after selecting a group inside skills, we dive into it before references."""
    refs = nested_harness / "references"
    refs.mkdir()

    disclose.cmd_start(str(nested_harness), "dfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    # Select both top-level groups
    all_ids = ",".join(str(i["id"]) for i in start_out["items"])
    disclose.cmd_select(sid, all_ids)
    out1 = json.loads(capsys.readouterr().out)
    assert out1["location"] == "skills"

    # Select the database group inside skills
    db_item = next(i for i in out1["items"] if i["name"] == "database")
    disclose.cmd_select(sid, str(db_item["id"]))
    out2 = json.loads(capsys.readouterr().out)

    # DFS: should dive into database/ before exploring references/
    assert out2["location"] == "skills/database"


def test_cmd_cancel_deletes_session(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]
    capsys.readouterr()

    disclose.cmd_cancel(sid)
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "cancelled"
    assert not (sessions_dir / f"harness_{sid}.json").exists()


def test_context_included_when_summary_exists(nested_harness, sessions_dir, capsys):
    disclose.cmd_start(str(nested_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    skills_item = next(i for i in start_out["items"] if i["name"] == "skills")
    disclose.cmd_select(sid, str(skills_item["id"]))
    out = json.loads(capsys.readouterr().out)

    # skills/ has SKILLS.md with body "Routing info here." — should appear as context
    assert "context" in out
    assert "Routing info here." in out["context"]


def test_resource_type_matches_top_level_folder(simple_harness, sessions_dir, capsys):
    disclose.cmd_start(str(simple_harness), "bfs")
    start_out = json.loads(capsys.readouterr().out)
    sid = start_out["session"]

    refs_item = next(i for i in start_out["items"] if i["name"] == "references")
    disclose.cmd_select(sid, str(refs_item["id"]))
    out = json.loads(capsys.readouterr().out)

    guide_item = next(i for i in out["items"] if i["name"] == "guide.md")
    disclose.cmd_select(sid, str(guide_item["id"]))
    final = json.loads(capsys.readouterr().out)

    if final["status"] == "exploring":
        disclose.cmd_select(sid, "")
        final = json.loads(capsys.readouterr().out)

    ref_resource = next(r for r in final["resources"] if r["name"] == "guide.md")
    assert ref_resource["type"] == "references"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_disclose_cli.py -v 2>&1 | head -30
```

Expected: `ImportError` for `cmd_start`, `cmd_select`, `cmd_cancel`.

- [ ] **Step 3: Append session management and CLI to `scripts/disclose.py`**

Add the following after the existing `peek` function (do not replace anything — append only):

```python
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
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Smoke test the CLI manually**

```bash
python scripts/disclose.py . --mode bfs
```

Expected: JSON with `status: exploring` showing the metaskill's own top-level entries (e.g. `docs/`, `scripts/`, `sessions/`, `tests/`).

- [ ] **Step 6: Commit**

```bash
git add scripts/disclose.py tests/test_disclose_cli.py
git commit -m "feat: add session management, traversal, and CLI commands to disclose.py"
```

---

### Task 4: SKILL.md

**Files:**
- Create: `SKILL.md`

**Interfaces:**
- Consumes: final CLI surface from Task 3 (exact command signatures)
- Produces: nothing — this is agent-facing documentation

- [ ] **Step 1: Create `SKILL.md`**

```markdown
---
name: metaskill
description: Progressive disclosure explorer for Agent Harnesses — enables agents without native harness integration to efficiently find relevant skills and references
---

Use this skill when you are pointed to a harness directory and need to discover which skills or references are relevant to your current task. It exposes only what you need, one layer at a time, so you don't flood your context with irrelevant content.

## Skills

- `scripts/disclose.py` — session-based harness explorer

## How to Use

### 1. Start a session

```
python scripts/disclose.py <harness_path> [--mode bfs|dfs]
```

`bfs` (default) explores breadth-first — exhausts each level before going deeper. `dfs` dives into the first relevant group immediately.

**Choosing a mode:**
- Use `bfs` when exploring an unfamiliar harness or when your task could involve multiple areas. You'll see all sibling groups before committing to any branch, which prevents missing something important in a folder you never peek.
- Use `dfs` when you already know which branch contains what you need (e.g., you've been told "the auth skill is under `skills/auth/`"). It gets you there without surveying siblings first.

When in doubt, use `bfs`.

The response is JSON:

```json
{
  "status": "exploring",
  "session": "a3f2c1b0",
  "location": ".",
  "items": [
    {"id": 1, "type": "group", "name": "skills", "description": "..."},
    {"id": 2, "type": "group", "name": "references", "description": "..."}
  ],
  "queued": 0,
  "found": 0
}
```

`context` appears when the current directory has a summary file — read it to orient yourself before selecting.

Item types:
- `"group"` — a subdirectory; selecting it recurses into it
- `"skill"` — a skill directory; selecting it queues it as a result (read `<path>/SKILL.md`)
- anything else (e.g. `"references"`) — a file resource; selecting it queues it as a result

### 2. Select relevant items

Respond with only the IDs of items relevant to your task, comma-separated. Pass `""` to skip the current level entirely.

```
python scripts/disclose.py --session <id> --select "1,3"
```

**Be selective.** Unselected groups are not explored. The goal is to load as little as possible.

### 3. Repeat until complete

Continue until `status` is `"complete"`:

```json
{
  "status": "complete",
  "session": "a3f2c1b0",
  "resources": [
    {"type": "skill",      "name": "my-skill", "path": "/abs/path/to/skills/my-skill"},
    {"type": "references", "name": "guide.md", "path": "/abs/path/to/references/guide.md"}
  ]
}
```

### 4. Load your resources

- For `skill` entries: read `<path>/SKILL.md`
- For file entries: read `<path>` directly

### Cancel a session

```
python scripts/disclose.py --session <id> --cancel
```
```

- [ ] **Step 2: Verify frontmatter parses correctly**

```bash
python -c "
from scripts.disclose import parse_frontmatter
text = open('SKILL.md').read()
meta, body = parse_frontmatter(text)
print('name:', meta.get('name'))
print('description:', meta.get('description'))
"
```

Expected output:
```
name: metaskill
description: Progressive disclosure explorer for Agent Harnesses — enables agents without native harness integration to efficiently find relevant skills and references
```

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "docs: add SKILL.md with operational instructions for disclose.py"
```

---

## Self-Review

**Spec coverage:**
- ✅ `disclose.py` start command
- ✅ `--session --select` continue command
- ✅ `--session --cancel` command
- ✅ Session files at `sessions/harness_<id>.json`
- ✅ Auto-delete on complete and cancel
- ✅ Peek classifies skill / group / file
- ✅ Skips HARNESS.md and `<DIRNAME_UPPER>.md`
- ✅ File type derived from top-level ancestor folder name
- ✅ Descriptions from frontmatter with fallback to body
- ✅ BFS appends groups to queue; DFS prepends
- ✅ `context` from summary body (truncated to 400 chars)
- ✅ `queued` and `found` progress fields
- ✅ Paths stripped from items output; present in state
- ✅ `SESSIONS_DIR` patchable for tests
- ✅ SKILL.md with frontmatter
- ✅ `.gitignore` for sessions/
- ✅ `sessions/` lives in metaskill root

**Placeholder scan:** None found.

**Type consistency:** `peek` → `list[dict]` used consistently in `cmd_start` and `_advance_queue`. `state["current_items"]` always set from `peek` output. `_session_file`, `_save_session`, `_load_session`, `_delete_session` names consistent throughout.
