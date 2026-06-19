# Progressive Disclosure Script — Design Spec

## Overview

`scripts/disclose.py` enables LLM agents without native Agent Harnesses integration to efficiently traverse a harness via structured, iterative discovery. The agent peeks one directory at a time, selects relevant items by index, and accumulates a resource list — loading only what the task requires.

## Commands

```
# Start a new session (peeks harness root)
python scripts/disclose.py <harness_path> [--mode bfs|dfs]

# Continue with selections (comma-separated IDs, or "" to skip)
python scripts/disclose.py --session <id> --select "1,3"

# Cancel and clean up
python scripts/disclose.py --session <id> --cancel
```

- Default mode: `bfs`
- Session IDs: 8-char hex
- Session state stored at: `sessions/harness_<id>.json` within the metaskill directory
- Sessions auto-deleted on completion or cancel

## Peek Behavior

When peeking directory `D`, entries are classified as follows:

**Skip:**
- Hidden entries (prefix `.`)
- `HARNESS.md` (explicit)
- The file `<D.name.upper()>.md` — the routing summary for the current directory (e.g. `SKILLS.md` inside `skills/`, `DATABASE.md` inside `database/`)

**Classify remaining entries:**
- Subdir containing `SKILL.md` → type `"skill"`, description from `SKILL.md` frontmatter `description` field
- Subdir without `SKILL.md` → type `"group"`, description from `<SUBDIRNAME_UPPER>.md` frontmatter inside that subdir
- File → type = top-level ancestor folder name (e.g. `"references"` for a file under `references/`), description from file frontmatter `description` field or first content line

Items are displayed as a flat, mixed-type indexed list regardless of type.

## Selection Processing

After the agent provides selections:

- `skill` or file resource selected → added to `resources` list with absolute path
  - Skill path = skill directory (agent reads `SKILL.md` from within)
  - File path = file path directly
- `group` selected → added to explore queue
  - BFS: appended to end of queue
  - DFS: prepended to front of queue
- Unselected groups are not explored

When the queue is exhausted, output `status: complete`.

## Output Format

**Exploring:**
```json
{
  "status": "exploring",
  "session": "a3f2c1b0",
  "location": "skills/database",
  "context": "SQL and NoSQL database skills for...",
  "items": [
    {"id": 1, "type": "group",      "name": "queries",    "description": "Parameterized query helpers"},
    {"id": 2, "type": "skill",      "name": "migrations", "description": "Run and roll back migrations"},
    {"id": 3, "type": "references", "name": "schema.md",  "description": "Live schema reference"}
  ],
  "queued": 1,
  "found": 2
}
```

- `context`: body of the current directory's summary file (e.g. `DATABASE.md`), truncated to ~400 chars. Omitted if no summary exists.
- `queued`: number of directories pending in the explore queue
- `found`: number of resources accumulated so far
- `description` fields are omitted from items when absent

**Complete:**
```json
{
  "status": "complete",
  "session": "a3f2c1b0",
  "resources": [
    {"type": "skill",      "name": "migrations", "path": "/abs/path/to/skills/database/migrations"},
    {"type": "references", "name": "schema.md",  "path": "/abs/path/to/references/schema.md"}
  ]
}
```

## State Schema

```json
{
  "root": "/abs/path/to/harness",
  "mode": "bfs",
  "queue": ["/abs/path/to/next/dir"],
  "resources": [],
  "current_path": "/abs/path/to/current/dir",
  "current_items": [],
  "current_context": "optional summary body text"
}
```

`current_items` entries include a `path` field (stripped from items output to keep agent response lean).

## Frontmatter Parsing

YAML frontmatter delimited by `---` markers. Simple key: value parsing only — no nested structures needed. Falls back to first non-empty, non-heading content line if `description` field is absent.

## Files to Create

- `scripts/disclose.py` — the explorer script
- `SKILL.md` — frontmatter + operational instructions for the agent
- `sessions/` — runtime state directory (gitignored)
- `.gitignore` — ignore `sessions/`
