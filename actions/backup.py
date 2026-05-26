import shutil
import time
from pathlib import Path
from datetime import datetime

from core.logging import get_logger

log = get_logger("jarvis.backup")


def _run_backup(source: str, destination: str) -> str:
    src = Path(source)
    dst = Path(destination)

    if not src.exists():
        return f"Origen no encontrado: {source}"

    try:
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            return f"Archivo respaldado: {dst}"
        else:
            if dst.exists():
                name = f"{src.name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                dst = dst.parent / name
            shutil.copytree(str(src), str(dst))
            return f"Carpeta respaldada: {dst}"
    except Exception as e:
        return f"Error al respaldar: {e}"


def backup(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "run")
    source = p.get("source", "")
    destination = p.get("destination", "")

    if action == "run":
        if not source:
            return "Necesito la carpeta o archivo de origen (source)."

        if not destination:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            src_path = Path(source)
            destination = str(Path.home() / "Desktop" / f"Backup_{src_path.name}_{ts}")

        return _run_backup(source, destination)

    elif action == "schedule":
        interval = p.get("interval_minutes", 1440)
        try:
            from actions.scheduler import scheduler as sched
            sched({
                "action": "add",
                "name": f"Backup de {source}",
                "task_action": "backup",
                "interval_minutes": interval,
                "extra": f"{source} -> {destination}",
            })
            return f"Backup programado cada {interval} minutos."
        except Exception as e:
            return f"Error al programar backup: {e}"

    else:
        return f"Accion desconocida: {action}. Usa: run, schedule"
