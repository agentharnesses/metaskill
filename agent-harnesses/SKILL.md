---
name: metaskill
description: Progressive disclosure explorer for Agent Harnesses — enables agents without native harness integration to efficiently find relevant skills and references
---

Use this skill when you are pointed to a harness directory and need to discover which skills or references are relevant to your current task. It exposes only what you need, one layer at a time, so you don't flood your context with irrelevant content.

## Skills

- `scripts/disclose.py` — session-based harness explorer
- `scripts/reverse_disclose.py` — find all .md files above a path that reference it
- `scripts/map_references.py` — print a visual tree of all spec files in a harness

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

**Be selective.** Unselected groups are not explored. The goal is to load as little as possible while still getting all information relevent to solve a task.

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

---

## Reverse Disclosure

Use `scripts/reverse_disclose.py` for maintenance: given a file or directory, find every `.md` file above it (in ancestor directories, up to the harness root) that contains a markdown link to it.

```
python scripts/reverse_disclose.py <target_path> [--root <harness_root>]
```

- `target_path` — file or directory to look up
- `--root` — explicit search root; defaults to nearest ancestor containing `HARNESS.md`

**Output:**

```json
{
  "status": "complete",
  "target": "skills/auth/SKILL.md",
  "root": "/abs/path/to/harness",
  "self": {"path": "/abs/path/to/skills/auth/SKILL.md"},
  "references": [
    {"kind": "routing", "path": "/abs/path/to/skills/SKILLS.md"},
    {"kind": "harness", "path": "/abs/path/to/HARNESS.md"}
  ]
}
```

- `self` — present only when the target is a `.md` file
- `references` — each ancestor `.md` file that links to the target; each entry has:
  - `kind` — `"routing"` for SKILLS.md index files, `"harness"` for HARNESS.md
  - `path` — absolute path to the referencing file
- Results are ordered nearest ancestor first
