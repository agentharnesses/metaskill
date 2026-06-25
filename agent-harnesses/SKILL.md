---
name: metaskill
description: Progressive disclosure explorer for Agent Harnesses — enables agents without native harness integration to efficiently find relevant skills and references
---

Use this skill when you are pointed to a harness directory and need to discover which skills or references are relevant to your current task. It exposes only what you need, one layer at a time, so you don't flood your context with irrelevant content.

## Scripts

- `scripts/summarize.py` — print the tree and all spec descriptions; use this first to orient before starting a session
- `scripts/disclose.py` — session-based harness explorer
- `scripts/reverse_disclose.py` — find all .md files above a path that reference it
- `scripts/map_references.py` — print a visual tree of all spec files in a harness with inline short descriptions

## Leaf Type Classification

Directories in a harness are either a **group** (plain subdirectory) or a **leaf** (a named type such as `"skill"` or `"mcp-server"`). The `type` field in `disclose.py` item responses reflects this.

Two mechanisms control leaf detection, checked in priority order:

**1. `.harnessleaf` file (explicit override)**
A directory containing a `.harnessleaf` file is a leaf. The first non-empty line is the type name:

```
mcp-server
```

**2. `.leaf-detectors` config (structural rules)**
A `.leaf-detectors` file anywhere in the ancestor chain defines rules. Each non-comment line is `leaf_type=relative_path`. A directory is classified as that `leaf_type` if the specified path exists inside it:

```
skill=SKILL.md
mcp-server=MCP-SERVER.md
```

The nearest ancestor's config applies. `.harnessleaf` always beats `.leaf-detectors`.

If neither mechanism matches, the directory is a plain `"group"`.

**Description source for leaf directories:** `disclose.py` looks for `<LEAF-TYPE-UPPER>.md` inside the directory (e.g. `SKILL.md` for type `skill`, `MCP-SERVER.md` for type `mcp-server`).

---

## How to Use

### 0. Summarize the harness (do this first)

Before starting a disclosure session, run the summarize script to get a full picture of the harness structure and what each spec file is for:

```
python scripts/summarize.py <harness_path>
```

Output: the visual tree with inline short descriptions, followed by a flat list of every spec file with its full description. Use this to decide which mode and branches to target in the session that follows.

```
my-harness/
├── [harness]  HARNESS.md  — Root harness for the payments platform
│
└── skills/
    ├── [routing]  SKILLS.md  — Index of all available skills
    ├── auth/
    │   └── [skill]  SKILL.md  — Handles login, OAuth, and session management
    └── payments/
        └── [skill]  SKILL.md  — Checkout flow and refund handling

────────────────────────────────────────────────────────────

[harness]  HARNESS.md
  Root harness for the payments platform

[routing]  skills/SKILLS.md
  Index of all available skills

[skill]  skills/auth/SKILL.md
  Handles login, OAuth, and session management

[skill]  skills/payments/SKILL.md
  Checkout flow and refund handling
```

### 1. Start a session

```
python scripts/disclose.py <harness_path> [--mode bfs|dfs|hybrid] [--max-parallel N]
```

`bfs` (default) explores breadth-first — exhausts each level before going deeper. `dfs` dives into the first relevant group immediately. `hybrid` does BFS until the frontier is wide enough, then forks into parallel branch sessions.

