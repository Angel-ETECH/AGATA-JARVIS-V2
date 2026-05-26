from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

if platform.system() == "Windows":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows:dpiawareness=0")

from PyQt6.QtCore import (
    QObject, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal, pyqtProperty,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QKeySequence, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 1400, 900
_MIN_W,     _MIN_H     = 900, 600
_OVERLAY_W = 400

_OS = platform.system()


class C:
    # Jarvis (electric blue / deep space)
    BG        = "#00020d"
    BG_DEEP   = "#000108"
    BORDER    = "#0d2444"
    BORDER_B  = "#1a5a99"
    BORDER_A  = "#0f3a66"
    PRI       = "#00d4ff"
    PRI_DIM   = "#0077aa"
    PRI_GHO   = "#001a2e"
    ACC       = "#ff8800"
    ACC2      = "#ffe066"
    GREEN     = "#00ffaa"
    GREEN_D   = "#00aa66"
    RED       = "#ff2244"
    MUTED_C   = "#ff2266"
    TEXT      = "#66eeff"
    TEXT_DIM  = "#1a5577"
    TEXT_MED  = "#33aacc"
    WHITE     = "#ccf4ff"
    DARK      = "#01060f"
    BAR_BG    = "#020f1e"
    STAR      = "#4477bb"
    NEBULA    = "#080835"
    NEBULA2   = "#030a28"
    AURORA    = "#00ccaa"
    COSMIC    = "#4400cc"
    GLASS_BG  = "rgba(0, 8, 22, 220)"
    GLASS_BDR = "rgba(0, 140, 220, 150)"
    # extra space palette
    PLANET    = "#0a1a44"
    RING1     = "#00aaff"
    RING2     = "#0055cc"
    ENERGY    = "#00ffee"


_JARVIS_THEME = {
    "BG": "#00020d", "BG_DEEP": "#000108", "BORDER": "#0d2444", "BORDER_B": "#1a5a99",
    "BORDER_A": "#0f3a66", "PRI": "#00d4ff", "PRI_DIM": "#0077aa", "PRI_GHO": "#001a2e",
    "ACC": "#ff8800", "ACC2": "#ffe066", "GREEN": "#00ffaa", "GREEN_D": "#00aa66",
    "RED": "#ff2244", "MUTED_C": "#ff2266", "TEXT": "#66eeff", "TEXT_DIM": "#1a5577",
    "TEXT_MED": "#33aacc", "WHITE": "#ccf4ff", "DARK": "#01060f", "BAR_BG": "#020f1e",
    "STAR": "#4477bb", "NEBULA": "#080835", "NEBULA2": "#030a28",
    "AURORA": "#00ccaa", "COSMIC": "#4400cc",
    "PLANET": "#0a1a44", "RING1": "#00aaff", "RING2": "#0055cc", "ENERGY": "#00ffee",
}

_AGATA_THEME = {
    "BG": "#080010", "BG_DEEP": "#050008", "BORDER": "#3a0835", "BORDER_B": "#aa1177",
    "BORDER_A": "#770d55", "PRI": "#ff44cc", "PRI_DIM": "#aa0077", "PRI_GHO": "#280020",
    "ACC": "#ff5599", "ACC2": "#ffcc44", "GREEN": "#44ffaa", "GREEN_D": "#22aa66",
    "RED": "#ff1144", "MUTED_C": "#ff2266", "TEXT": "#ffaaee", "TEXT_DIM": "#883366",
    "TEXT_MED": "#cc55aa", "WHITE": "#ffe0f8", "DARK": "#0d0010", "BAR_BG": "#18001e",
    "STAR": "#dd88cc", "NEBULA": "#2a0028", "NEBULA2": "#150015",
    "AURORA": "#ff0099", "COSMIC": "#cc00ff",
    "PLANET": "#2a0030", "RING1": "#ff44dd", "RING2": "#aa0088", "ENERGY": "#ff88ff",
}


def apply_theme(name: str):
    theme = _AGATA_THEME if name == "agata" else _JARVIS_THEME
    for k, v in theme.items():
        setattr(C, k, v)


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(a)
    return c


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0; self.mem = 0.0; self.net = 0.0
        self.gpu  = -1.0; self.tmp = -1.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try: self._update()
            except Exception: pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        net = ((nc.bytes_sent - self._last_net.bytes_sent) + (nc.bytes_recv - self._last_net.bytes_recv)) / dt / (1024*1024) if dt > 0 else 0.0
        self._last_net = nc; self._last_net_t = now
        gpu = self._get_gpu(); tmp = self._get_temp()
        with self._lock: self.cpu = cpu; self.mem = mem; self.net = net; self.gpu = gpu; self.tmp = tmp

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals: return sum(vals) / len(vals)
        except Exception: pass
        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries: return entries[0].current
        except Exception: pass
        if _OS == "Windows":
            try:
                r = subprocess.run(["powershell", "-Command", "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"], capture_output=True, text=True, timeout=3)
                if r.returncode == 0 and r.stdout.strip():
                    return (float(r.stdout.strip().split("\n")[0]) / 10.0) - 273.15
            except Exception: pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock: return {"cpu": self.cpu, "mem": self.mem, "net": self.net, "gpu": self.gpu, "tmp": self.tmp}


_metrics = _SysMetrics()


# ═══════════════════════════════════════════════════════════════════════
# STARFIELD + SPACE EFFECTS
# ═══════════════════════════════════════════════════════════════════════

class _Star:
    __slots__ = ('x', 'y', 'radius', 'alpha', 'twinkle_speed', 'twinkle_phase', 'color', 'layer')
    def __init__(self, w, h):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.layer = random.choice([0, 0, 0, 1, 1, 2])
        self.radius = [random.uniform(0.2, 0.9), random.uniform(0.6, 1.8), random.uniform(1.2, 3.0)][self.layer]
        self.alpha = random.uniform(20, [150, 200, 255][self.layer])
        self.twinkle_speed = random.uniform(0.008, 0.06)
        self.twinkle_phase = random.uniform(0, math.pi * 2)
        self.color = random.choice([C.STAR, C.PRI, C.WHITE, C.COSMIC, C.AURORA, C.ENERGY])


class _NebulaBlob:
    __slots__ = ('x', 'y', 'radius', 'alpha', 'drift_x', 'drift_y', 'color', 'pulse')
    def __init__(self, w, h):
        self.x = random.uniform(-w * 0.1, w * 1.1)
        self.y = random.uniform(-h * 0.1, h * 1.1)
        self.radius = random.uniform(80, 260)
        self.alpha = random.uniform(8, 30)
        self.drift_x = random.uniform(-0.08, 0.08)
        self.drift_y = random.uniform(-0.06, 0.06)
        self.pulse = random.uniform(0, math.pi * 2)
        self.color = random.choice([C.NEBULA, C.NEBULA2, C.COSMIC, C.AURORA, C.PRI_GHO])


class _Planet:
    __slots__ = ('x', 'y', 'radius', 'alpha', 'ring_tilt', 'color', 'ring_color')
    def __init__(self, w, h, idx):
        positions = [
            (w * random.uniform(0.05, 0.20), h * random.uniform(0.05, 0.25)),
            (w * random.uniform(0.80, 0.95), h * random.uniform(0.05, 0.25)),
            (w * random.uniform(0.05, 0.18), h * random.uniform(0.70, 0.92)),
            (w * random.uniform(0.82, 0.95), h * random.uniform(0.70, 0.92)),
        ]
        self.x, self.y = positions[idx % len(positions)]
        self.radius = random.uniform(28, 55)
        self.alpha = random.uniform(55, 100)
        self.ring_tilt = random.uniform(0.18, 0.38)
        pc = random.choice(['blue', 'pink', 'purple', 'teal'])
        if pc == 'blue':
            self.color = QColor(10, 30, 80, 180)
            self.ring_color = QColor(0, 120, 255, 90)
        elif pc == 'pink':
            self.color = QColor(60, 5, 50, 180)
            self.ring_color = QColor(220, 0, 160, 90)
        elif pc == 'purple':
            self.color = QColor(30, 5, 60, 180)
            self.ring_color = QColor(140, 0, 255, 90)
        else:
            self.color = QColor(0, 40, 50, 180)
            self.ring_color = QColor(0, 200, 180, 90)


class _EnergyNode:
    __slots__ = ('theta', 'phi', 'speed_t', 'speed_p', 'radius', 'trail', 'alpha', 'color_frac')
    def __init__(self):
        self.theta = random.uniform(0, math.pi * 2)
        self.phi = random.uniform(0, math.pi)
        self.speed_t = random.uniform(0.004, 0.018) * random.choice([-1, 1])
        self.speed_p = random.uniform(0.002, 0.010) * random.choice([-1, 1])
        self.radius = random.uniform(1.5, 4.0)
        self.trail: list = []
        self.alpha = random.uniform(140, 255)
        self.color_frac = random.random()


class _DataStream:
    __slots__ = ('x', 'y', 'speed', 'chars', 'alpha', 'col')
    _GLYPHS = "01<>[]{}|/\\+=ΩΔΨΦΞΛabcdef0123456789JARVAGATA"
    def __init__(self, W, H):
        self.x = random.choice([
            random.uniform(8, W * 0.12),
            random.uniform(W * 0.88, W - 8)
        ])
        self.y = random.uniform(-H, 0)
        self.speed = random.uniform(0.8, 2.5)
        self.chars = [random.choice(self._GLYPHS) for _ in range(random.randint(6, 20))]
        self.alpha = random.uniform(30, 100)
        self.col = random.choice([C.PRI, C.ENERGY, C.GREEN])


class _ShootingStar:
    __slots__ = ('x', 'y', 'length', 'angle', 'speed', 'alpha', 'width')
    def __init__(self, W, H):
        self.x = random.uniform(-W * 0.2, W * 1.2)
        self.y = random.uniform(-H * 0.1, H * 0.5)
        self.length = random.uniform(60, 200)
        self.angle = random.uniform(-0.4, 0.2)
        self.speed = random.uniform(8, 20)
        self.alpha = 1.0
        self.width = random.uniform(0.8, 2.2)
    def dead(self, W, H):
        return self.alpha <= 0 or self.x > W + 200 or self.y > H + 200 or self.x < -200 or self.y < -200


# ═══════════════════════════════════════════════════════════════════════
# MAIN STARFIELD CANVAS  —  EPIC SPACE REDESIGN
# ═══════════════════════════════════════════════════════════════════════

class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INICIANDO"
        self.persona  = "jarvis"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._energy     = 55.0
        self._tgt_energy = 55.0
        self._last_t     = time.time()

        self._ring_angles = [0.0, 72.0, 144.0, 216.0, 288.0]
        self._ring_speeds = [0.45, -0.30, 0.70, -0.55, 0.25]
        self._ring_tilts  = [0.0, 0.35, 0.60, -0.25, 0.80]

        self._scan   = 0.0
        self._scan2  = 180.0
        self._scan3  = 90.0

        self._pulses: list[float] = [0.0, 60.0, 120.0]
        self._blink      = True
        self._blink_tick = 0
        self._burst: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._stars: list[_Star] = []
        self._blobs: list[_NebulaBlob] = []
        self._planets: list[_Planet] = []
        self._nodes: list[_EnergyNode] = []
        self._streams: list[_DataStream] = []
        self._shooting: list[_ShootingStar] = []
        self._shoot_cd = 0
        self._stream_cd = 0
        self._init_space(1200, 900)

        self._hex_phase = 0.0
        self._name_glow = 0.0
        self._name_glow_dir = 1.0

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _init_space(self, w, h):
        self._stars   = [_Star(w, h) for _ in range(400)]
        self._blobs   = [_NebulaBlob(w, h) for _ in range(14)]
        self._planets = [_Planet(w, h, i) for i in range(4)]
        self._nodes   = [_EnergyNode() for _ in range(28)]
        self._streams = []
        self._shooting = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._init_space(event.size().width(), event.size().height())

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        W, H = self.width(), self.height()

        if now - self._last_t > (0.10 if self.speaking else 0.45):
            if self.speaking:
                self._tgt_scale  = random.uniform(1.04, 1.12)
                self._tgt_energy = random.uniform(180, 255)
            elif self.muted:
                self._tgt_scale  = random.uniform(0.998, 1.002)
                self._tgt_energy = random.uniform(12, 24)
            else:
                self._tgt_scale  = random.uniform(1.002, 1.010)
                self._tgt_energy = random.uniform(60, 100)
            self._last_t = now

        sp = 0.40 if self.speaking else 0.12
        self._scale  += (self._tgt_scale  - self._scale)  * sp
        self._energy += (self._tgt_energy - self._energy) * sp

        spk_mult = 2.8 if self.speaking else 1.0
        for i in range(len(self._ring_angles)):
            self._ring_angles[i] = (self._ring_angles[i] + self._ring_speeds[i] * spk_mult) % 360

        sc_spd = 2.8 if self.speaking else 1.1
        self._scan  = (self._scan  + sc_spd) % 360
        self._scan2 = (self._scan2 - sc_spd * 0.7) % 360
        self._scan3 = (self._scan3 + sc_spd * 1.4) % 360

        fw = min(W, H)
        lim = fw * 0.80
        ps  = 3.5 if self.speaking else 1.6
        self._pulses = [r + ps for r in self._pulses if r + ps < lim]
        if len(self._pulses) < 4 and random.random() < (0.10 if self.speaking else 0.030):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.32:
            cx2, cy2 = W / 2, H / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.26
            spd = random.uniform(1.2, 3.0)
            self._burst.append([
                cx2 + math.cos(ang) * r_s, cy2 + math.sin(ang) * r_s,
                math.cos(ang) * spd, math.sin(ang) * spd - 0.3, 1.0, random.random(),
            ])
        self._burst = [
            [b[0]+b[2], b[1]+b[3], b[2]*0.96, b[3]*0.96, b[4]-0.025, b[5]]
            for b in self._burst if b[4] > 0
        ]

        spk_n = 3.0 if self.speaking else 1.0
        for nd in self._nodes:
            nd.theta = (nd.theta + nd.speed_t * spk_n) % (math.pi * 2)
            nd.phi   = (nd.phi   + nd.speed_p * spk_n) % math.pi
            nd.trail.append((nd.theta, nd.phi))
            if len(nd.trail) > 12:
                nd.trail.pop(0)

        for blob in self._blobs:
            blob.x += blob.drift_x
            blob.y += blob.drift_y
            blob.pulse = (blob.pulse + 0.008) % (math.pi * 2)
            if blob.x < -300: blob.x = W + 300
            elif blob.x > W + 300: blob.x = -300
            if blob.y < -300: blob.y = H + 300
            elif blob.y > H + 300: blob.y = -300

        self._shoot_cd -= 1
        if self._shoot_cd <= 0 and random.random() < (0.030 if self.speaking else 0.010):
            self._shooting.append(_ShootingStar(W, H))
            self._shoot_cd = random.randint(30, 140)
        for s in self._shooting:
            s.x += s.speed * math.cos(s.angle)
            s.y += s.speed * math.sin(s.angle)
            s.alpha -= 0.018
        self._shooting = [s for s in self._shooting if not s.dead(W, H)]

        self._stream_cd -= 1
        if self._stream_cd <= 0 and len(self._streams) < 12:
            self._streams.append(_DataStream(W, H))
            self._stream_cd = random.randint(20, 80)
        for st in self._streams:
            st.y += st.speed
        self._streams = [st for st in self._streams if st.y < H + 200]

        self._hex_phase = (self._hex_phase + 0.012 * (2.0 if self.speaking else 1.0)) % (math.pi * 2)

        self._name_glow += 0.04 * self._name_glow_dir
        if self._name_glow > 1.0: self._name_glow_dir = -1.0
        elif self._name_glow < 0.0: self._name_glow_dir = 1.0

        self._blink_tick += 1
        if self._blink_tick >= 35:
            self._blink = not self._blink; self._blink_tick = 0

        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # 1. Deep space background
        bg_grad = QRadialGradient(QPointF(cx, cy), fw * 0.9)
        if self.persona == "agata":
            bg_grad.setColorAt(0.0, QColor(18,  0, 22, 255))
            bg_grad.setColorAt(0.5, QColor(10,  0, 16, 255))
            bg_grad.setColorAt(1.0, QColor( 4,  0,  8, 255))
        else:
            bg_grad.setColorAt(0.0, QColor( 0,  4, 22, 255))
            bg_grad.setColorAt(0.5, QColor( 0,  2, 14, 255))
            bg_grad.setColorAt(1.0, QColor( 0,  1,  8, 255))
        p.fillRect(self.rect(), QBrush(bg_grad))

        # 2. Volumetric nebulae
        for blob in self._blobs:
            pulse_a = blob.alpha * (0.75 + 0.25 * math.sin(blob.pulse))
            g = QRadialGradient(QPointF(blob.x, blob.y), blob.radius)
            col = QColor(blob.color); col.setAlpha(int(pulse_a))
            g.setColorAt(0.0, col)
            mid = QColor(blob.color); mid.setAlpha(int(pulse_a * 0.4))
            g.setColorAt(0.5, mid)
            g.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(blob.x - blob.radius, blob.y - blob.radius, blob.radius * 2, blob.radius * 2))

        # 3. Background planets with rings
        for planet in self._planets:
            pg = QRadialGradient(QPointF(planet.x - planet.radius * 0.28,
                                         planet.y - planet.radius * 0.28), planet.radius)
            lc = QColor(planet.color); lc.setAlpha(int(planet.alpha * 1.4))
            dc = QColor(planet.color); dc.setAlpha(int(planet.alpha * 0.6))
            pg.setColorAt(0.0, lc); pg.setColorAt(0.7, planet.color); pg.setColorAt(1.0, dc)
            p.setBrush(QBrush(pg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(planet.x - planet.radius, planet.y - planet.radius,
                                 planet.radius * 2, planet.radius * 2))
            rw = planet.radius * 2.2; rh = planet.radius * planet.ring_tilt
            p.setPen(QPen(planet.ring_color, planet.radius * 0.22)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(planet.x - rw / 2, planet.y - rh / 2, rw, rh))
            atm = QRadialGradient(QPointF(planet.x, planet.y), planet.radius * 1.35)
            ac = QColor(planet.ring_color); ac.setAlpha(30)
            atm.setColorAt(0.6, QColor(0, 0, 0, 0)); atm.setColorAt(1.0, ac)
            p.setBrush(QBrush(atm)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(planet.x - planet.radius * 1.35, planet.y - planet.radius * 1.35,
                                 planet.radius * 2.7, planet.radius * 2.7))

        # 4. Multi-layer stars
        for star in self._stars:
            flicker = 0.50 + 0.50 * math.sin(self._tick * star.twinkle_speed + star.twinkle_phase)
            a = max(8, min(255, int(star.alpha * flicker)))
            if star.layer == 2 and a > 160:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(star.color, a // 3)))
                p.drawEllipse(QPointF(star.x, star.y), star.radius * 2.5, star.radius * 2.5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(star.color, a)))
            p.drawEllipse(QPointF(star.x, star.y), star.radius, star.radius)

        # 5. Shooting stars
        for s in self._shooting:
            a = int(s.alpha * 220)
            if a <= 0: continue
            ex, ey = s.x, s.y
            sx2 = ex - math.cos(s.angle) * s.length
            sy2 = ey - math.sin(s.angle) * s.length
            grad = QLinearGradient(QPointF(ex, ey), QPointF(sx2, sy2))
            grad.setColorAt(0.0, QColor(220, 240, 255, a))
            grad.setColorAt(0.3, qcol(C.PRI, a // 2))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(QPen(QBrush(grad), s.width))
            p.drawLine(QPointF(ex, ey), QPointF(sx2, sy2))

        # 6. Data streams on edges
        font_ds = QFont("Courier New", 7)
        p.setFont(font_ds)
        for st in self._streams:
            for ci, ch in enumerate(st.chars):
                fade = max(0, 1.0 - ci / len(st.chars))
                a = int(st.alpha * fade * (0.5 + 0.5 * math.sin(self._tick * 0.05 + ci)))
                p.setPen(QPen(qcol(st.col, a), 1))
                p.drawText(QPointF(st.x, st.y - ci * 11), ch)

        # 7. Central glow cloud
        r_orb = fw * 0.28
        for i in range(10, 0, -1):
            r = r_orb * (2.2 - i * 0.15)
            frc = i / 10
            a = max(0, min(255, int(self._energy * 0.22 * frc)))
            if self.persona == "agata":
                nc = QColor(int(50 * frc), 0, int(40 * frc), a)
            else:
                nc = QColor(0, int(12 * frc), int(50 * frc), a)
            p.setBrush(QBrush(nc)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # 8. Hex grid on orb
        self._draw_hex_grid(p, cx, cy, r_orb * 0.92)

        # 9. Holographic orbital rings (5 rings)
        ring_cfgs = [
            (0.52, 4.2, 100, 60),
            (0.44, 2.8,  75, 50),
            (0.36, 2.0,  55, 38),
            (0.60, 1.4,  40, 80),
            (0.28, 1.2,  35, 28),
        ]
        ring_cols = [C.PRI, C.ENERGY, C.PRI_DIM, C.COSMIC, C.RING1]
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(ring_cfgs):
            ring_r = fw * r_frac
            base   = self._ring_angles[idx]
            tilt   = self._ring_tilts[idx]
            a_val  = max(0, min(255, int(self._energy * (1.0 - idx * 0.12))))
            col_h  = C.MUTED_C if self.muted else ring_cols[idx]
            col    = qcol(col_h, a_val)
            p.save()
            p.translate(cx, cy)
            p.scale(1.0, 0.30 + 0.25 * abs(math.sin(tilt + self._tick * 0.003)))
            p.translate(-cx, -cy)
            p.setPen(QPen(col, w_r, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            angle = base
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap
            p.restore()

        # 10. Energy nodes on orb surface
        self._draw_energy_nodes(p, cx, cy, r_orb)

        # 11. Radial pulse rings
        for pr in self._pulses:
            frac = pr / (fw * 0.80)
            a = max(0, int(200 * (1.0 - frac)))
            w_pr = max(0.5, 3.0 * (1.0 - frac))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, w_pr)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # 12. Scanners
        sr = fw * 0.56
        sa = min(255, int(self._energy * 1.8))
        ex_arc = 90 if self.speaking else 52
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.setPen(QPen(qcol(C.MUTED_C if self.muted else C.PRI, sa), 3.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(srect, int(self._scan * 16), int(ex_arc * 16))
        s2c = QColor(C.COSMIC); s2c.setAlpha(sa // 2)
        p.setPen(QPen(s2c, 2.0)); p.drawArc(srect, int(self._scan2 * 16), int(ex_arc * 16))
        s3c = QColor(C.ENERGY); s3c.setAlpha(sa // 3)
        p.setPen(QPen(s3c, 1.5)); p.drawArc(srect, int(self._scan3 * 16), int(ex_arc * 16))

        # 13. Tick dial
        t_out, t_in = fw * 0.535, fw * 0.510
        for deg in range(0, 360, 3):
            rad = math.radians(deg)
            major = (deg % 30 == 0)
            inn = t_in if major else t_in + (t_out - t_in) * 0.55
            p.setPen(QPen(qcol(C.PRI if major else C.STAR, 230 if major else 55), 1.5 if major else 0.7))
            p.drawLine(QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                       QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)))

        # 14. Crosshair
        ch_r, gap_h = fw * 0.56, fw * 0.20
        p.setPen(QPen(qcol(C.PRI, int(self._energy * 0.55)), 1.2))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

        # 15. Corner brackets
        bl = 38
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        for bx, by, dx, dy in [(hl, ht, 1, 1), (hr, ht, -1, 1), (hl, hb, 1, -1), (hr, hb, -1, -1)]:
            p.setPen(QPen(qcol(C.PRI, 240), 2.8))
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))
            inner = int(bl * 0.38)
            p.setPen(QPen(qcol(C.ENERGY, 110), 1.2))
            p.drawLine(QPointF(bx + dx * (bl - inner), by + dy * (bl - inner)),
                       QPointF(bx + dx * bl, by + dy * (bl - inner)))
            p.drawLine(QPointF(bx + dx * (bl - inner), by + dy * (bl - inner)),
                       QPointF(bx + dx * (bl - inner), by + dy * bl))

        # 16. Orb core
        if self._face_px:
            fsz = int(fw * 0.58 * self._scale)
            scaled = self._face_px.scaled(fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
        else:
            self._draw_energy_core(p, cx, cy, fw)

        # 17. Burst particles
        for pt in self._burst:
            a = max(0, min(255, int(pt[4] * 255)))
            col_b = C.ENERGY if pt[5] > 0.5 else C.PRI
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(col_b, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 3.0, 3.0)

        # 18. AI name with glow
        name = "A.G.A.T.A" if self.persona == "agata" else "J.A.R.V.I.S"
        glow_a = int(80 + 120 * self._name_glow)
        for gi in range(4, 0, -1):
            gc = qcol(C.PRI, glow_a // (gi + 1))
            p.setFont(QFont("Courier New", 16 + gi, QFont.Weight.Bold))
            p.setPen(QPen(gc, 1))
            p.drawText(QRectF(cx - 100 - gi, cy - 16 - gi, 200 + gi * 2, 32 + gi * 2),
                       Qt.AlignmentFlag.AlignCenter, name)
        p.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE, min(255, int(self._energy * 2.2))), 1))
        p.drawText(QRectF(cx - 100, cy - 16, 200, 32), Qt.AlignmentFlag.AlignCenter, name)

        # 19. Status
        sy = cy + fw * 0.40
        if self.muted:            txt, col_s = "[ X ]  SILENCIADO",  qcol(C.MUTED_C)
        elif self.speaking:       txt, col_s = "[ O ]  HABLANDO",    qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "<>" if self._blink else "><"
            txt, col_s = f"{sym}  PENSANDO",    qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = ">>" if self._blink else "<<"
            txt, col_s = f"{sym}  PROCESANDO",  qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "[*]" if self._blink else "[ ]"
            txt, col_s = f"{sym}  ESCUCHANDO",  qcol(C.GREEN)
        else:
            sym = "[-]" if self._blink else "[=]"
            txt, col_s = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col_s, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # 20. Waveform
        wy = sy + 34
        N, bw = 54, 6
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C, 120)
            elif self.speaking:
                hgt = random.randint(2, 30)
                frac = hgt / 30
                cl = qcol(C.ENERGY if frac > 0.65 else C.PRI, 160 + int(95 * frac))
            else:
                hgt = int(3 + 4 * math.sin(self._tick * 0.07 + i * 0.55))
                cl = qcol(C.BORDER_B, 140)
            p.fillRect(QRectF(wx0 + i * bw, wy + 22 - hgt, bw - 2, hgt), cl)

    def _draw_hex_grid(self, p: QPainter, cx: float, cy: float, orb_r: float):
        hex_size = orb_r * 0.14
        cols = int(orb_r / hex_size) * 2 + 2
        for row in range(-cols, cols + 1):
            for col in range(-cols, cols + 1):
                hx = col * hex_size * 1.732
                hy = row * hex_size * 1.5 + (col % 2) * hex_size * 0.75
                dist = math.sqrt(hx * hx + hy * hy)
                if dist > orb_r * 0.95: continue
                depth_frac = 1.0 - dist / orb_r
                pulse = 0.5 + 0.5 * math.sin(self._hex_phase + dist * 0.04)
                a = int(depth_frac * pulse * 45)
                if a < 4: continue
                p.setPen(QPen(qcol(C.PRI, a), 0.6))
                p.setBrush(Qt.BrushStyle.NoBrush)
                pts = [QPointF(cx + hx + hex_size * 0.45 * math.cos(math.radians(60 * k - 30)),
                               cy + hy + hex_size * 0.45 * math.sin(math.radians(60 * k - 30)))
                       for k in range(6)]
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]: path.lineTo(pt)
                path.closeSubpath()
                p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)

    def _draw_energy_nodes(self, p: QPainter, cx: float, cy: float, orb_r: float):
        for nd in self._nodes:
            sin_phi = math.sin(nd.phi)
            nx = cx + orb_r * sin_phi * math.cos(nd.theta)
            ny = cy + orb_r * sin_phi * math.sin(nd.theta) * 0.40
            depth = math.cos(nd.phi)
            if depth < -0.1: continue
            frac = (depth + 1) / 2
            a_nd = int(nd.alpha * frac)
            col_nd = C.ENERGY if nd.color_frac > 0.5 else C.PRI
            for ti, (tt, tp) in enumerate(nd.trail[:-1]):
                trail_frac = ti / max(1, len(nd.trail))
                ta = int(a_nd * trail_frac * 0.5)
                if ta < 5: continue
                tx = cx + orb_r * math.sin(tp) * math.cos(tt)
                ty = cy + orb_r * math.sin(tp) * math.sin(tt) * 0.40
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(col_nd, ta)))
                p.drawEllipse(QPointF(tx, ty), nd.radius * trail_frac * 0.6, nd.radius * trail_frac * 0.6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(col_nd, min(255, a_nd // 3))))
            p.drawEllipse(QPointF(nx, ny), nd.radius * 2.5, nd.radius * 2.5)
            p.setBrush(QBrush(qcol(col_nd, a_nd)))
            p.drawEllipse(QPointF(nx, ny), nd.radius, nd.radius)

    def _draw_energy_core(self, p: QPainter, cx: float, cy: float, fw: float):
        r_core = int(fw * 0.24 * self._scale)
        for i in range(12, 0, -1):
            r2 = int(r_core * i / 12); frc = i / 12
            a = max(0, min(255, int(self._energy * 1.2 * frc)))
            if self.persona == "agata":
                p.setBrush(QBrush(QColor(int(200 * frc), 0, int(180 * frc), a)))
            else:
                p.setBrush(QBrush(QColor(0, int(150 * frc), int(255 * frc), a)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
        ig = QRadialGradient(QPointF(cx, cy), r_core * 0.5)
        if self.persona == "agata":
            ig.setColorAt(0.0, QColor(255, 180, 255, min(255, int(self._energy * 2))))
            ig.setColorAt(0.4, QColor(220,  50, 200, int(self._energy)))
        else:
            ig.setColorAt(0.0, QColor(180, 255, 255, min(255, int(self._energy * 2))))
            ig.setColorAt(0.4, QColor(  0, 200, 255, int(self._energy)))
        ig.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(ig)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - r_core * 0.5, cy - r_core * 0.5, r_core, r_core))







# ═══════════════════════════════════════════════════════════════════════
# GLASS OVERLAY PANEL (slides from right)
# ═══════════════════════════════════════════════════════════════════════











_FILE_ICONS = {
    "image": ("[IMG]", "#4dc9f6"), "video": ("[VID]", "#ff7722"),
    "audio": ("[AUD]", "#aa44ff"), "pdf": ("[PDF]", "#ff4444"),
    "word": ("[DOC]", "#4488ff"), "excel": ("[XLS]", "#44bb44"),
    "code": ("[COD]", "#f0c040"), "archive": ("[ARC]", "#ff8844"),
    "pptx": ("[PPT]", "#ff6622"), "text": ("[TXT]", "#aaaaaa"),
    "data": ("[DAT]", "#88ddff"), "unknown": ("[ARCH]", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"], "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"], "audio"),
    **dict.fromkeys(["pdf"], "pdf"),
    **dict.fromkeys(["doc","docx"], "word"),
    **dict.fromkeys(["xls","xlsx","ods"], "excel"),
    **dict.fromkeys(["ppt","pptx"], "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp","cs","go","rs","rb","php","swift","kt","sh","sql","lua"], "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"], "archive"),
    **dict.fromkeys(["txt","md","rst","log"], "text"),
    **dict.fromkeys(["csv","tsv","json","xml"], "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if size < 1024: return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else: return f"{size/1024**3:.1f} GB"


class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 8))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(0, 10, 25, 0.25);
                color: {C.TEXT};
                border: 1px solid rgba(0, 210, 255, 0.15);
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: rgba(0, 8, 18, 80);
                width: 4px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.PRI_DIM}; min-height: 16px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self._queue: list[str] = []
        self._typing = False; self._text = ""; self._pos = 0; self._tag = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(self._fmt(text))
        if not self._typing: self._next()

    def _fmt(self, text: str) -> str:
        tl = text.lower()
        if tl.startswith("you:") or tl.startswith("tu:"):
            return f"[USR]> {text.split(':', 1)[1].strip()}"
        if tl.startswith("jarvis:") or tl.startswith("agata:"):
            rest = text.split(":", 1)[1].strip()
            pre = "[SYS_A.G.A.T.A]>" if tl.startswith("agata:") else "[SYS_J.A.R.V.I.S]>"
            return f"{pre} {rest}"
        if tl.startswith("file:"):
            return f"[FILE]> {text.split(':', 1)[1].strip()}"
        if tl.startswith("sys:") or tl.startswith("err:"):
            tag = "[ERR]>" if tl.startswith("err:") else "[SYS]>"
            return f"{tag} {text.split(':', 1)[1].strip()}"
        return text

    def _next(self):
        if not self._queue:
            self._typing = False; return
        self._typing = True
        self._text = self._queue.pop(0); self._pos = 0
        if self._text.startswith("[USR]"):                  self._tag = "you"
        elif self._text.startswith("[SYS_J.A.R.V.I.S]") or self._text.startswith("[SYS_A.G.A.T.A]"): self._tag = "ai"
        elif self._text.startswith("[FILE]"):               self._tag = "file"
        elif self._text.startswith("[ERR]"):                self._tag = "err"
        else:                                               self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch = self._text[self._pos]
            cur = self.textCursor(); fmt = cur.charFormat()
            col = {"you": qcol(C.WHITE), "ai": qcol(C.PRI), "err": qcol(C.RED), "file": qcol(C.GREEN), "sys": qcol(C.ACC2)}.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End); cur.insertText(ch, fmt)
            self.setTextCursor(cur); self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor(); cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n"); self.setTextCursor(cur); self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)


