import json
from pathlib import Path
from datetime import datetime, timedelta

from core.paths import BASE_DIR
from core.logging import get_logger

log = get_logger("jarvis.calendar")

EVENTS_FILE = BASE_DIR / "config" / "calendar_events.json"


def _load_events() -> list[dict]:
    try:
        if EVENTS_FILE.exists():
            return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_events(events: list[dict]):
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    EVENTS_FILE.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")


def _list_upcoming(events: list[dict], days: int = 7) -> str:
    now = datetime.now()
    cutoff = now + timedelta(days=days)

    upcoming = []
    for e in events:
        try:
            event_dt = datetime.fromisoformat(e.get("datetime", ""))
            if now <= event_dt <= cutoff:
                upcoming.append(e)
        except Exception:
            pass

    upcoming.sort(key=lambda e: e.get("datetime", ""))

    if not upcoming:
        return f"No hay eventos en los proximos {days} dias, senor."

    lines = [f"Eventos proximos ({days} dias):\n"]
    for e in upcoming:
        dt = datetime.fromisoformat(e["datetime"])
        lines.append(
            f"  {dt.strftime('%d/%m %H:%M')} | {e['title']}"
            + (f" | {e.get('location', '')}" if e.get("location") else "")
        )
    return "\n".join(lines)


def _list_all(events: list[dict]) -> str:
    if not events:
        return "No hay eventos agendados, senor."

    events.sort(key=lambda e: e.get("datetime", ""))
    lines = ["Todos los eventos:\n"]
    for e in events:
        dt = datetime.fromisoformat(e["datetime"])
        lines.append(
            f"  {dt.strftime('%d/%m/%Y %H:%M')} | {e['title']}"
            + (f" @ {e.get('location', '')}" if e.get("location") else "")
        )
    return "\n".join(lines)


def _add_event(events: list[dict], title: str, dt_str: str, location: str = "") -> str:
    try:
        datetime.fromisoformat(dt_str)
    except ValueError:
        return f"Formato de fecha invalido: {dt_str}. Usa YYYY-MM-DDTHH:MM"

    events.append({
        "title": title,
        "datetime": dt_str,
        "location": location,
        "created": datetime.now().isoformat(),
    })
    _save_events(events)
    return f"Evento '{title}' agregado para {dt_str}."


def _remove_event(events: list[dict], index: int) -> str:
    if 1 <= index <= len(events):
        removed = events.pop(index - 1)
        _save_events(events)
        return f"Evento '{removed['title']}' eliminado."
    return f"Indice invalido. Hay {len(events)} eventos."


def calendar_manager(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "upcoming")
    events = _load_events()

    if action == "upcoming":
        days = int(p.get("days", 7))
        return _list_upcoming(events, days)

    elif action == "list":
        return _list_all(events)

    elif action == "add":
        title = p.get("title", "")
        dt_str = p.get("datetime", "")
        location = p.get("location", "")
        if not title or not dt_str:
            return "Necesito title y datetime (formato: YYYY-MM-DDTHH:MM)."
        return _add_event(events, title, dt_str, location)

    elif action == "remove":
        index = int(p.get("index", 0))
        return _remove_event(events, index)

    elif action == "today":
        now = datetime.now()
        today_events = []
        for e in events:
            try:
                dt = datetime.fromisoformat(e["datetime"])
                if dt.date() == now.date():
                    today_events.append(e)
            except Exception:
                pass
        if not today_events:
            return "No tienes eventos hoy, senor."
        lines = ["Eventos de hoy:\n"]
        for e in sorted(today_events, key=lambda x: x["datetime"]):
            dt = datetime.fromisoformat(e["datetime"])
            lines.append(f"  {dt.strftime('%H:%M')} | {e['title']}")
        return "\n".join(lines)

    else:
        return f"Accion desconocida: {action}. Usa: upcoming, list, add, remove, today"
