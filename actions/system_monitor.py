import json
import time
from datetime import datetime
from pathlib import Path

from core.logging import get_logger

log = get_logger("jarvis.system_monitor")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import platform
    HAS_PLATFORM = True
except ImportError:
    HAS_PLATFORM = True


def _cpu_info() -> str:
    if not HAS_PSUTIL:
        return "psutil no instalado."
    cpu_pct = psutil.cpu_percent(interval=1)
    cores = psutil.cpu_count(logical=True)
    freq = psutil.cpu_freq()
    parts = [f"CPU: {cpu_pct}% usado | {cores} nucleos"]
    if freq:
        parts.append(f" | {freq.current:.0f} MHz")
    return "".join(parts)


def _ram_info() -> str:
    if not HAS_PSUTIL:
        return ""
    mem = psutil.virtual_memory()
    return (f"RAM: {mem.used / (1024**3):.1f}GB / {mem.total / (1024**3):.1f}GB "
            f"({mem.percent}% usada)")


def _disk_info() -> str:
    if not HAS_PSUTIL:
        return ""
    lines = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            lines.append(
                f"{part.device} ({part.mountpoint}): "
                f"{usage.used / (1024**3):.1f}GB / {usage.total / (1024**3):.1f}GB "
                f"({usage.percent}%)"
            )
        except Exception:
            pass
    return "\n".join(lines) if lines else "Sin discos detectados."


def _network_info() -> str:
    if not HAS_PSUTIL:
        return ""
    net = psutil.net_io_counters()
    return (f"Red: {net.bytes_sent / (1024**2):.1f}MB enviados | "
            f"{net.bytes_recv / (1024**2):.1f}MB recibidos")


def _battery_info() -> str:
    if not HAS_PSUTIL:
        return ""
    try:
        bat = psutil.sensors_battery()
        if bat is None:
            return ""
        status = "cargando" if bat.power_plugged else "bateria"
        return f"Bateria: {bat.percent}% ({status}) | {bat.secsleft // 60} min restantes" if bat.secsleft > 0 else f"Bateria: {bat.percent}% ({status})"
    except Exception:
        return ""


def _process_info() -> str:
    if not HAS_PSUTIL:
        return ""
    procs = sorted(
        psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
        key=lambda p: p.info.get("cpu_percent", 0) or 0,
        reverse=True
    )[:10]
    lines = ["Top 10 procesos por CPU:"]
    for p in procs:
        info = p.info
        lines.append(
            f"  {info['name'][:25]:<25} | "
            f"CPU: {info.get('cpu_percent', 0) or 0:5.1f}% | "
            f"RAM: {info.get('memory_percent', 0) or 0:5.1f}%"
        )
    return "\n".join(lines)


def _uptime_info() -> str:
    if not HAS_PSUTIL:
        return ""
    boot = datetime.fromtimestamp(psutil.boot_time())
    now = datetime.now()
    delta = now - boot
    hours = delta.total_seconds() // 3600
    minutes = (delta.total_seconds() % 3600) // 60
    return f"Encendido desde: {hours:.0f}h {minutes:.0f}min ({boot.strftime('%H:%M')})"


def system_monitor(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "full")

    if not HAS_PSUTIL:
        return "psutil no esta instalado, senor. Ejecuta: pip install psutil"

    handlers = {
        "cpu": _cpu_info,
        "ram": _ram_info,
        "disk": _disk_info,
        "network": _network_info,
        "battery": _battery_info,
        "processes": _process_info,
        "uptime": _uptime_info,
    }

    if action in handlers:
        return handlers[action]()

    sections = [
        _cpu_info(),
        _ram_info(),
        _disk_info(),
        _network_info(),
    ]
    bat = _battery_info()
    if bat:
        sections.append(bat)
    sections.append(_uptime_info())

    return "\n\n".join(sections)