class _DropCanvas(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._z = parent

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z = self._z; W, H = self.width(), self.height(); pad = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)
        if z._drag_over: bg_col = QColor(0, 30, 60, 100)
        elif z._hovering: bg_col = QColor(0, 20, 40, 80)
        else: bg_col = QColor(0, 10, 25, 50)
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 8, 8)
        if z._current_file: border_col = qcol(C.GREEN, 200)
        elif z._drag_over: border_col = qcol(C.PRI, 200)
        elif z._hovering: border_col = qcol(C.PRI_DIM, 160)
        else: border_col = qcol(C.PRI_DIM, 80)
        pen = QPen(border_col, 1.8, Qt.PenStyle.DashLine); pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 8, 8)
        if z._current_file: self._paint_file(p, W, H)
        elif z._drag_over: self._paint_drag_over(p, W, H)
        else: self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 16), QPointF(cx, cy + 8))
        p.drawLine(QPointF(cx - 10, cy - 6), QPointF(cx, cy - 16))
        p.drawLine(QPointF(cx + 10, cy - 6), QPointF(cx, cy - 16))
        p.drawLine(QPointF(cx - 16, cy + 8), QPointF(cx + 16, cy + 8))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Suelta archivo  |  Click para buscar")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 16, W, 24), Qt.AlignmentFlag.AlignCenter, "[ LISTO ]")
        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.drawText(QRectF(0, cy + 12, W, 18), Qt.AlignmentFlag.AlignCenter, "Suelta para cargar")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str = path.suffix.upper().lstrip(".") or "FILE"
        block_x, block_w = 12, 55
        p.setFont(QFont("Courier New", 20, QFont.Weight.Bold))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)
        tx = block_x + block_w + 8; tw = W - tx - 40
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 30 else path.name[:27] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
        p.setFont(QFont("Courier New", 7)); p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{ext_str}  |  {size_str}")
        p.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 36, 0, 30, H), Qt.AlignmentFlag.AlignCenter, "[X]")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 36: z.clear_file()
        else: z.mousePressEvent(e)


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(105)
        self._current_file: str | None = None
        self._hovering = False; self._drag_over = False; self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate); self._anim_tmr.start(40)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        self._canvas = _DropCanvas(self); layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20; self._canvas.update()

    def dragEnterEvent(self, e): e.acceptProposedAction(); self._drag_over = True; self._canvas.update()
    def dragLeaveEvent(self, e): self._drag_over = False; self._canvas.update()
    def dropEvent(self, e):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file(): self._set_file(path)
        self._canvas.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._browse()
    def enterEvent(self, e): self._hovering = True; self._canvas.update()
    def leaveEvent(self, e): self._hovering = False; self._canvas.update()
    def current_file(self) -> str | None: return self._current_file
    def clear_file(self): self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo para JARVIS", str(Path.home()),
            "All Files (*.*);;Imagenes (*.jpg *.jpeg *.png *.gif *.webp);;Documentos (*.pdf *.docx *.txt);;Codigo (*.py *.js *.ts *.html *.css);;Audio (*.mp3 *.wav);;Video (*.mp4 *.mov)")
        if path: self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path; self._canvas.update()
        self.file_selected.emit(path)


