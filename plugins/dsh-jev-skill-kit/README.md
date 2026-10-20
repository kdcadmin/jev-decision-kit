# dsh-jev-skill-kit

A DeepSeek Harness plugin that asks a **local** skill-selection model which skills a task needs, then injects that choice as a one-line preface at the start of the turn.

```
jev-decision: 已选定：docx、office-docx。不要读取技能，不要再挑选。
```

The agent then loads exactly those skills instead of browsing or picking again. Selection runs on the machine — no network call, no API key.

## What it does

On every new turn (`agent/pre-step`), before the model speaks:

1. Reads the user's message text.
2. Asks the bundled helper process (a local HTTP service on `127.0.0.1`) for a selection.
3. Prepends the resulting one-line preface to the first user message of the turn.

It also reports subagent start/stop events to the same helper, so the kit's local dashboard can show delegation history.

If the turn already starts with `jev-decision:` (or the legacy `【技能柜】`), nothing is injected — a user typing the marker mid-sentence still gets a selection.

## Requirement: the jev-decision-kit workspace

This plugin is the DeepSeek Harness adapter of [jev-decision-kit](https://github.com/kdcadmin/jev-decision-kit). It does **not** ship the model or the scoring code; it calls the ones in that workspace:

- Python venv at `<kit>/.venv` (Windows `Scripts/python.exe`, macOS/Linux `bin/python`)
- `<kit>/host/preface_worker.py` and the trained weights in `<kit>/models/jev/`

Without the kit the plugin **stays silent**: it injects nothing and writes one `kit-missing` line to `<kit>/runtime/harness-plugin.log`. It will not prefix your turns with an error.

## Install

1. Clone and set up the kit ([README](https://github.com/kdcadmin/jev-decision-kit#readme)).
2. Install this plugin into a DSH profile:
   - **GUI**: 设置 → 插件 → 添加插件 → the absolute path to this directory, then restart DSH and open a new session.
   - **CLI** (non-desktop profiles): `dsh plugin add <absolute path to this directory>`
3. The profile must use a `link:` (or `file:`) dependency — that is how the plugin finds the kit after a reinstall. See the kit's `INTEGRATION.md` for the exact steps.

Where the kit lives, in order of precedence:

1. `JEV_KIT_ROOT` environment variable
2. `<plugin dir>/kit-root.txt`
3. `%LOCALAPPDATA%/jev-skill-kit/root.txt` (Windows) or `~/.local/share/jev-skill-kit/root.txt`
4. the source path recorded in the profile's `package.json` (`link:`/`file:` dependency)
5. two directories above the plugin (a plain checkout)

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `JEV_KIT_ROOT` | — | Kit workspace override |
| `JEV_WORKER_WAIT_MS` | `8000` | How long to wait for the helper process to come up |
| `JEV_HARNESS_LOG` | `<kit>/runtime/harness-plugin.log` | Diagnostics log (one JSON line per event) |

## Privacy

Everything runs locally. The plugin starts a `127.0.0.1` helper process and posts the task text to it; nothing leaves the machine. The helper is spawned with `windowsHide: true` and no `detached`, so no console window appears.

## License

MIT — same as the parent workspace.
