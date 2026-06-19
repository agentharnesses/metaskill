# metaskill

A skill for agents that don't have native [Agent Harnesses](https://agentharnesses.io) integration.

## Background

The [Agent Harnesses standard](https://agentharnesses.io) defines a way to package AI agent roles, skills, and contextual references into a portable directory structure. A harness contains a `HARNESS.md` entry point, a `skills/` directory of atomic capabilities, and a `references/` directory of supporting documentation. Large harnesses can contain dozens of skills and references organized into nested subdirectories.

Agents with native harness integration should employ progressive disclosure to navigate a harness effectively. Agents that only support **skills** (individual callable capabilities) don't have those tools and often, as a result, inefficiently traverse large harnesses.

The "agent harnesses metaskill", exposed to agents as "agent-harnesses" bridges that gap by exposing tools for progressive exposure of a harness to the agent, allowing agents to more rapidly and robustly explore large harnesses.

## Core Principles

**Programmatic Progressive Disclosure**

Rather than loading a harness all at once, metaskill exposes a script (`disclose.py`) that mimics the discovery and activation tools a natively integrated agent would have. The agent peeks one directory level at a time, sees a compact indexed list of what's there, selects only what's relevant to its current task, and repeats until it has a precise list of resources to load. Irrelevant branches are never explored.

**Skill-Based Invocation**

Some agent runtimes, like claude, do not support nested skill structures. "agent-harnesses" acts as a proxy: by invoking a single skill (`agent-harnesses`), an agent gains access to the full progressive disclosure workflow without needing any harness-specific tooling to support nested skill structures.

## Structure

```
metaskill/
├── agent-harnesses/       # The skill — invoke this to explore a harness
│   ├── SKILL.md           # Agent instructions and usage
│   ├── scripts/
│   │   └── disclose.py    # Progressive disclosure CLI
│   └── sessions/          # Runtime session state (gitignored)
└── tests/                 # Test suite for disclose.py
```

## How Progressive Disclosure Works

When an agent invokes the `agent-harnesses` skill and needs to explore a harness at `/path/to/some-harness`, it runs `disclose.py` in a loop:

### 1. Start a session

```
python agent-harnesses/scripts/disclose.py /path/to/some-harness
```

Returns a compact JSON snapshot of the harness root — one entry per top-level directory or file, with names and descriptions:

```json
{
  "status": "exploring",
  "session": "a3f2c1b0",
  "location": ".",
  "items": [
    {"id": 1, "type": "group", "name": "skills",     "description": "All agent capabilities"},
    {"id": 2, "type": "group", "name": "references", "description": "Brand and infrastructure docs"}
  ],
  "queued": 0,
  "found": 0
}
```

### 2. Select relevant items

The agent reads the list and responds with only the IDs of items relevant to its task:

```
python agent-harnesses/scripts/disclose.py --session a3f2c1b0 --select "1"
```

- Selecting a **group** queues it for exploration and returns its contents on the next call
- Selecting a **skill** or **file** adds it directly to the accumulated resource list
- Unselected groups are never explored

### 3. Repeat until complete

The loop continues, one directory level at a time, until the queue is exhausted:

```json
{
  "status": "complete",
  "session": "a3f2c1b0",
  "resources": [
    {"type": "skill",      "name": "auth",      "path": "/path/to/some-harness/skills/auth"},
    {"type": "references", "name": "schema.md", "path": "/path/to/some-harness/references/schema.md"}
  ]
}
```

The agent then reads only those resources — `<skill-path>/SKILL.md` for skills, the file directly for references.

### Traversal modes

`--mode bfs` (default) exhausts each level before going deeper — best when exploring an unfamiliar harness or when the task might span multiple areas.

`--mode dfs` dives into the first selected group immediately — best when you already know which branch contains what you need.

## What Gets Classified as What

When `disclose.py` peeks a directory, each entry is classified:

| Entry | Classified as | Description source |
|-------|---------------|--------------------|
| Directory containing `SKILL.md` | `"skill"` | `SKILL.md` frontmatter `description` field |
| Directory without `SKILL.md` | `"group"` | `<DIRNAME_UPPER>.md` inside that dir (e.g. `DATABASE.md` inside `database/`) |
| File | Type = parent top-level folder name (e.g. `"references"`) | File frontmatter `description` field or first content line |

Summary files like `SKILLS.md`, `REFERENCES.md`, and `HARNESS.md` are not provided to the model as an end result as they exist for routing purposes.

## Installation

### Claude Code — global (all projects)

Symlink the `agent-harnesses` skill into your user skills directory so Claude Code can invoke it from any project:

```bash
git clone https://github.com/agentharnesses/metaskill
ln -s "$(pwd)/metaskill/agent-harnesses" ~/.claude/skills/agent-harnesses
```

The skill will be available to Claude as `agent-harnesses`.

### Claude Code — project-local (one project)

To limit the skill to a single project, symlink into that project's `.claude/skills/` directory instead:

```bash
git clone https://github.com/agentharnesses/metaskill
mkdir -p /path/to/your/project/.claude/skills
ln -s "$(pwd)/metaskill/agent-harnesses" /path/to/your/project/.claude/skills/agent-harnesses
```

### Other Agent Skills-compatible runtimes

Copy or symlink `agent-harnesses/` wherever your runtime loads skills from, then invoke it as `agent-harnesses`. Consult your runtime's documentation for the exact skill directory path.

---

## Running the Tests

```bash
python3 -m pytest tests/ -v
```

32 tests covering frontmatter parsing, classification, peek logic, session management, BFS/DFS traversal, and end-to-end CLI behavior.