class GlassOverlay(QWidget):
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._current_file: str | None = None
        self._muted = False
        self._visible = True
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: transparent;")
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 6, 12, 8)
        main.setSpacing(6)

        # ── TOP BAR ──
        top = QHBoxLayout()
        self._panel_title = QLabel("[ SYS_J.A.R.V.I.S ]  ──  TERMINAL v3.0.1")
        self._panel_title.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        self._panel_title.setStyleSheet(f"""
            color: {C.PRI}; background: rgba(0,10,25,0.35);
            border: 1px solid rgba(0,210,255,0.25); padding: 3px 10px;
        """)
        top.addWidget(self._panel_title)
        top.addStretch()
        sep_lbl = QLabel("// INTERFAZ HOLOGRÁFICA")
        sep_lbl.setFont(QFont("Courier New", 7))
        sep_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        top.addWidget(sep_lbl)
        top.addSpacing(10)
        close_btn = QPushButton("[X]")
        close_btn.setFixedSize(32, 26)
        close_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: rgba(0,10,25,0.35); color: {C.TEXT_DIM}; border: 1px solid rgba(0,210,255,0.2); }}
            QPushButton:hover {{ color: {C.RED}; border: 1px solid {C.RED}; background: rgba(40,0,0,0.3); }}
        """)
        close_btn.clicked.connect(self.hide_panel)
        top.addWidget(close_btn)
        main.addLayout(top)

        # ── MID ROW: terminal log (left) + file sys (right) ──
        mid = QHBoxLayout()
        mid.setSpacing(8)

        # Terminal / Log panel
        log_panel = QWidget()
        log_panel.setStyleSheet(f"""
            background: rgba(0,10,25,0.3);
            border: 1px solid rgba(0,210,255,0.18);
        """)
        log_lay = QVBoxLayout(log_panel)
        log_lay.setContentsMargins(6, 6, 6, 6)
        log_lay.setSpacing(4)
        log_hdr = QLabel("> REGISTRO DE ACTIVIDAD  //  TERMINAL")
        log_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        log_hdr.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        log_lay.addWidget(log_hdr)
        self._log = LogWidget()
        log_lay.addWidget(self._log, stretch=1)
        mid.addWidget(log_panel, stretch=2)

        # File upload panel
        file_panel = QWidget()
        file_panel.setStyleSheet(f"""
            background: rgba(0,10,25,0.3);
            border: 1px solid rgba(0,210,255,0.18);
        """)
        file_lay = QVBoxLayout(file_panel)
        file_lay.setContentsMargins(6, 6, 6, 6)
        file_lay.setSpacing(4)
        file_hdr = QLabel("> SUBIR ARCHIVO  //  FILE SYSTEM")
        file_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        file_hdr.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        file_lay.addWidget(file_hdr)
        self._drop_zone = FileDropZone()
        file_lay.addWidget(self._drop_zone)
        self._file_hint = QLabel("Sin archivo cargado.")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        file_lay.addWidget(self._file_hint)
        file_lay.addStretch()
        mid.addWidget(file_panel, stretch=1)
        main.addLayout(mid, stretch=1)

        # ── BOTTOM INPUT BAR ──
        input_bar = QWidget()
        input_bar.setStyleSheet(f"""
            background: rgba(0,10,25,0.35);
            border: 1px solid rgba(0,210,255,0.18);
        """)
        inp_lay = QHBoxLayout(input_bar)
        inp_lay.setContentsMargins(10, 4, 10, 4)
        inp_lay.setSpacing(6)
        prompt = QLabel(">")
        prompt.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        prompt.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        inp_lay.addWidget(prompt)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Escribe un comando o pregunta...")
        self._input.setFont(QFont("Courier New", 11))
        self._input.setFixedHeight(32)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; color: {C.WHITE};
                border: none; border-bottom: 1px solid rgba(0,210,255,0.3);
                padding: 2px 6px;
            }}
            QLineEdit:focus {{ border-bottom: 1px solid {C.PRI}; }}
        """)
        inp_lay.addWidget(self._input, stretch=1)
        send_btn = QPushButton(">")
        send_btn.setFixedSize(32, 32)
        send_btn.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,40,80,0.3); color: {C.PRI};
                border: 1px solid {C.PRI_DIM};
            }}
            QPushButton:hover {{
                background: rgba(0,60,120,0.4); border: 1px solid {C.PRI};
            }}
        """)
        inp_lay.addWidget(send_btn)
        self._mute_btn = QPushButton("[ O ]  MIC · ACTIVO")
        self._mute_btn.setFixedHeight(32)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        inp_lay.addWidget(self._mute_btn)
        main.addWidget(input_bar)

        self._style_mute_btn()

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("[ X ]  MIC · SILENCIADO")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{ background: rgba(40,0,6,0.35); color: {C.MUTED_C}; border: 1px solid {C.MUTED_C}; }}
                QPushButton:hover {{ background: rgba(60,0,8,0.45); }}
            """)
        else:
            self._mute_btn.setText("[ O ]  MIC · ACTIVO")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{ background: rgba(0,40,10,0.35); color: {C.GREEN}; border: 1px solid {C.GREEN}; }}
                QPushButton:hover {{ background: rgba(0,60,14,0.45); }}
            """)

    def show_panel(self, animated=True):
        if self._visible: return
        self._visible = True
        p = self.parent()
        if p:
            self.setGeometry(p.rect())
        self.show()
        self.raise_()

    def hide_panel(self, animated=True):
        if not self._visible: return
        self._visible = False
        self.hide()
        self.close_requested.emit()

    def toggle(self):
        if self._visible: self.hide_panel()
        else: self.show_panel()

    def paintEvent(self, event):
        pass

    @property
    def current_file(self): return self._drop_zone.current_file()
    @property
    def muted(self): return self._muted
    @muted.setter
    def muted(self, v: bool): self._muted = v; self._style_mute_btn()

    def set_persona(self, name: str):
        n = "SYS_A.G.A.T.A" if name == "agata" else "SYS_J.A.R.V.I.S"
        self._panel_title.setText(f"[ {n} ]  ──  TERMINAL v3.0.1")





# ═══════════════════════════════════════════════════════════════════════
# SETUP OVERLAY
# ═══════════════════════════════════════════════════════════════════════

class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{ background: rgba(4,12,24,248); border: 1px solid {C.BORDER_B}; border-radius: 0px; }}
        """)
        detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = detected
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 26, 34, 26); layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;"); return w

        layout.addWidget(_lbl("[ INICIALIZACION REQUERIDA ]", 13, True))
        layout.addWidget(_lbl("Configura J.A.R.V.I.S. antes del primer inicio.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)
        layout.addWidget(_lbl("CLAVE API GEMINI", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password); self._key_input.setPlaceholderText("AIza...")
        self._key_input.setFont(QFont("Courier New", 10)); self._key_input.setFixedHeight(34)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{ background: rgba(3,10,20,220); color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 0px; padding: 4px 10px; }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input); layout.addSpacing(12)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine); sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)
        layout.addWidget(_lbl("SISTEMA OPERATIVO", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Detectado: {det_name}", 8, color=C.ACC2, align=Qt.AlignmentFlag.AlignLeft))
        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows", "[W] Windows"), ("mac", "[M] macOS"), ("linux", "[L] Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold)); btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn); self._os_btns[key] = btn
        layout.addLayout(os_row); self._sel(detected); layout.addSpacing(12)
        init_btn = QPushButton("[>] INICIAR SISTEMAS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold)); init_btn.setFixedHeight(40)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 0px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        init_btn.clicked.connect(self._submit); layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows": (C.PRI, "#001a22"), "mac": (C.ACC2, "#1a1400"), "linux": (C.GREEN, "#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"QPushButton {{ background: {fg}; color: {bg}; border: none; border-radius: 0px; font-weight: bold; }}")
            else:
                btn.setStyleSheet(f"QPushButton {{ background: rgba(3,10,20,200); color: {C.TEXT_DIM}; border: 1px solid {C.BORDER}; border-radius: 0px; }} QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}")

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(self._key_input.styleSheet() + f" QLineEdit {{ border: 1px solid {C.RED}; }}"); return
        self.done.emit(key, self._sel_os)


# ═══════════════════════════════════════════════════════════════════════
# CRT SCANLINE OVERLAY
# ═══════════════════════════════════════════════════════════════════════

class ScanlinesOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        W, H = self.width(), self.height()
        for y in range(0, H, 3):
            p.fillRect(0, y, W, 1, QColor(0, 0, 0, 6))
        # subtle vignette
        vg = QRadialGradient(QPointF(W / 2, H / 2), max(W, H) * 0.7)
        vg.setColorAt(0.0, QColor(0, 0, 0, 0))
        vg.setColorAt(1.0, QColor(0, 0, 0, 100))
        p.setBrush(QBrush(vg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(self.rect())


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _panel_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S  |  MARK XXXIX")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - _DEFAULT_W) // 2, (screen.height() - _DEFAULT_H) // 2)

        self.on_text_command = None
        self._muted = False
        self._current_file: str | None = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # starfield canvas fills everything
        self.hud = HudCanvas(face_path)
        root.addWidget(self.hud)

        # CRT scanline overlay (above HUD, invisible to mouse)
        self._scanlines = ScanlinesOverlay(self.centralWidget())
        self._scanlines.setGeometry(self.centralWidget().rect())

        # terminal overlay — floating panels over HUD (always visible)
        self._overlay_panel = GlassOverlay(central)
        self._overlay_panel.setGeometry(self.centralWidget().rect())
        self._overlay_panel._drop_zone.file_selected.connect(self._on_file_selected)
        self._overlay_panel._mute_btn.clicked.connect(self._toggle_mute)
        self._overlay_panel._input.returnPressed.connect(self._send)
        self._overlay_panel._input.setFocus()

        # signals
        self._log_sig.connect(self._overlay_panel._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._panel_sig.connect(self._handle_panel)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock); self._clock_tmr.start(1000)
        self._tick_clock()

        self._ready = self._check_config()
        if not self._ready: self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self); sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self); sc_full.activated.connect(self._toggle_fullscreen)
        sc_toggle = QShortcut(QKeySequence("F2"), self); sc_toggle.activated.connect(self._toggle_panel)


    def _toggle_fullscreen(self):
        if self.isFullScreen(): self.showNormal()
        else: self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        cr = cw.rect()
        if self._overlay_panel.isVisible():
            self._overlay_panel.setGeometry(cr)

        if hasattr(self, '_scanlines'):
            self._scanlines.setGeometry(cr)
        if hasattr(self, '_overlay') and self._overlay and self._overlay.isVisible():
            ow, oh = 480, 420
            self._overlay.setGeometry((cr.width() - ow) // 2, (cr.height() - oh) // 2, ow, oh)

    def _tick_clock(self):
        t = time.strftime("%H:%M:%S"); d = time.strftime("%a %d %b %Y")
        name = "AGATA" if self.hud.persona == "agata" else "J.A.R.V.I.S"
        self.setWindowTitle(f"{name}  |  {t}")

    def _on_file_selected(self, path: str):
        self._current_file = path
        p = Path(path)
        cat = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._overlay_panel._file_hint.setText(f"{icon}  {p.name}  |  {size}  |  Listo.")
        self._log_sig.emit(f"ARCHIVO: {p.name} ({size}) cargado")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' ({size}) has been uploaded."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._overlay_panel.muted = self._muted
        if self._muted:
            self._apply_state("MUTED"); self._log_sig.emit("SYS: Microfono silenciado.")
        else:
            self._apply_state("LISTENING"); self._log_sig.emit("SYS: Microfono activo.")

    def _send(self):
        txt = self._overlay_panel._input.text().strip()
        if not txt: return
        self._overlay_panel._input.clear()
        self._log_sig.emit(f"Tu: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state = state; self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception: return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 480, 420
        ov.setGeometry((cw.width() - ow) // 2, (cw.height() - oh) // 2, ow, oh)
        ov.done.connect(self._on_setup_done); ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(json.dumps({"gemini_api_key": key, "os_system": os_name}, indent=4), encoding="utf-8")
        self._ready = True
        if self._overlay: self._overlay.hide(); self._overlay = None
        self._apply_state("LISTENING")
        self._log_sig.emit(f"SYS: Inicializado. OS={os_name.upper()}. JARVIS en linea.")

    # --- Panel control methods ---

    def _toggle_panel(self):
        self._overlay_panel.toggle()

    def show_file_upload(self):
        if not self._overlay_panel._visible:
            self._overlay_panel.show_panel()
            self._log_sig.emit("SYS: Subida de archivos lista.")

    def hide_panels(self):
        if self._overlay_panel._visible:
            self._overlay_panel.hide_panel()
        self._log_sig.emit("SYS: Paneles ocultos.")

    def _handle_panel(self, action: str):
        if action in ("show_chat", "show_all"):
            self._overlay_panel.show_panel()
        elif action == "show_files":
            self.show_file_upload()
        elif action == "hide_all":
            self.hide_panels()

    def set_persona(self, name: str):
        apply_theme(name)
        self.hud.persona = name
        self._overlay_panel.set_persona(name)

    @property
    def current_file(self):
        return self._drop_zone.current_file() if hasattr(self, '_drop_zone') else None


# ═══════════════════════════════════════════════════════════════════════
# ROOT SHIM
# ═══════════════════════════════════════════════════════════════════════

class _RootShim:
    def __init__(self, app: QApplication): self._app = app
    def mainloop(self): self._app.exec()
    def protocol(self, *_): pass


# ═══════════════════════════════════════════════════════════════════════
# JARVIS UI FACADE
# ═══════════════════════════════════════════════════════════════════════

class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.showMaximized()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool: return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted: self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._overlay_panel._drop_zone.current_file()

    @property
    def on_text_command(self): return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb): self._win.on_text_command = cb

    def set_state(self, state: str): self._win._state_sig.emit(state)

    def write_log(self, text: str): self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready: time.sleep(0.1)

    def start_speaking(self): self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")

    def show_file_upload(self): self._win.show_file_upload()

    def hide_panels(self): self._win.hide_panels()

    def toggle_panel(self, action: str): self._win._panel_sig.emit(action)

    def set_persona(self, name: str): self._win.set_persona(name)
