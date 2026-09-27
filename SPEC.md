# Jev decision kit

Locked 2026-09-25.

## Decision model

- JEV scores before the agent speaks. Each door in `host/gate.py` is a separate yes/no on the original sentence. A trained door is kept only when the sentence names that job and its yes-probability is at or above 0.4. Untrained plugin doors can pass on the name alone. A nearby 不要 drops that mention; a later 还是用 can take it back. Every such door is kept. None means do it yourself.
- The door is the local jobs (data, files, browser, video, thesis, and the other entries in that file). The rest of the cabinet stays browsable and is not an option.
- The agent receives that decision and follows it. It does not choose whether to ask, and it does not pick again.
- The scores come from `models/jev/head.json`, trained by `python -m host.train_jev` on door wording. That file is the selector. Laya is not on this path.

## Library

- Canonical copies live under `skills/<category>/<skill-name>/` inside this project.
- Category folder ids: `code`, `web`, `prompts`, `thesis`, `research`, `design`, `docs`, `market`, `media`, `router`, `other`.
- First import sorts by name keywords. Moving a skill later means moving its directory between these folders.
- Sources, in priority order (first name wins):
  1. `%USERPROFILE%\.cursor\skills`
  2. `%USERPROFILE%\.openclaw\workspace\skills` (skip junctions)
  3. `%USERPROFILE%\.agents\skills`
- Original folders are not moved and not deleted.
- A skill is a directory with `SKILL.md` at its root.
- Category changes move the directory inside this kit only.

## Tools

- Version 1 tools are the `scripts/` files that ship inside a skill.
- No separate machine-wide command registry.

## Not in this kit

- Jev Ultrafast (browser agent, TypeSafe API).
- jev-chat-windows (cloud Jev + chat overlay).
- storyflow (story harness).
