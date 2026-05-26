import subprocess
import sys
import platform
from pathlib import Path

from core.logging import get_logger

log = get_logger("jarvis.terminal")


def _detect_python() -> str:
    try:
        result = subprocess.run(
            [sys.executable or "python", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return sys.executable or "python"
    except Exception:
        pass
    for candidate in ["python", "python3", "py"]:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                return candidate
        except Exception:
            pass
    return "python"


def _run_command(command: str, timeout: int = 30, cwd: str | None = None) -> str:
    system = platform.system().lower()

    if system == "windows":
        is_venv_activate = "activate" in command.lower() and ".ps1" in command.lower()
        exec_policy = "-ExecutionPolicy Bypass" if is_venv_activate else ""
        shell_cmd = ["powershell", exec_policy, "-Command", command] if exec_policy else ["powershell", "-Command", command]
        shell_cmd = [s for s in shell_cmd if s]
    elif system == "darwin":
        shell_cmd = ["zsh", "-c", command]
    else:
        shell_cmd = ["bash", "-c", command]

    try:
        result = subprocess.run(
            shell_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd or str(Path.home()),
        )
        output = result.stdout.strip()
        error = result.stderr.strip()

        if is_venv_activate and result.returncode == 0:
            return f"Virtual environment activated. Python: {_detect_python()}"

        if "executionpolicy" in error.lower() and "restricted" in error.lower():
            parts = ["[OUTPUT]"]
            if output:
                parts.append(output)
            parts.append("[ERROR] PowerShell execution policy restricted. Re-running with Bypass...")
            parts.append("[INFO] Try: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned")
            return "\n\n".join(parts)

        parts = []
        if output:
            parts.append(f"[OUTPUT]\n{output}")
        if error:
            parts.append(f"[ERROR]\n{error}")

        if not parts:
            if result.returncode == 0:
                return "Command executed successfully with no output."
            return f"Command failed (exit code {result.returncode}) with no output."

        status = f"[EXIT CODE] {result.returncode}"
        parts.append(status)
        return "\n\n".join(parts)

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except FileNotFoundError as e:
        return f"Shell not found: {e}"
    except Exception as e:
        return f"Execution error: {e}"


def terminal(parameters: dict, player=None, speak=None) -> str:
    command = parameters.get("command", "").strip()
    timeout = int(parameters.get("timeout", 30))
    cwd = parameters.get("cwd", "").strip() or None

    if not command:
        return "No command provided. Tell me what to execute."

    log.info(f"[Terminal] Executing: {command[:200]}")
    if player:
        player.write_log(f"[Terminal] $ {command[:200]}")

    result = _run_command(command, timeout, cwd)

    truncated = result
    if len(truncated) > 2000:
        truncated = truncated[:1997] + "..."

    return truncated
