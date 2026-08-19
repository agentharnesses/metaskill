---
name: metaskill
description: Source of the agent-harnesses skill — the progressive-disclosure bridge that lets agents without native Agent Harnesses integration (skill-only runtimes) explore a large harness one directory level at a time instead of loading it all at once.
---

## Upon loading the Harness

This repo packages exactly one thing: the `agent-harnesses/` directory *is* the skill (frontmatter `description` in `agent-harnesses/SKILL.md` is what gets shown to an agent choosing whether to invoke it). There's no separate `skills/` wrapper folder — per the spec, top-level directory names are chosen by the author, and this repo's author chose to name it after the one thing it contains.

- `agent-harnesses/SKILL.md` — the instructions an invoking agent actually reads: how to run a `disclose.py` session (start → select → repeat until `"complete"`), the three response shapes (`exploring`/`parallelize`/`complete`), and the reverse-disclosure maintenance workflow.
- `agent-harnesses/scripts/` — `disclose.py` (the CLI itself), `reverse_disclose.py` (given a path, find every routing/harness file above it that links to it — used when adding/moving/removing files to know what needs updating), `map_references.py`, `summarize.py`.
- `agent-harnesses/sessions/` — gitignored runtime state for in-progress `disclose.py` sessions; not source.
- `agent-harnesses/.leaf-detectors` — `skill=SKILL.md`, i.e. any directory containing a `SKILL.md` is a skill leaf. Notably scoped *inside* the skill directory itself rather than at this repo's own root.
- `tests/` — pytest suite (32 tests per `README.md`) covering frontmatter parsing, classification, peek logic, session management, BFS/DFS traversal, and end-to-end CLI behavior — each test builds its own fabricated `.leaf-detectors`/harness fixtures in a temp dir rather than depending on the real one above.

## Distribution

This skill is meant to be git-cloned and then symlinked (not copied) into wherever an agent runtime loads skills from — e.g. `toprope-agentdev`'s own `.claude/skills/agent-harnesses` is a symlink straight into a checkout of this repo's `agent-harnesses/`, not a plain directory. If this repo has drifted from what a symlink target expects, the fix belongs here, not in a hand-copied duplicate — see the `toprope-agentdev` diary entry `2026-08-18-1523-routing-filename-bug.md` for the incident that established this.

## Testing

```
python3 -m pytest tests/ -v
```

## Skills

This repo *is* a single skill — see `agent-harnesses/SKILL.md` directly. No further skills bucket needed.

## References

No references bucket yet — `README.md` and `agent-harnesses/SKILL.md` already cover everything this repo's own maintainers need.
