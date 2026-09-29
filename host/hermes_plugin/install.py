"""Install a thin Hermes plugin that always loads this checkout's current hook code."""
from __future__ import annotations

from pathlib import Path
import json
import sys


def _read_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return stream.read()


def _write_exact(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent


def install_shell_hooks(config_path: Path, *, python: Path | None = None, approve=None) -> dict:
    """Add only JEV hooks, preserving every unrelated Hermes setting."""
    python = python or Path(sys.executable)
    script = ROOT / "host" / "hermes_shell_hook.py"
    command = f'"{python.as_posix()}" "{script.as_posix()}"'
    events = {"pre_llm_call": 180, "pre_tool_call": 15, "subagent_start": 15, "subagent_stop": 15}
    original = _read_exact(config_path)
    if "hooks: {}" not in original and "# JEV_SHELL_HOOKS_V1" not in original:
        raise RuntimeError("Hermes hooks config is not empty; refusing to overwrite it")
    if "# JEV_SHELL_HOOKS_V1" in original:
        return {"changed": False, "command": command}
    lines = ["hooks: # JEV_SHELL_HOOKS_V1"]
    for event, timeout in events.items():
        lines.extend([f"  {event}:", f"    - command: {json.dumps(command)}", f"      timeout: {timeout}"])
        if event == "pre_tool_call":
            lines.append('      matcher: "delegate_task"')
    newline = "\r\n" if "\r\n" in original else "\n"
    updated = original.replace("hooks: {}", newline.join(lines), 1)
    backup = config_path.with_name(config_path.name + ".jev.bak")
    if not backup.exists():
        backup.write_bytes(config_path.read_bytes())
    temporary = config_path.with_name(config_path.name + ".jev.tmp")
    _write_exact(temporary, updated)
    temporary.replace(config_path)
    if approve is not None:
        for event in events:
            approve(event, command)
    return {"changed": True, "command": command}


def uninstall_shell_hooks(config_path: Path) -> bool:
    original = _read_exact(config_path)
    if "# JEV_SHELL_HOOKS_V1" not in original:
        return False
    lines = original.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith("hooks: # JEV_SHELL_HOOKS_V1"))
    end = next((i for i in range(start + 1, len(lines)) if lines[i] and not lines[i][0].isspace() and lines[i].strip()), len(lines))
    newline = "\r\n" if "\r\n" in original else "\n"
    lines[start:end] = ["hooks: {}" + newline]
    _write_exact(config_path, "".join(lines))
    return True


def install_plugin(target: Path | None = None) -> dict:
    target = target or (Path.home() / ".hermes" / "plugins" / "jev-skill-kit")
    target.mkdir(parents=True, exist_ok=True)
    shim = (
        "from pathlib import Path\n"
        "import sys\n"
        f"ROOT = Path({str(ROOT)!r})\n"
        "if str(ROOT) not in sys.path:\n"
        "    sys.path.insert(0, str(ROOT))\n"
        "from host.hermes_plugin import register\n"
    )
    desired = {
        "__init__.py": shim,
        "plugin.yaml": (SOURCE / "plugin.yaml").read_text(encoding="utf-8"),
    }
    changed = False
    for name, content in desired.items():
        path = target / name
        previous = path.read_text(encoding="utf-8") if path.is_file() else None
        if previous == content:
            continue
        if previous is not None:
            backup = target / (name + ".jev.bak")
            if not backup.exists():
                backup.write_text(previous, encoding="utf-8")
        temporary = target / (name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
        changed = True
    return {"path": str(target), "changed": changed}


if __name__ == "__main__":
    print(install_plugin())
