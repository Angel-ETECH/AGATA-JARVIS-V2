import json
import threading
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable

from core.paths import BASE_DIR
from core.logging import get_logger

log = get_logger("jarvis.scheduler")

SCHEDULE_FILE = BASE_DIR / "config" / "schedule.json"
_lock = threading.Lock()
_tasks: list[dict] = []
_running = False


def _load_tasks():
    global _tasks
    try:
        if SCHEDULE_FILE.exists():
            _tasks = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    except Exception:
        _tasks = []


def _save_tasks():
    try:
        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULE_FILE.write_text(json.dumps(_tasks, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.error("Failed to save schedule: %s", e)


def _run_scheduler():
    global _running, _tasks
    _running = True
    while _running:
        now = datetime.now()
        with _lock:
            for task in _tasks:
                if not task.get("enabled", True):
                    continue
                last_run = task.get("last_run")
                interval_min = task.get("interval_minutes", 60)

                should_run = False
                if last_run:
                    last = datetime.fromisoformat(last_run)
                    if (now - last).total_seconds() >= interval_min * 60:
                        should_run = True
                else:
                    should_run = True

                if should_run:
                    log.info("Running scheduled task: %s", task.get("name", "unnamed"))
                    task["last_run"] = now.isoformat()
                    _execute_task(task)

            _save_tasks()
        time.sleep(30)


def _execute_task(task: dict):
    action = task.get("action", "")
    try:
        if action == "open_app":
            app = task.get("app", "")
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", app], shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app])
            else:
                subprocess.Popen([app])

        elif action == "run_command":
            cmd = task.get("command", "")
            subprocess.Popen(cmd, shell=True)

        elif action == "reminder":
            pass

        elif action == "backup":
            from actions.backup import _run_backup
            source = task.get("source", "")
            dest = task.get("destination", "")
            if source and dest:
                _run_backup(source, dest)

    except Exception as e:
        log.error("Scheduled task failed: %s", e)


_scheduler_thread = None


def _ensure_scheduler():
    global _scheduler_thread, _running
    _load_tasks()
    if not _running:
        _scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
        _scheduler_thread.start()


def scheduler(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "list")

    _ensure_scheduler()

    if action == "list":
        with _lock:
            if not _tasks:
                return "No hay tareas programadas, senor."
            lines = ["Tareas programadas:"]
            for i, t in enumerate(_tasks, 1):
                status = "ACTIVA" if t.get("enabled", True) else "PAUSADA"
                last = t.get("last_run", "nunca")
                interval = t.get("interval_minutes", 60)
                lines.append(
                    f"  [{i}] {t.get('name', 'Sin nombre')} | "
                    f"Cada {interval}min | Estado: {status} | "
                    f"Ultima: {last[:16] if last != 'nunca' else last}"
                )
            return "\n".join(lines)

    elif action == "add":
        name = p.get("name", "Tarea sin nombre")
        task_action = p.get("task_action", "reminder")
        interval = int(p.get("interval_minutes", 60))
        extra = p.get("extra", "")

        task = {
            "name": name,
            "action": task_action,
            "interval_minutes": interval,
            "enabled": True,
            "last_run": None,
        }
        if task_action == "open_app":
            task["app"] = extra
        elif task_action == "run_command":
            task["command"] = extra
        elif task_action == "backup":
            parts = extra.split("->") if "->" in extra else [extra, ""]
            task["source"] = parts[0].strip()
            task["destination"] = parts[1].strip() if len(parts) > 1 else ""

        with _lock:
            _tasks.append(task)
            _save_tasks()

        return f"Tarea '{name}' agregada. Se ejecutara cada {interval} minutos."

    elif action == "remove":
        idx = int(p.get("index", 0))
        with _lock:
            if 1 <= idx <= len(_tasks):
                removed = _tasks.pop(idx - 1)
                _save_tasks()
                return f"Tarea '{removed.get('name')}' eliminada."
            return f"Indice invalido. Hay {len(_tasks)} tareas."

    elif action == "toggle":
        idx = int(p.get("index", 0))
        with _lock:
            if 1 <= idx <= len(_tasks):
                t = _tasks[idx - 1]
                t["enabled"] = not t.get("enabled", True)
                _save_tasks()
                status = "activada" if t["enabled"] else "pausada"
                return f"Tarea '{t.get('name')}' {status}."
            return f"Indice invalido. Hay {len(_tasks)} tareas."

    elif action == "run_now":
        idx = int(p.get("index", 0))
        with _lock:
            if 1 <= idx <= len(_tasks):
                task = _tasks[idx - 1]
                _execute_task(task)
                task["last_run"] = datetime.now().isoformat()
                _save_tasks()
                return f"Tarea '{task.get('name')}' ejecutada."
            return f"Indice invalido."

    else:
        return f"Accion desconocida: {action}. Usa: list, add, remove, toggle, run_now"
