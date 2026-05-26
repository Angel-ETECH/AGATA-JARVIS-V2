import json
import time
import threading
from pathlib import Path
from datetime import datetime

from core.paths import BASE_DIR
from core.logging import get_logger

log = get_logger("jarvis.macro_recorder")

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import pynput
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

MACROS_FILE = BASE_DIR / "config" / "macros.json"
_recording = False
_events: list[dict] = []
_record_start = 0.0


def _load_macros() -> dict:
    try:
        if MACROS_FILE.exists():
            return json.loads(MACROS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_macros(macros: dict):
    MACROS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MACROS_FILE.write_text(json.dumps(macros, indent=2), encoding="utf-8")


def _record_mouse_movement():
    global _events, _recording, _record_start
    last_x, last_y = pyautogui.position()
    while _recording:
        x, y = pyautogui.position()
        if (x, y) != (last_x, last_y):
            elapsed = time.time() - _record_start
            _events.append({
                "type": "move",
                "x": x, "y": y,
                "time": round(elapsed, 3)
            })
            last_x, last_y = x, y
        time.sleep(0.05)


def _play_events(events: list[dict], speed: float = 1.0):
    if not events:
        return
    start = events[0]["time"]
    for evt in events:
        delay = (evt["time"] - start) / speed
        if delay > 0:
            time.sleep(delay)
            start = evt["time"]
        try:
            if evt["type"] == "move":
                pyautogui.moveTo(evt["x"], evt["y"])
            elif evt["type"] == "click":
                pyautogui.click(evt.get("x", 0), evt.get("y", 0),
                                button=evt.get("button", "left"))
            elif evt["type"] == "key":
                pyautogui.press(evt["key"])
            elif evt["type"] == "write":
                pyautogui.write(evt["text"], interval=0.02)
            elif evt["type"] == "hotkey":
                pyautogui.hotkey(*evt["keys"])
            elif evt["type"] == "scroll":
                pyautogui.scroll(evt.get("amount", 3))
        except Exception as e:
            log.warning("Macro playback error: %s", e)


def macro_recorder(parameters: dict | None = None, player=None, speak=None) -> str:
    global _recording, _events, _record_start

    if not HAS_PYAUTOGUI:
        return "Necesito pyautogui. Ejecuta: pip install pyautogui"

    p = parameters or {}
    action = p.get("action", "list")

    if action == "record":
        name = p.get("name", f"macro_{datetime.now().strftime('%H%M%S')}")
        duration = int(p.get("duration", 10))

        _events = []
        _recording = True
        _record_start = time.time()

        t = threading.Thread(target=_record_mouse_movement, daemon=True)
        t.start()

        return (
            f"Grabando macro '{name}' por {duration} segundos. "
            f"Haz los clicks y movimientos que quieras grabar. "
            f"La grabacion se detendra automaticamente."
        )

    elif action == "stop":
        if _recording:
            _recording = False
            name = p.get("name", f"macro_{datetime.now().strftime('%H%M%S')}")
            macros = _load_macros()
            macros[name] = _events
            _save_macros(macros)
            count = len(_events)
            _events = []
            return f"Macro '{name}' guardada con {count} eventos."
        return "No hay grabacion en curso."

    elif action == "play":
        name = p.get("name", "")
        speed = float(p.get("speed", 1.0))
        macros = _load_macros()

        if name not in macros:
            available = list(macros.keys())
            return f"Macro '{name}' no encontrada. Disponibles: {', '.join(available) if available else 'ninguna'}"

        events = macros[name]
        delay = int(p.get("delay", 3))
        return (
            f"Reproduciendo macro '{name}' ({len(events)} eventos, velocidad x{speed}). "
            f"Comenzando en {delay} segundos..."
        )

    elif action == "play_now":
        name = p.get("name", "")
        speed = float(p.get("speed", 1.0))
        macros = _load_macros()

        if name not in macros:
            return f"Macro '{name}' no encontrada."

        events = macros[name]
        t = threading.Thread(target=_play_events, args=(events, speed), daemon=True)
        t.start()
        return f"Reproduciendo macro '{name}'..."

    elif action == "list":
        macros = _load_macros()
        if not macros:
            return "No hay macros grabadas, senor."
        lines = ["Macros guardadas:"]
        for name, events in macros.items():
            lines.append(f"  - {name} ({len(events)} eventos)")
        return "\n".join(lines)

    elif action == "delete":
        name = p.get("name", "")
        macros = _load_macros()
        if name in macros:
            del macros[name]
            _save_macros(macros)
            return f"Macro '{name}' eliminada."
        return f"Macro '{name}' no encontrada."

    else:
        return f"Accion desconocida: {action}. Usa: record, stop, play, play_now, list, delete"
