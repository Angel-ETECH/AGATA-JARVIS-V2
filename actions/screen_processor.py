import base64
import io
import json
import threading
from pathlib import Path

from core.config import get_api_key, gemini_generate
from core.logging import get_logger

log = get_logger("jarvis.screen_processor")

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False

try:
    import mss
    _MSS = True
except ImportError:
    _MSS = False

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

_IMG_MAX_W = 640
_IMG_MAX_H = 360
_JPEG_Q = 40


def _compress(img_bytes: bytes) -> tuple[bytes, str]:
    if not _PIL:
        return img_bytes, "image/png"
    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q, optimize=False)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return img_bytes, "image/png"


def _capture_screen() -> bytes | None:
    if not _MSS:
        return None
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            return mss.tools.to_png(img.rgb, img.size)
    except Exception as e:
        log.warning("Screen capture failed: %s", e)
        return None


def _capture_camera() -> bytes | None:
    if not _CV2:
        return None
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        _, buf = cv2.imencode(".png", frame)
        return buf.tobytes()
    except Exception as e:
        log.warning("Camera capture failed: %s", e)
        return None


def _safe_speak(speak_func, msg: str):
    if speak_func and msg:
        try:
            speak_func(msg)
        except Exception:
            pass


def _analyze_image(img_bytes: bytes, mime_type: str, question: str = "") -> str:
    from google import genai
    from google.genai import types as gtypes

    client = genai.Client(api_key=get_api_key())
    encoded = base64.b64encode(img_bytes).decode("ascii")

    prompt = question or "Describe detalladamente lo que ves en esta imagen, en espanol. Se conciso, maximo 3 frases."
    if not prompt.endswith("."):
        prompt += "."

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                gtypes.Part.from_bytes(data=img_bytes, mime_type=mime_type),
                prompt,
            ],
            config=gtypes.GenerateContentConfig(
                system_instruction=(
                    "Eres JARVIS, asistente de IA. Analiza la imagen con precision. "
                    "Responde en espanol, dirigiendote al usuario como 'senor'. "
                    "Se conciso y directo, maximo 3 frases."
                ),
                max_output_tokens=300,
            ),
        )
        return response.text.strip()
    except Exception as e:
        log.error("Vision analysis failed: %s", e)
        return f"No pude analizar la imagen: {e}"


def screen_process(
    parameters: dict | None = None,
    response=None,
    player=None,
    session_memory=None,
    speak_func=None,
):
    p = parameters or {}
    source = p.get("source", "screen")
    question = p.get("question", "")

    log.info("Vision: capturing %s", source)

    if source == "camera":
        img_bytes = _capture_camera()
    else:
        img_bytes = _capture_screen()

    if img_bytes is None:
        msg = f"No pude capturar la {'camara' if source == 'camera' else 'pantalla'}, senor."
        _safe_speak(speak_func, msg)
        if player:
            player.write_log(f"[Vision] {msg}")
        return msg

    img_bytes, mime_type = _compress(img_bytes)

    if player:
        player.write_log(f"[Vision] Captured {len(img_bytes)} bytes, analyzing...")

    def _vision_task():
        try:
            result = _analyze_image(img_bytes, mime_type, question)
            log.info("Vision result: %s", result[:150])
            if player:
                player.write_log(f"[Vision] {result[:200]}")
            _safe_speak(speak_func, result)
        except Exception as e:
            log.error("Vision task failed: %s", e)
            if player:
                player.write_log(f"[Vision] Error: {e}")
            _safe_speak(speak_func, "No pude analizar la imagen, senor.")

    threading.Thread(target=_vision_task, daemon=True).start()
    return "Vision module activated."
