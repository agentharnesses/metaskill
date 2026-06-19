# map_references Script — Design Spec

## Overview

`scripts/map_references.py` walks an Agent Harnesses directory tree and prints a human-readable ASCII tree of every spec file found. It is a visualization tool — output is intended for humans to read at a glance, not for machine consumption.

Spec files are the structural files that organize the harness:

| Pattern | Kind |
|---|---|
| `HARNESS.md` in any directory | `harness` |
| `SKILL.md` in any directory | `skill` |
| `<DIRNAME_UPPER>.md` in a directory | `routing` |

## CLI

```
python scripts/map_references.py [harness_root]
```

- `harness_root` — path to the harness root directory; defaults to CWD if omitted
- Auto-detects root by walking up from `harness_root` to find the nearest ancestor containing `HARNESS.md`; falls back to `harness_root` itself if none found

No additional flags.

## Implementation

`map_references.py` imports and reuses functions from the two existing scripts rather than reimplementing filesystem traversal:

- `spec_files_in(directory)` from `reverse_disclose.py` — finds spec files at a given directory
- `peek(directory, root)` from `disclose.py` — lists child entries using the established skip/classify logic (hidden dirs, `sessions/`, routing summary files are all handled)
- `get_description(path, kind)` from `disclose.py` — reads frontmatter `description` or falls back to first content line

The traversal is recursive:
1. At each directory, call `spec_files_in` to collect local spec files
2. Call `peek` to discover child groups and skills
3. Recurse into each child
4. **Prune empty branches** — omit any directory node whose subtree contains no spec files

## Output Format

Plain stdout, ASCII tree using box-drawing characters. ANSI color is applied to kind badges.

```
my-harness/
├── [harness]  HARNESS.md     My harness for AI agents
│
├── skills/
│   ├── [routing]  SKILLS.md  All available skills
│   ├── auth/
│   │   └── [skill]  SKILL.md    Authentication and session flows
│   └── database/
│       └── [skill]  SKILL.md    SQL helpers and migrations
│
└── references/
    ├── [routing]  REFERENCES.md  Reference library index
    └── api-guide/
        └── [skill]  SKILL.md    REST API usage guide
```

- Kind badges are fixed-width and ANSI-colored: `[harness]` in red/bold, `[routing]` in yellow, `[skill]` in cyan
- Descriptions are truncated at 60 characters
- A blank line is inserted after each directory that has children, to improve scannability
- Directories with no spec files anywhere in their subtree are omitted

## SKILL.md Update

Add `scripts/map_references.py` to the Skills list in `SKILL.md`:

```
- `scripts/map_references.py` — print a visual tree of all spec files in a harness
```

## Files to Create / Modify

- `scripts/map_references.py` — the new script
- `agent-harnesses/SKILL.md` — add entry to Skills list
