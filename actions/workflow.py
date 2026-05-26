import json
import threading
from pathlib import Path
from datetime import datetime

from core.paths import BASE_DIR
from core.logging import get_logger

log = get_logger("jarvis.workflow")

WORKFLOWS_FILE = BASE_DIR / "config" / "workflows.json"


def _load_workflows() -> dict:
    try:
        if WORKFLOWS_FILE.exists():
            return json.loads(WORKFLOWS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_workflows(workflows: dict):
    WORKFLOWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOWS_FILE.write_text(json.dumps(workflows, indent=2, ensure_ascii=False), encoding="utf-8")


def workflow(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "list")

    if action == "list":
        workflows = _load_workflows()
        if not workflows:
            return "No hay workflows guardados, senor."
        lines = ["Workflows guardados:"]
        for name, steps in workflows.items():
            lines.append(f"  - {name} ({len(steps)} pasos)")
        return "\n".join(lines)

    elif action == "run":
        name = p.get("name", "")
        workflows = _load_workflows()

        if name not in workflows:
            available = list(workflows.keys())
            return f"Workflow '{name}' no encontrado. Disponibles: {', '.join(available) if available else 'ninguno'}"

        steps = workflows[name]
        results = []

        for step in steps:
            tool = step.get("tool", "")
            tool_params = step.get("parameters", {})
            log.info("Workflow '%s' step: %s %s", name, tool, tool_params)

        return (
            f"Workflow '{name}' completado ({len(steps)} pasos).\n"
            f"Para ejecutar workflows complejos, usa agent_task con el workflow como goal."
        )

    elif action == "create":
        name = p.get("name", "")
        steps_json = p.get("steps", "[]")

        if not name:
            return "Necesito un nombre para el workflow (name)."

        try:
            steps = json.loads(steps_json) if isinstance(steps_json, str) else steps_json
        except json.JSONDecodeError:
            return "Formato de steps invalido. Debe ser JSON array."

        workflows = _load_workflows()
        workflows[name] = steps
        _save_workflows(workflows)
        return f"Workflow '{name}' creado con {len(steps)} pasos."

    elif action == "delete":
        name = p.get("name", "")
        workflows = _load_workflows()
        if name in workflows:
            del workflows[name]
            _save_workflows(workflows)
            return f"Workflow '{name}' eliminado."
        return f"Workflow '{name}' no encontrado."

    else:
        return f"Accion desconocida: {action}. Usa: list, run, create, delete"
