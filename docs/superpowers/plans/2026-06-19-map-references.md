# map_references Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `scripts/map_references.py` that prints a human-readable, ANSI-colored ASCII tree of every spec file in an Agent Harness.

**Architecture:** The script imports `peek` and `parse_frontmatter` from `disclose.py` and `spec_files_in` + `find_root` from `reverse_disclose.py` to reuse existing traversal logic. `build_tree` walks the harness recursively, collecting spec files per directory and pruning empty branches. `format_lines` renders the tree with box-drawing characters and ANSI-colored kind badges.

**Tech Stack:** Python 3.13, stdlib only (`argparse`, `sys`, `pathlib`, `re`). Imports from sibling scripts in `agent-harnesses/scripts/`.

## Global Constraints

- All imports from other scripts use `from scripts.disclose import ...` / `from scripts.reverse_disclose import ...` (conftest.py adds `agent-harnesses/` to sys.path)
- Tests live in `tests/test_map_references.py` and follow the same fixture/import pattern as the existing test files
- No new dependencies — stdlib only
- Python 3.13 type annotations (`dict | None`, `str | None`)

---

### Task 1: get_spec_description and build_tree

**Files:**
- Create: `agent-harnesses/scripts/map_references.py`
- Create: `tests/test_map_references.py`

**Interfaces:**
- Produces:
  - `get_spec_description(path: Path) -> str | None` — reads description from a spec file's frontmatter or first body line
  - `build_tree(directory: Path, root: Path) -> dict | None` — returns a node dict or `None` if the subtree has no spec files

Node dict shape:
```python
{
    "name": str,           # directory.name
    "path": Path,          # absolute directory path
    "specs": [             # spec files found directly in this directory
        {
            "kind": str,          # "harness" | "routing" | "skill"
            "path": str,          # absolute path to the spec file
            "name": str,          # filename (e.g. "SKILL.md")
            "description": str,   # optional — omitted if not found
        }
    ],
    "children": [dict],    # recursively same shape, pruned (empty branches excluded)
}
```

- [ ] **Step 1: Write failing tests for get_spec_description**

Create `tests/test_map_references.py` with all imports up front (functions will be added incrementally across tasks):

```python
import pytest
import re
from pathlib import Path
from scripts.map_references import get_spec_description, build_tree, format_lines, cmd_run


def test_get_spec_description_reads_frontmatter(tmp_path):
    f = tmp_path / "HARNESS.md"
    f.write_text("---\ndescription: Root harness\n---\nBody text\n")
    assert get_spec_description(f) == "Root harness"


def test_get_spec_description_falls_back_to_body(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("No frontmatter here, just body text.\n")
    assert get_spec_description(f) == "No frontmatter here, just body text."


def test_get_spec_description_skips_headings_in_body(tmp_path):
    f = tmp_path / "SKILLS.md"
    f.write_text("# Heading\n\nFirst real paragraph.\n")
    assert get_spec_description(f) == "First real paragraph."


def test_get_spec_description_returns_none_for_missing_file(tmp_path):
    assert get_spec_description(tmp_path / "nonexistent.md") is None


def test_get_spec_description_returns_none_for_empty_file(tmp_path):
    f = tmp_path / "empty.md"
    f.write_text("")
    assert get_spec_description(f) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_map_references.py::test_get_spec_description_reads_frontmatter -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `map_references` doesn't exist yet.

- [ ] **Step 3: Write failing tests for build_tree**

Append to `tests/test_map_references.py`:

```python
def test_build_tree_single_harness_md(tmp_path):
    (tmp_path / "HARNESS.md").write_text("---\ndescription: Root harness\n---\n")
    node = build_tree(tmp_path, tmp_path)
    assert node is not None
    assert node["name"] == tmp_path.name
    assert len(node["specs"]) == 1
    assert node["specs"][0]["kind"] == "harness"
    assert node["specs"][0]["name"] == "HARNESS.md"
    assert node["specs"][0]["description"] == "Root harness"
    assert node["children"] == []


def test_build_tree_returns_none_for_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert build_tree(empty, tmp_path) is None


