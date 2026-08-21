---
name: harnessify
description: Survey the current repo and author real Agent Harnesses routing for it — HARNESS.md content, nested routing files, and leaf descriptors grounded in what's actually here, not a template.
---

Use this skill when the current working directory is a repo that has a bare `HARNESS.md` (e.g.
freshly written by `ahar init`, with `TODO` placeholders) and nothing else — no routing files, no
skills/references buckets, no leaf structure. Your job is to give this specific repo real,
accurate Agent Harnesses routing, the same way a maintainer who actually understood the codebase
would author it by hand. This is understanding-work, not templating: a generic or boilerplate
routing file is worse than no routing file, since it would bias any comparison run against it
without adding real navigational value.

**You are the only pass this repo gets.** Nothing reviews or corrects your output before it's
used. Ground every claim in something you actually read — a README, a docstring, a real file's
contents, an existing test — never in what a repo *like this one* typically contains.

## Process

### 1. Survey before deciding anything

Read what's already there before inventing structure:
- Root `README.md`, `CONTRIBUTING.md`, or equivalent — often states the project's own mental model
  of its parts, which you should prefer over inventing your own.
- The top-level directory listing. For most languages, real package/module boundaries already
  exist and don't need to be discovered from scratch — Python packages (`__init__.py`), a
  `src/`/`lib/` layout, a monorepo's own workspace manifest, etc. Use these as your first-pass
  bucket boundaries rather than imposing an unrelated decomposition.
- A handful of representative files per candidate bucket — enough to write an accurate one- or
  two-sentence description, not exhaustive reading of every file.

### 2. Decide bucket boundaries and leaf types

Not every directory needs its own routing file, and not every repo needs a leaf-type ontology at
all — decide based on what's actually here, don't force one:

- A directory is worth its own routing file when it's large/varied enough that a flat description
  in its parent wouldn't be useful — mirrors why `skills/`/`references/` get their own `SKILLS.md`/
  `REFERENCES.md` in this standard's own convention, rather than everything living in one root
  `HARNESS.md`.
- A directory is worth a **leaf** type (a `.leaf-detectors` rule, e.g. `service=SERVICE.md` or
  `module=MODULE.md` — pick a name that fits what this repo actually calls its own units, don't
  default to `skill=SKILL.md` unless this repo genuinely has skill-shaped units) when it's better
  understood as one atomic, self-contained thing worth a dedicated descriptor file, not a group to
  keep recursing into. Many repos won't need this at all — a plain nested-routing-files structure
  with no leaves is a completely valid, often better, fit. Don't invent a leaf concept the repo
  doesn't have.

### 3. Author the routing

- Fill in `HARNESS.md`'s `TODO`s for real: a real `description`, a real "Upon loading the Harness"
  entry message, and (if you created any) a "## Skills"/"## References"-equivalent section listing
  the buckets you decided on.
- Every routing file is named after the **top-level directory it lives under**, and that name
  propagates unchanged through all nesting beneath it, resetting only at a nested `HARNESS.md`
  boundary — the exact convention `agent-harnesses/SKILL.md`'s "Routing Filenames and Nested
  Harnesses" section documents; if the metaskill is installed in this repo (`--metaskill` was used
  at `ahar init` time), read that section directly rather than re-deriving the rule from memory.
- Write `.leaf-detectors` only if step 2 decided this repo genuinely needs leaf typing.
- Descriptions must be specific to what you actually found in that directory — "handles user
  authentication via OAuth and session tokens," not "authentication-related code."

### 4. Validate before finishing

Run `ahar validate .` (or the harness root's path) and fix anything it flags. This is a free,
already-built correctness check — don't skip it and don't hand-roll your own.
