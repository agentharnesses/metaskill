---
name: metaskill
description: Source of two skills — agent-harnesses, the progressive-disclosure bridge that lets agents without native Agent Harnesses integration explore a large harness one directory level at a time, and harnessify, which surveys a repo and authors real routing for it.
---

## Upon loading the Harness

This repo packages two skills, each its own top-level directory (per the spec, top-level directory
names are chosen by the author; this repo's author named each after the one thing it contains —
still true now that there are two, not one). No `skills/` wrapper folder: at this size (two
skills), a routed `skills/SKILLS.md` indirection layer would add a hop without adding real
navigational value — this section just describes both directly, matching how the rest of this
small repo is already documented in flat prose rather than progressive disclosure on itself.

**`agent-harnesses/`** — the progressive-disclosure skill itself; see `README.md` for what it's
for. Its own directory name is load-bearing, not cosmetic: `vendor/cli`'s `ahar init --metaskill`
clones this repo and hardcodes `agent-harnesses/` as the source path to copy from — moving or
renaming this directory would break every existing `ahar init --metaskill` install. Don't move it.
- `agent-harnesses/SKILL.md` — the instructions an invoking agent actually reads: how to run a `disclose.py` session (start → select → repeat until `"complete"`), the three response shapes (`exploring`/`parallelize`/`complete`), and the reverse-disclosure maintenance workflow.
- `agent-harnesses/scripts/` — `disclose.py` (the CLI itself), `reverse_disclose.py` (given a path, find every routing/harness file above it that links to it — used when adding/moving/removing files to know what needs updating), `map_references.py`, `summarize.py`.
- `agent-harnesses/sessions/` — gitignored runtime state for in-progress `disclose.py` sessions; not source.
- `agent-harnesses/.leaf-detectors` — `skill=SKILL.md`, i.e. any directory containing a `SKILL.md` is a skill leaf. Notably scoped *inside* the skill directory itself rather than at this repo's own root.

**`harnessify/`** — added 2026-08-21, alongside the `traversal-compare` harnessify pipeline (see
that repo's `references/architecture.md` and the parent `agentdev` meta-repo's diary). Given a repo
with a bare `HARNESS.md` and nothing else (`ahar init`'s minimal default), surveys the repo's real
structure and authors real routing for it — `HARNESS.md` content, nested routing files, leaf
descriptors where they genuinely fit — grounded in what's actually there, never a template. See
`harnessify/SKILL.md` for the full process.

`tests/` — pytest suite (32 tests per `README.md`) covering `agent-harnesses`' own frontmatter parsing, classification, peek logic, session management, BFS/DFS traversal, and end-to-end CLI behavior — each test builds its own fabricated `.leaf-detectors`/harness fixtures in a temp dir rather than depending on the real one above.

## Distribution

Both skills are meant to be git-cloned and then symlinked (not copied) into wherever an agent
runtime loads skills from — e.g. `toprope-agentdev`'s own `.claude/skills/agent-harnesses` is a
symlink straight into a checkout of this repo's `agent-harnesses/`, not a plain directory. If this
repo has drifted from what a symlink target expects, the fix belongs here, not in a hand-copied
duplicate — see the `toprope-agentdev` diary entry `2026-08-18-1523-routing-filename-bug.md` for
the incident that established this. `vendor/cli`'s `ahar init --metaskill` does an actual `git
clone` + copy (not a symlink) instead, and installs both `agent-harnesses/` and `harnessify/`
together from the one clone — a harnessify session needs `harnessify` discoverable in the same
`.claude/skills/` a `load harness` turn just populated, not a second separate install step.

## Testing

```
python3 -m pytest tests/ -v
```

## Skills

This repo packages two skills directly at its root — `agent-harnesses/SKILL.md` and
`harnessify/SKILL.md` — described above. No `skills/` bucket; see "Upon loading the Harness" for
why.

## References

No references bucket yet — `README.md` and each skill's own `SKILL.md` already cover everything this repo's own maintainers need.