def test_build_tree_recurses_into_child_dirs(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    skills = tmp_path / "skills"
    skills.mkdir()
    auth = skills / "auth"
    auth.mkdir()
    (auth / "SKILL.md").write_text("---\ndescription: Auth skill\n---\n")

    node = build_tree(tmp_path, tmp_path)
    assert node is not None
    assert len(node["children"]) == 1
    skills_node = node["children"][0]
    assert skills_node["name"] == "skills"
    assert len(skills_node["children"]) == 1
    auth_node = skills_node["children"][0]
    assert auth_node["name"] == "auth"
    assert auth_node["specs"][0]["kind"] == "skill"
    assert auth_node["specs"][0]["description"] == "Auth skill"


def test_build_tree_prunes_empty_branches(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    empty = tmp_path / "no_specs_here"
    empty.mkdir()

    node = build_tree(tmp_path, tmp_path)
    child_names = [c["name"] for c in node["children"]]
    assert "no_specs_here" not in child_names


def test_build_tree_routing_file(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "SKILLS.md").write_text("---\ndescription: Skill index\n---\n")

    node = build_tree(skills, tmp_path)
    assert node is not None
    assert node["specs"][0]["kind"] == "routing"
    assert node["specs"][0]["description"] == "Skill index"


def test_build_tree_no_description_when_file_empty(tmp_path):
    (tmp_path / "HARNESS.md").touch()
    node = build_tree(tmp_path, tmp_path)
    assert node is not None
    assert "description" not in node["specs"][0]
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
pytest tests/test_map_references.py -v
```

Expected: All fail with `ImportError`.

- [ ] **Step 5: Implement get_spec_description and build_tree**

Create `agent-harnesses/scripts/map_references.py`:

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_map_references.py -v
```

Expected: All `test_get_spec_description_*` and `test_build_tree_*` tests pass.

- [ ] **Step 7: Commit**

```bash
git add agent-harnesses/scripts/map_references.py tests/test_map_references.py
git commit -m "feat: add build_tree and get_spec_description to map_references"
```

---

### Task 2: format_lines — ASCII renderer with ANSI color

**Files:**
- Modify: `agent-harnesses/scripts/map_references.py` (add `format_lines`)
- Modify: `tests/test_map_references.py` (add renderer tests)

**Interfaces:**
- Consumes: node dict from `build_tree` (Task 1)
- Produces:
  - `format_lines(node: dict, prefix: str = "", is_last: bool = True, depth: int = 0) -> list[str]`
    Returns a list of printable lines for the node and all its descendants.

Output rules:
- Root node (depth=0): first line is `"name/"`, child_prefix is `""`
- Child nodes: first line is `prefix + connector + "name/"` where connector is `"└── "` (last) or `"├── "` (non-last), child_prefix is `prefix + "    "` (last) or `prefix + "│   "` (non-last)
- Within each node: specs listed first, then child directories
- Spec lines: `child_prefix + connector + _badge(kind) + "  " + name + "  " + description` (description omitted if empty)
- Descriptions truncated to 60 chars
- At depth=0 only: a bare `"│"` separator line is inserted between every pair of sibling items

- [ ] **Step 1: Write failing tests for format_lines**

Append to `tests/test_map_references.py`:

```python
def strip_ansi(s: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', s)


def _make_spec(kind: str, filename: str, description: str = "") -> dict:
    spec: dict = {"kind": kind, "path": f"/fake/{filename}", "name": filename}
    if description:
        spec["description"] = description
    return spec


def _make_node(name: str, specs=None, children=None) -> dict:
    return {
        "name": name,
        "path": Path(f"/fake/{name}"),
        "specs": specs or [],
        "children": children or [],
    }


def test_format_lines_root_header():
    node = _make_node("my-harness")
    lines = format_lines(node)
    assert lines[0] == "my-harness/"


def test_format_lines_spec_badge_and_name():
    node = _make_node("root", specs=[_make_spec("harness", "HARNESS.md", "My harness")])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert "[harness]" in raw
    assert "HARNESS.md" in raw
    assert "My harness" in raw


def test_format_lines_badge_colors_present():
    node = _make_node("root", specs=[
        _make_spec("harness", "HARNESS.md"),
        _make_spec("routing", "SKILLS.md"),
        _make_spec("skill",   "SKILL.md"),
    ])
    output = "\n".join(format_lines(node))
    assert "\033[1;31m" in output  # harness: bold red
    assert "\033[33m"   in output  # routing: yellow
    assert "\033[36m"   in output  # skill: cyan


def test_format_lines_last_item_uses_corner():
    child = _make_node("skills", specs=[_make_spec("routing", "SKILLS.md")])
    node = _make_node("root", children=[child])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert "└── skills/" in raw


def test_format_lines_non_last_item_uses_tee():
    child_a = _make_node("skills", specs=[_make_spec("routing", "SKILLS.md")])
    child_b = _make_node("refs",   specs=[_make_spec("routing", "REFS.md")])
    node = _make_node("root", children=[child_a, child_b])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert "├── skills/" in raw
    assert "└── refs/" in raw


def test_format_lines_truncates_long_description():
    long_desc = "x" * 80
    node = _make_node("root", specs=[_make_spec("harness", "HARNESS.md", long_desc)])
    raw = strip_ansi("\n".join(format_lines(node)))
    assert long_desc not in raw
    assert "..." in raw


def test_format_lines_no_description_when_absent():
    node = _make_node("root", specs=[_make_spec("harness", "HARNESS.md")])
    raw = strip_ansi("\n".join(format_lines(node)))
    # Line should end after filename with no trailing spaces
    spec_line = [l for l in raw.splitlines() if "HARNESS.md" in l][0]
    assert not spec_line.endswith("  ")


def test_format_lines_nested_indentation():
    auth = _make_node("auth", specs=[_make_spec("skill", "SKILL.md", "Auth")])
    skills = _make_node("skills", children=[auth])
    node = _make_node("root", children=[skills])
    raw = strip_ansi("\n".join(format_lines(node)))
    # auth/ is nested under skills/, so it gets deeper indentation
    auth_line = [l for l in raw.splitlines() if "auth/" in l][0]
    assert auth_line.startswith("    ")  # indented under root's child_prefix


def test_format_lines_root_separator_between_items():
    spec = _make_spec("harness", "HARNESS.md")
    child = _make_node("skills", specs=[_make_spec("routing", "SKILLS.md")])
    node = _make_node("root", specs=[spec], children=[child])
    lines = format_lines(node)
    # A bare "│" separator should appear between spec and child at root level
    assert "│" in lines
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_map_references.py -k "format_lines" -v
```

Expected: `ImportError` — `format_lines` not defined yet.

- [ ] **Step 3: Implement format_lines**

Add to `agent-harnesses/scripts/map_references.py` (after `_truncate`):

```python
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
            desc = _truncate(item.get("description", ""), 60)
            line = f"{child_prefix}{item_connector}{badge}  {name}"
            if desc:
                line += f"  {desc}"
            lines.append(line)
        else:
            lines.extend(format_lines(item, child_prefix, item_is_last, depth + 1))

        if depth == 0 and not item_is_last:
            lines.append("│")

    return lines
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_map_references.py -v
```

Expected: All tests pass including the new `format_lines` tests.

- [ ] **Step 5: Commit**

```bash
git add agent-harnesses/scripts/map_references.py tests/test_map_references.py
git commit -m "feat: add format_lines renderer to map_references"
```

---

### Task 3: CLI entry point and SKILL.md update

**Files:**
- Modify: `agent-harnesses/scripts/map_references.py` (add `cmd_run` and `main`)
- Modify: `agent-harnesses/SKILL.md` (add script entry)
- Modify: `tests/test_map_references.py` (add CLI tests)

**Interfaces:**
- Consumes: `build_tree` and `format_lines` from Tasks 1 and 2
- Produces:
  - `cmd_run(harness_root: str) -> None`
  - `main() -> None`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_map_references.py`:

```python
def test_cmd_run_prints_tree_for_valid_harness(tmp_path, capsys):
    (tmp_path / "HARNESS.md").write_text("---\ndescription: Test harness\n---\n")
    cmd_run(str(tmp_path))
    out = capsys.readouterr().out
    assert tmp_path.name + "/" in out
    assert "HARNESS.md" in strip_ansi(out)
    assert "[harness]" in strip_ansi(out)


def test_cmd_run_shows_nested_skills(tmp_path, capsys):
    (tmp_path / "HARNESS.md").touch()
    skills = tmp_path / "skills"
    skills.mkdir()
    auth = skills / "auth"
    auth.mkdir()
    (auth / "SKILL.md").write_text("---\ndescription: Auth\n---\n")

    cmd_run(str(tmp_path))
    out = strip_ansi(capsys.readouterr().out)
    assert "skills/" in out
    assert "auth/" in out
    assert "SKILL.md" in out


def test_cmd_run_exits_on_nonexistent_path(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cmd_run(str(tmp_path / "nonexistent"))
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "error" in out.lower()


def test_cmd_run_exits_when_no_spec_files_found(tmp_path, capsys):
    empty = tmp_path / "empty_harness"
    empty.mkdir()
    with pytest.raises(SystemExit):
        cmd_run(str(empty))
    out = capsys.readouterr().out
    assert "no spec files" in out.lower() or "error" in out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_map_references.py -k "cmd_run" -v
```

Expected: `ImportError` — `cmd_run` not defined yet.

- [ ] **Step 3: Implement cmd_run and main**

Add to the bottom of `agent-harnesses/scripts/map_references.py`:

```python
def cmd_run(harness_root: str) -> None:
    root = Path(harness_root).resolve()
    if not root.exists():
        print(f"error: path not found: {harness_root}")
        sys.exit(1)

    node = build_tree(root, root)
    if node is None:
        print(f"error: no spec files found under {harness_root}")
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
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
pytest tests/test_map_references.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Update SKILL.md**

In `agent-harnesses/SKILL.md`, add the new script to the `## Skills` list:

Current:
```markdown
## Skills

- `scripts/disclose.py` — session-based harness explorer
- `scripts/reverse_disclose.py` — find all .md files above a path that reference it
```

Updated:
```markdown
## Skills

- `scripts/disclose.py` — session-based harness explorer
- `scripts/reverse_disclose.py` — find all .md files above a path that reference it
- `scripts/map_references.py` — print a visual tree of all spec files in a harness
```

- [ ] **Step 6: Run the script manually to verify visual output**

```bash
python agent-harnesses/scripts/map_references.py agent-harnesses
```

Verify:
- Tree starts with `agent-harnesses/`
- `SKILL.md` appears with a cyan `[skill]` badge (or `[routing]` for the harness-level file if present)
- Box-drawing characters (`├──`, `└──`, `│`) render correctly

- [ ] **Step 7: Commit**

```bash
git add agent-harnesses/scripts/map_references.py agent-harnesses/SKILL.md tests/test_map_references.py
git commit -m "feat: add map_references CLI and update SKILL.md"
```
