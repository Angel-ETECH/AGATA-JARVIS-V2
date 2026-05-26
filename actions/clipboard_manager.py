import time
import threading
from pathlib import Path
from datetime import datetime

from core.logging import get_logger

log = get_logger("jarvis.clipboard_manager")

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

_history: list[dict] = []
_max_history = 50
_lock = threading.Lock()


def _record_clipboard():
    global _history
    last = ""
    while True:
        try:
            current = pyperclip.paste()
            if current and current != last and len(current.strip()) > 0:
                with _lock:
                    if not _history or _history[-1].get("text") != current:
                        _history.append({
                            "text": current[:500],
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "length": len(current),
                        })
                        if len(_history) > _max_history:
                            _history = _history[-_max_history // 2:]
                last = current
        except Exception:
            pass
        time.sleep(0.5)


_watcher_started = False


def _ensure_watcher():
    global _watcher_started
    if not _watcher_started and HAS_PYPERCLIP:
        _watcher_started = True
        t = threading.Thread(target=_record_clipboard, daemon=True)
        t.start()


def clipboard_manager(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "list")

    if not HAS_PYPERCLIP:
        return "pyperclip no esta instalado, senor. Ejecuta: pip install pyperclip"

    _ensure_watcher()

    if action == "list":
        with _lock:
            if not _history:
                return "No hay historial del portapapeles aun, senor."
            lines = [f"Historial del portapapeles ({len(_history)} items):"]
            for i, h in enumerate(reversed(_history[-20:])):
                preview = h["text"].replace("\n", " ")[:80]
                lines.append(
                    f"  [{len(_history) - i}] {h['time']} | "
                    f"{h['length']} chars | {preview}..."
                )
            return "\n".join(lines)

    elif action == "get_last":
        with _lock:
            if not _history:
                return "Portapapeles vacio, senor."
            return _history[-1]["text"]

    elif action == "get_index":
        idx = int(p.get("index", 0))
        with _lock:
            if 1 <= idx <= len(_history):
                item = _history[idx - 1]
                pyperclip.copy(item["text"])
                return f"Copiado al portapapeles: {item['text'][:100]}..."
            return f"Indice invalido. Hay {len(_history)} items."

    elif action == "copy":
        text = p.get("text", "")
        if text:
            pyperclip.copy(text)
            return f"Copiado: {text[:100]}..."
        return "Necesito el texto a copiar."

    elif action == "clear":
        with _lock:
            count = len(_history)
            _history.clear()
        return f"Historial limpiado ({count} items eliminados)."

    else:
        return f"Accion desconocida: {action}. Usa: list, get_last, get_index, copy, clear"
