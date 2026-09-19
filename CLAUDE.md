# fable-research (UAEK)

Project type: `python`. Wired to the shared **devkit** at `../devkit`
(re-run `bash link-devkit.sh` to re-wire after devkit changes; `copier update`
is not used because this project was wired manually, not bootstrapped via copier).

## Shared tooling

This project reuses devkit rather than copying it. Wired-in agents (hardlink, live):
`code-reviewer`, `code-explorer` — see `.claude/agents/`.
Wired-in skill (junction, live): `knowledge-management` — see `.claude/skills/`.

## Knowledge base

Before solving something that might already be known, consult the shared KB:
`grep -ri "<term>" ../devkit/kb/` and read `../devkit/kb/INDEX.md`. The
`knowledge-management` skill (wired into `.claude/skills/`) triggers this automatically.
`../devkit/handbook/Index.md` catalogs thick reference manuals — consult on demand, do not preload.

## Project notes

<!-- Add project-specific commands, gotchas, dependency relationships, and architecture below. -->