**Choosing a mode:**
- Use `hybrid` when you can spawn sub-agents. It keeps doing BFS until the queue holds at least N groups, then forks each into an independent DFS session so sub-agents can explore in parallel.
- Use `bfs` when you cannot spawn sub-agents but the task could span multiple areas. You'll see all sibling groups before committing to any branch, which prevents missing something important in a folder you never peek.
- Use `dfs` when you already know which branch contains what you need (e.g., you've been told "the auth skill is under `skills/auth/`"). It gets you there without surveying siblings first.

**When in doubt: use `hybrid` if you can spawn sub-agents, `bfs` otherwise.**

The response is JSON with one of three statuses:

**`"exploring"`** — normal step, select from the listed items:

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

**`"parallelize"`** — emitted by hybrid mode when the BFS phase is complete. Each entry in `branches` is a pre-seeded DFS session already in the `exploring` state — `items` shows exactly what it is waiting for a `--select` decision on:

```json
{
  "status": "parallelize",
  "session": "a3f2c1b0",
  "hint": "Explore each branch independently; run in parallel if your framework supports it, otherwise process sequentially.",
  "branches": [
    {
      "session": "b1c2d3e4",
      "location": "skills/auth",
      "items": [
        {"id": 1, "type": "skill", "name": "login",   "description": "..."},
        {"id": 2, "type": "skill", "name": "oauth",   "description": "..."}
      ]
    },
    {
      "session": "f5a6b7c8",
      "location": "skills/payments",
      "items": [
        {"id": 1, "type": "skill", "name": "checkout", "description": "..."}
      ]
    }
  ],
  "resources": [...]
}
```

`resources` only appears when some resources were already found during the BFS phase; collect them alongside branch results. The parent session is deleted when this is emitted.

**How to handle `"parallelize"`:**
- Each branch is already in `exploring` state. Do **not** call `--select ""` or issue any start command — call `--select <ids>` immediately using the `items` list in the branch descriptor.
- If your framework supports parallel sub-agents: spawn one sub-agent per branch. Pass the branch `session` ID, the `items` list, and your task description so the sub-agent can make an informed first `--select` decision without any additional discovery step. Collect all `"complete"` responses and merge their `resources` lists.
- If your framework is sequential: process each branch session one at a time using the normal `--select` loop until each reaches `"complete"`.

**`"complete"`** — all queued directories exhausted:

Item types:
- `"group"` — a plain subdirectory; selecting it recurses into it
- any leaf type (e.g. `"skill"`, `"mcp-server"`) — a leaf directory; selecting it queues it as a result; read `<path>/<LEAF-TYPE-UPPER>.md` (e.g. `SKILL.md`, `MCP-SERVER.md`)
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
    {"type": "skill",      "name": "my-skill", "path": "/abs/path/to/skills/my-skill",   "session": "a3f2c1b0"},
    {"type": "references", "name": "guide.md", "path": "/abs/path/to/references/guide.md", "session": "a3f2c1b0"}
  ]
}
```

Every resource carries a `"session"` field identifying which session found it. This lets you trace results back to their origin after merging resources from multiple branch sessions.

### 4. Load your resources

- For leaf type entries (e.g. `skill`, `mcp-server`): read `<path>/<LEAF-TYPE-UPPER>.md` (e.g. `<path>/SKILL.md`, `<path>/MCP-SERVER.md`)
- For file entries: read `<path>` directly

### Cancel a session

```
python scripts/disclose.py --session <id> --cancel
```

---

## Harness Maintenance

Whenever you make a structural change to a harness — adding, moving, renaming, or removing any skill, reference, document, or directory — routing files (`SKILLS.md` indexes, `HARNESS.md`) may need to be updated. Use `reverse_disclose.py` to find which files are affected.

**Before any structural change:** run `reverse_disclose.py` on the target to find every routing file that currently links to it. Those files will need updating.

**After any structural change:** run `reverse_disclose.py` on the new path to confirm it is correctly referenced. If `references` is empty and you expected links, a routing file was missed — go back and update it.

For a brand new file with no existing links, run `reverse_disclose.py` on a sibling file in the same directory to discover which routing files cover that level, then add entries for the new file to each of those.

Never leave a routing file pointing to a stale path, and never add a file that nothing references — both break discoverability.

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
  - `kind` — `"harness"` for HARNESS.md, `"routing"` for index files (e.g. SKILLS.md), or a leaf type (e.g. `"skill"`, `"mcp-server"`) when the ancestor directory is itself a leaf
  - `path` — absolute path to the referencing file
- Results are ordered nearest ancestor first
