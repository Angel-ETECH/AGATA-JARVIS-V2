import math
import os
import uuid
from pathlib import Path

import requests
from colorthief import ColorThief
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from PIL import Image
from io import BytesIO

TEMP_IMAGES = Path(r"C:\Users\ASUS\OneDrive\Documenti") / "temp_images"

PPTX_SUPPORTED = {"BMP", "GIF", "JPEG", "PNG", "TIFF", "WMF"}


def _ensure_temp():
    TEMP_IMAGES.mkdir(parents=True, exist_ok=True)


def _ensure_pptx_compatible(image_path: str) -> str:
    try:
        img = Image.open(image_path)
        fmt = img.format
        if fmt and fmt.upper() in PPTX_SUPPORTED:
            return image_path
        new_path = Path(image_path).with_suffix(".png")
        if new_path.exists():
            return str(new_path)
        img = img.convert("RGB")
        img.save(new_path, "PNG")
        return str(new_path)
    except Exception:
        return image_path


def buscar_y_descargar_imagen(query: str) -> str | None:
    _ensure_temp()
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=5, size="large"))
            if not results:
                return None
            for result in results:
                try:
                    img_url = result["image"]
                    img_name = f"{query.replace(' ', '_')[:50]}_{uuid.uuid4().hex[:6]}.jpg"
                    img_path = TEMP_IMAGES / img_name
                    img_data = requests.get(img_url, timeout=15).content
                    if len(img_data) < 500:
                        continue
                    Image.open(BytesIO(img_data)).verify()
                    img_path.write_bytes(img_data)
                    return _ensure_pptx_compatible(str(img_path))
                except Exception:
                    continue
            return None
    except Exception:
        return None


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def analizar_paleta_y_brillo(image_path: str) -> dict:
    try:
        color_thief = ColorThief(image_path)
        paleta = color_thief.get_palette(color_count=5, quality=10)
        dominant = paleta[0]
        accent = paleta[1] if len(paleta) > 1 else paleta[0]

        r, g, b = dominant
        r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
        luminancia = (0.2126 * r_norm) + (0.7152 * g_norm) + (0.0722 * b_norm)

        text_main = (0, 0, 0) if luminancia > 0.5 else (255, 255, 255)
        text_secondary = (
            (60, 60, 60) if luminancia > 0.5 else (200, 200, 200)
        )

        return {
            "accent": accent,
            "text_main": text_main,
            "text_secondary": text_secondary,
            "is_background_light": luminancia > 0.5,
            "dominant": dominant,
        }
    except Exception:
        return {
            "accent": (231, 76, 60),
            "text_main": (255, 255, 255),
            "text_secondary": (200, 200, 200),
            "is_background_light": False,
            "dominant": (44, 62, 80),
        }
